from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import HTTPException, UploadFile, status

from app.schemas import ContentPackageResponse


MAX_TEXT_CHARS = 5_000
MAX_PHOTOS = 5
MAX_PHOTO_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 200 * 1024 * 1024
MAX_AUDIO_BYTES = 50 * 1024 * 1024
MAX_MEDIA_DURATION_MS = 3 * 60 * 1000


def classify_content_type(content_type: str | None) -> str:
    value = content_type or ""
    if value.startswith("image/"):
        return "photo"
    if value.startswith("video/"):
        return "video"
    if value.startswith("audio/"):
        return "audio"
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="사진·영상·음성 파일만 추가할 수 있습니다.",
    )


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
