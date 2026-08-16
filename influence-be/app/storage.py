from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile, status

from app.config import Settings
from app.schemas import ContentPackageResponse


MAX_TEXT_CHARS = 5_000
MAX_PHOTOS = 5
MAX_PHOTO_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 200 * 1024 * 1024
MAX_AUDIO_BYTES = 50 * 1024 * 1024
MAX_MEDIA_DURATION_MS = 3 * 60 * 1000
SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@dataclass(frozen=True)
class PreparedUpload:
    key: str
    url: str
    headers: dict[str, str]


class MediaStorage:
    def __init__(self, settings: Settings):
        settings.validate_storage()
        self.mode = settings.storage_backend
        self.bucket = settings.s3_bucket
        self.region = settings.s3_region
        self.presign_ttl_seconds = settings.s3_presign_ttl_seconds
        self._s3 = (
            boto3.client("s3", region_name=self.region)
            if self.mode == "s3"
            else None
        )

    async def prepare_upload(
        self, user_id: str, filename: str, content_type: str
    ) -> PreparedUpload:
        if self._s3 is None or self.bucket is None:
            raise RuntimeError("S3 storage is not configured")
        suffix = Path(filename).suffix[:12]
        key = f"pending/{user_id}/{uuid4()}{suffix}"
        params = {
            "Bucket": self.bucket,
            "Key": key,
            "ContentType": content_type,
        }
        url = await asyncio.to_thread(
            self._s3.generate_presigned_url,
            "put_object",
            Params=params,
            ExpiresIn=self.presign_ttl_seconds,
            HttpMethod="PUT",
        )
        return PreparedUpload(
            key=key,
            url=url,
            headers={"Content-Type": content_type},
        )

    async def materialize_pending(
        self,
        key: str,
        expected_size: int,
        expected_content_type: str,
        directory: Path,
    ) -> tuple[Path, int]:
        if self._s3 is None or self.bucket is None:
            raise HTTPException(status_code=422, detail="S3 업로드를 사용할 수 없습니다.")
        try:
            metadata = await asyncio.to_thread(
                self._s3.head_object, Bucket=self.bucket, Key=key
            )
        except ClientError as exc:
            raise HTTPException(
                status_code=422,
                detail="업로드한 파일을 확인할 수 없습니다. 다시 선택해 주세요.",
            ) from exc
        actual_size = int(metadata.get("ContentLength", 0))
        actual_content_type = metadata.get("ContentType") or ""
        if actual_size != expected_size or actual_content_type != expected_content_type:
            raise HTTPException(
                status_code=422,
                detail="업로드한 파일 정보가 일치하지 않습니다. 다시 선택해 주세요.",
            )
        directory.mkdir(parents=True, exist_ok=True)
        suffix = Path(key).suffix[:12]
        target = directory / f"{uuid4()}{suffix}"
        await asyncio.to_thread(
            self._s3.download_file, self.bucket, key, str(target)
        )
        return target, actual_size

    async def store_record_file(
        self,
        path: Path,
        user_id: str,
        record_id: str,
        content_type: str,
        *,
        pending_key: str | None = None,
    ) -> str:
        if self._s3 is None or self.bucket is None:
            return str(path)
        suffix = path.suffix[:12]
        key = f"records/{user_id}/{record_id}/{uuid4()}{suffix}"
        if pending_key:
            await asyncio.to_thread(
                self._s3.copy_object,
                Bucket=self.bucket,
                CopySource={"Bucket": self.bucket, "Key": pending_key},
                Key=key,
                ContentType=content_type,
                MetadataDirective="REPLACE",
            )
            await asyncio.to_thread(
                self._s3.delete_object, Bucket=self.bucket, Key=pending_key
            )
        else:
            await asyncio.to_thread(
                self._s3.upload_file,
                str(path),
                self.bucket,
                key,
                ExtraArgs={"ContentType": content_type},
            )
        return f"s3://{self.bucket}/{key}"

    async def materialize(self, reference: str, directory: Path) -> Path:
        parsed = self._parse_s3_reference(reference)
        if parsed is None:
            return Path(reference)
        bucket, key = parsed
        if self._s3 is None:
            raise RuntimeError("S3 storage is not configured")
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{uuid4()}{Path(key).suffix[:12]}"
        await asyncio.to_thread(self._s3.download_file, bucket, key, str(target))
        return target

    async def delete(self, reference: str | None) -> None:
        if not reference:
            return
        parsed = self._parse_s3_reference(reference)
        if parsed is None:
            Path(reference).unlink(missing_ok=True)
            return
        if self._s3 is None:
            return
        bucket, key = parsed
        await asyncio.to_thread(self._s3.delete_object, Bucket=bucket, Key=key)

    @staticmethod
    def _parse_s3_reference(reference: str) -> tuple[str, str] | None:
        if not reference.startswith("s3://"):
            return None
        bucket, separator, key = reference[5:].partition("/")
        if not separator or not bucket or not key:
            raise ValueError("Invalid S3 storage reference")
        return bucket, key


def classify_content_type(content_type: str | None) -> str:
    value = content_type or ""
    if value.startswith("image/"):
        if value not in SUPPORTED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="사진은 JPG, PNG, WebP, GIF 형식만 추가할 수 있습니다.",
            )
        return "photo"
    if value.startswith("video/"):
        return "video"
    if value.startswith("audio/"):
        return "audio"
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="사진·영상·음성 파일만 추가할 수 있습니다.",
    )


def validate_upload_batch(
    files: list[tuple[str | None, int]],
) -> None:
    photo_count = 0
    audio_bytes = 0
    video_bytes = 0
    for content_type, size in files:
        asset_type = classify_content_type(content_type)
        if size <= 0:
            raise HTTPException(status_code=422, detail="빈 파일은 추가할 수 없습니다.")
        if asset_type == "photo":
            photo_count += 1
            if photo_count > MAX_PHOTOS:
                raise HTTPException(status_code=413, detail="사진은 최대 5장입니다.")
            if size > MAX_PHOTO_BYTES:
                raise HTTPException(status_code=413, detail="사진은 장당 10MB까지입니다.")
        elif asset_type == "audio":
            audio_bytes += size
            if audio_bytes > MAX_AUDIO_BYTES:
                raise HTTPException(status_code=413, detail="음성은 합계 50MB까지입니다.")
        elif asset_type == "video":
            video_bytes += size
            if video_bytes > MAX_VIDEO_BYTES:
                raise HTTPException(status_code=413, detail="영상은 합계 200MB까지입니다.")


async def save_upload(upload: UploadFile, directory: Path) -> tuple[Path, int]:
    directory.mkdir(parents=True, exist_ok=True)
    suffix = Path(upload.filename or "").suffix[:12]
    target = directory / f"{uuid4()}{suffix}"
    size = 0
    with target.open("wb") as output:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            output.write(chunk)
    await upload.close()
    return target, size


async def probe_duration_ms(path: Path) -> int | None:
    if shutil.which("ffprobe") is None:
        return None
    process = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await process.communicate()
    if process.returncode != 0:
        return None
    try:
        return int(float(stdout.decode().strip()) * 1000)
    except ValueError:
        return None


async def extract_audio(video_path: Path, directory: Path) -> Path | None:
    if shutil.which("ffmpeg") is None:
        return None
    target = directory / f"{uuid4()}.mp3"
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "libmp3lame",
        str(target),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await process.communicate()
    if process.returncode != 0 or not target.exists():
        return None
    return target


async def extract_video_frame(video_path: Path, directory: Path) -> Path | None:
    if shutil.which("ffmpeg") is None:
        return None
    target = directory / f"{uuid4()}.jpg"
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-ss",
        "1",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-vf",
        "scale='min(1280,iw)':-2",
        str(target),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await process.communicate()
    if process.returncode != 0 or not target.exists():
        return None
    return target


def package_markdown(package: ContentPackageResponse) -> str:
    lines = [
        f"# {package.format.upper()} 제작 패키지",
        "",
        f"- 목적: {package.objective}",
        f"- 상태: {package.status}",
        "",
        "## 훅 후보",
        "",
    ]
    lines.extend(f"- {hook}" for hook in package.hook_options)
    lines.extend(["", "## Storyboard", ""])
    for beat in package.storyboard:
        lines.extend(
            [
                f"### {beat.order}. {beat.label} · {beat.timing}",
                "",
                f"- 화면: {beat.visual}",
                f"- 대사·카피: {beat.content}",
                f"- 제작 지시: {beat.production_note}",
                "",
            ]
        )
    lines.extend(["## 대사·카피", ""])
    lines.extend(f"- {copy}" for copy in package.script_or_copy)
    if package.captions:
        lines.extend(["", "## 자막·캡션", ""])
        lines.extend(f"- {caption}" for caption in package.captions)
    lines.extend(["", "## CTA", "", package.cta, "", "## 제작 지시", ""])
    lines.extend(f"- {instruction}" for instruction in package.production_instructions)
    return "\n".join(lines).strip() + "\n"


def build_export_zip(
    target: Path,
    packages: list[ContentPackageResponse],
    source_paths: list[tuple[Path, str]],
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
        for package in packages:
            archive.writestr(
                f"{package.format}/production-package.md",
                package_markdown(package),
            )
        for source_path, filename in source_paths:
            if source_path.exists():
                archive.write(source_path, f"sources/{filename}")
