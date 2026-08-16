from __future__ import annotations

import hmac
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Any
from urllib.parse import urlencode
from uuid import uuid4

import httpx
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import create_ai_provider
from app.auth import (
    TokenCipher,
    TokenSigner,
    clear_session_cookie,
    current_user,
    exchange_google_code,
    google_authorization_url,
    google_userinfo,
    refresh_google_token,
    set_session_cookie,
    upsert_google_user,
)
from app.database import session_dependency
from app.models import (
    BrandProfile,
    ContentBrief,
    ContentPackage,
    ConversationLog,
    ExportPackage,
    GoogleConnection,
    MetricSnapshot,
    PatternReference,
    PublicationConfirmation,
    QualityReview,
    SourceAsset,
    StoryCard,
    StoryRecord,
    Transcript,
    User,
    WorkflowRun,
    utc_now,
)
from app.schemas import (
    AuthStartResponse,
    BrandProfileInput,
    CalendarEventSchema,
    ContentPackageResponse,
    ConversationAnswersRequest,
    DevelopmentLoginRequest,
    ExportRequest,
    GeneratedPackage,
    InviteRequest,
    InviteResponse,
    InterviewQuestion,
    MetricInput,
    PackageDecisionRequest,
    PackageUpdateRequest,
    PreparedUploadResponse,
    PublicationRequest,
    PublicationResponse,
    QualityIssueResponse,
    QualityResolutionRequest,
    RecordResponse,
    SourceAssetResponse,
    StoryCardCandidate,
    StoryCardDecisionRequest,
    StoryCardResponse,
    UploadPrepareRequest,
    UploadPrepareResponse,
    UserResponse,
)
from app.storage import (
    MAX_AUDIO_BYTES,
    MAX_MEDIA_DURATION_MS,
    MAX_TEXT_CHARS,
    MAX_VIDEO_BYTES,
    build_export_zip,
    classify_content_type,
    extract_audio,
    extract_video_frame,
    probe_duration_ms,
    save_upload,
    validate_upload_batch,
)


router = APIRouter(prefix="/api")


def _settings(request: Request):
    return request.app.state.settings


def _signer(request: Request) -> TokenSigner:
    return TokenSigner(_settings(request).session_secret)


def _provider(request: Request):
    return request.app.state.ai_provider


def _storage(request: Request):
    return request.app.state.storage


@dataclass
class MaterializedUpload:
    filename: str
    content_type: str
    size: int
    path: Path
    pending_key: str | None = None


async def _record_for_user(
    session: AsyncSession, record_id: str, user_id: str
) -> StoryRecord:
    record = await session.scalar(
        select(StoryRecord).where(
            StoryRecord.id == record_id, StoryRecord.user_id == user_id
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다.")
    return record


async def _package_for_user(
    session: AsyncSession, package_id: str, user_id: str
) -> ContentPackage:
    package = await session.scalar(
        select(ContentPackage)
        .join(ContentBrief, ContentPackage.brief_id == ContentBrief.id)
        .join(StoryCard, ContentBrief.story_card_id == StoryCard.id)
        .join(StoryRecord, StoryCard.record_id == StoryRecord.id)
        .where(ContentPackage.id == package_id, StoryRecord.user_id == user_id)
    )
    if package is None:
        raise HTTPException(status_code=404, detail="제작 패키지를 찾을 수 없습니다.")
    return package


async def _advance(
    session: AsyncSession,
    record: StoryRecord,
    state: str,
    *,
    model_version: str | None = None,
) -> None:
    record.state = state
    record.updated_at = utc_now()
    session.add(
        WorkflowRun(
            record_id=record.id,
            state=state,
            model_version=model_version,
            prompt_version="mvp-v1",
        )
    )


async def _serialize_record(
    session: AsyncSession, record: StoryRecord
) -> RecordResponse:
    assets = (
        await session.scalars(
            select(SourceAsset)
            .where(SourceAsset.record_id == record.id)
            .order_by(SourceAsset.created_at)
        )
    ).all()
    transcripts = {
        item.asset_id: item.text
        for item in (
            await session.scalars(
                select(Transcript).where(
                    Transcript.asset_id.in_([asset.id for asset in assets])
                )
            )
        ).all()
    } if assets else {}
    return RecordResponse(
        id=record.id,
        state=record.state,
        title=record.title,
        sources=[
            SourceAssetResponse(
                id=asset.id,
                type=asset.type,
                filename=asset.filename,
                size_bytes=asset.size_bytes,
                duration_ms=asset.duration_ms,
                transcript=transcripts.get(asset.id),
            )
            for asset in assets
        ],
        calendar_context=[
            CalendarEventSchema.model_validate(item)
            for item in (record.calendar_context or [])
        ],
    )


async def _serialize_package(
    session: AsyncSession, package: ContentPackage
) -> ContentPackageResponse:
    issues = (
        await session.scalars(
            select(QualityReview).where(QualityReview.package_id == package.id)
        )
    ).all()
    return ContentPackageResponse(
        id=package.id,
        format=package.format,
        objective=package.objective,
        hook_options=package.hook_options,
        storyboard=package.storyboard,
        script_or_copy=package.script_or_copy,
        captions=package.captions,
        cta=package.cta,
        production_instructions=package.production_instructions,
        status=package.status,
        approved_copy=package.approved_copy,
        source_refs=package.source_refs,
        reference_refs=package.reference_refs,
        quality_issues=[
            QualityIssueResponse(
                id=issue.id,
                format=package.format,
                category=issue.category,
                severity=issue.severity,
                target_ref=issue.target_ref,
                source_ref=issue.source_ref,
                message=issue.message,
                resolution=issue.resolution,
            )
            for issue in issues
        ],
    )


@router.post("/access/invite", response_model=InviteResponse)
async def verify_invite(request: Request, payload: InviteRequest) -> InviteResponse:
    settings = _settings(request)
    if not hmac.compare_digest(payload.code.strip(), settings.invite_code):
        raise HTTPException(status_code=403, detail="초대 코드를 확인해 주세요.")
    expires = 10 * 60
    return InviteResponse(
        invite_token=_signer(request).sign({"type": "invite"}, expires),
        expires_in_seconds=expires,
    )


@router.get("/auth/google/start", response_model=AuthStartResponse)
async def google_start(request: Request, invite_token: str) -> AuthStartResponse:
    _signer(request).verify(invite_token, "invite")
    settings = _settings(request)
    if not settings.google_oauth_configured:
        if not settings.is_development:
            raise HTTPException(status_code=503, detail="Google 로그인이 설정되지 않았습니다.")
        return AuthStartResponse(mode="development")
    state_token = _signer(request).sign({"type": "google_login"}, 10 * 60)
    return AuthStartResponse(
        mode="google",
        authorization_url=google_authorization_url(
            settings,
            redirect_uri=settings.google_redirect_uri,
            state=state_token,
        ),
    )


@router.post("/auth/development", response_model=UserResponse)
async def development_login(
    request: Request,
    response: Response,
    payload: DevelopmentLoginRequest,
    session: AsyncSession = Depends(session_dependency),
) -> UserResponse:
    settings = _settings(request)
    if not settings.is_development:
        raise HTTPException(status_code=404, detail="개발 로그인을 사용할 수 없습니다.")
    _signer(request).verify(payload.invite_token, "invite")
    user = await upsert_google_user(
        session,
        {
            "sub": "development-google-user",
            "email": "creator@example.com",
            "name": "베타 크리에이터",
            "picture": None,
        },
    )
    set_session_cookie(response, settings, _signer(request), user.id)
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        picture_url=user.picture_url,
        calendar_connected=False,
        ai_mode=_provider(request).mode,
    )


@router.get("/auth/google/callback")
async def google_callback(
    request: Request,
    code: str,
    state: str,
    session: AsyncSession = Depends(session_dependency),
) -> RedirectResponse:
    settings = _settings(request)
    _signer(request).verify(state, "google_login")
    token = await exchange_google_code(
        settings, code=code, redirect_uri=settings.google_redirect_uri
    )
    userinfo = await google_userinfo(token["access_token"])
    user = await upsert_google_user(session, userinfo)
    response = RedirectResponse(settings.app_frontend_url)
    set_session_cookie(response, settings, _signer(request), user.id)
    return response


@router.get("/me", response_model=UserResponse)
async def me(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(session_dependency),
) -> UserResponse:
    connection = await session.get(GoogleConnection, user.id)
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        picture_url=user.picture_url,
        calendar_connected=bool(connection and connection.calendar_connected),
        ai_mode=_provider(request).mode,
    )


@router.post("/auth/logout", status_code=204)
async def logout(response: Response) -> None:
    clear_session_cookie(response)


@router.get("/calendar/start", response_model=AuthStartResponse)
async def calendar_start(
    request: Request,
    user: User = Depends(current_user),
) -> AuthStartResponse:
    settings = _settings(request)
    if not settings.google_oauth_configured:
        if settings.is_development:
            return AuthStartResponse(mode="development")
        raise HTTPException(status_code=503, detail="Calendar 연결이 설정되지 않았습니다.")
    state = _signer(request).sign(
        {"type": "calendar", "user_id": user.id}, 10 * 60
    )
    return AuthStartResponse(
        mode="google",
        authorization_url=google_authorization_url(
            settings,
            redirect_uri=settings.calendar_redirect_uri,
            state=state,
            calendar=True,
        ),
    )


@router.get("/calendar/callback")
async def calendar_callback(
    request: Request,
    code: str,
    state: str,
    session: AsyncSession = Depends(session_dependency),
) -> RedirectResponse:
    settings = _settings(request)
    state_payload = _signer(request).verify(state, "calendar")
    token = await exchange_google_code(
        settings, code=code, redirect_uri=settings.calendar_redirect_uri
    )
    connection = await session.get(GoogleConnection, state_payload["user_id"])
    if connection is None:
        raise HTTPException(status_code=404, detail="Google 계정을 찾을 수 없습니다.")
    connection.calendar_connected = True
    connection.encrypted_token = TokenCipher(settings.session_secret).encrypt(token)
    connection.token_expires_at = utc_now() + timedelta(
        seconds=int(token.get("expires_in", 3600))
    )
    await session.commit()
    return RedirectResponse(f"{settings.app_frontend_url}/?calendar=connected")


@router.get("/calendar/events", response_model=list[CalendarEventSchema])
async def calendar_events(
    request: Request,
    target_date: date = Query(default_factory=date.today, alias="date"),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(session_dependency),
) -> list[CalendarEventSchema]:
    settings = _settings(request)
    start = datetime.combine(target_date, time(0), tzinfo=timezone.utc)
    if not settings.google_oauth_configured and settings.is_development:
        return [
            CalendarEventSchema(
                id="dev-event-1",
                title="AI 음성 에이전트 테스트",
                start_at=start.replace(hour=10),
                end_at=start.replace(hour=11),
                source="development",
            ),
            CalendarEventSchema(
                id="dev-event-2",
                title="팀 제품 회의",
                start_at=start.replace(hour=14),
                end_at=start.replace(hour=15),
                source="development",
            ),
            CalendarEventSchema(
                id="dev-event-3",
                title="하루 회고",
                start_at=start.replace(hour=18, minute=30),
                end_at=start.replace(hour=19),
                source="development",
            ),
        ]
    connection = await session.get(GoogleConnection, user.id)
    if connection is None or not connection.calendar_connected:
        raise HTTPException(status_code=409, detail="Calendar 연결이 필요합니다.")
    cipher = TokenCipher(settings.session_secret)
    token = await refresh_google_token(settings, connection, cipher)
    await session.commit()
    params = {
        "timeMin": start.isoformat().replace("+00:00", "Z"),
        "timeMax": (start + timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        "singleEvents": "true",
        "orderBy": "startTime",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            f"https://www.googleapis.com/calendar/v3/calendars/primary/events?{urlencode(params)}",
            headers={"Authorization": f"Bearer {token['access_token']}"},
        )
    if response.is_error:
        raise HTTPException(status_code=502, detail="Calendar 일정을 가져오지 못했습니다.")
    events = []
    for item in response.json().get("items", []):
        start_value = item.get("start", {}).get("dateTime")
        end_value = item.get("end", {}).get("dateTime")
        if not start_value or not end_value:
            continue
        events.append(
            CalendarEventSchema(
                id=item["id"],
                title=item.get("summary", "제목 없는 일정"),
                start_at=datetime.fromisoformat(start_value),
                end_at=datetime.fromisoformat(end_value),
                source="google",
            )
        )
    return events


@router.delete("/calendar", status_code=204)
async def disconnect_calendar(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(session_dependency),
) -> None:
    connection = await session.get(GoogleConnection, user.id)
    if connection:
        connection.calendar_connected = False
        connection.encrypted_token = None
        connection.token_expires_at = None
        await session.commit()


@router.post("/uploads/prepare", response_model=UploadPrepareResponse)
async def prepare_uploads(
    request: Request,
    payload: UploadPrepareRequest,
    user: User = Depends(current_user),
) -> UploadPrepareResponse:
    validate_upload_batch(
        [(item.content_type, item.size_bytes) for item in payload.files]
    )
    storage = _storage(request)
    if storage.mode == "local":
        return UploadPrepareResponse(mode="multipart")

    prepared_responses = []
    for item in payload.files:
        prepared = await storage.prepare_upload(
            user.id, item.filename, item.content_type
        )
        upload_token = _signer(request).sign(
            {
                "type": "upload",
                "user_id": user.id,
                "key": prepared.key,
                "filename": item.filename,
                "content_type": item.content_type,
                "size_bytes": item.size_bytes,
            },
            storage.presign_ttl_seconds + 300,
        )
        prepared_responses.append(
            PreparedUploadResponse(
                upload_url=prepared.url,
                upload_token=upload_token,
                headers=prepared.headers,
            )
        )
    return UploadPrepareResponse(mode="s3", uploads=prepared_responses)


@router.post("/transcribe")
async def transcribe_answer(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(current_user),
) -> dict[str, str]:
    del user
    if not (file.content_type or "").startswith("audio/"):
        raise HTTPException(status_code=422, detail="음성 파일만 전사할 수 있습니다.")
    target, size = await save_upload(file, _settings(request).storage_path / "temp")
    try:
        if size > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="음성 파일이 너무 큽니다.")
        text_value = await _provider(request).transcribe(target)
        return {"text": text_value, "mode": _provider(request).mode}
    finally:
        target.unlink(missing_ok=True)


@router.post("/records", response_model=RecordResponse)
async def create_record(
    request: Request,
    text_input: Annotated[str, Form(alias="text")] = "",
    calendar_context_json: Annotated[str, Form()] = "[]",
    uploaded_files_json: Annotated[str, Form()] = "[]",
    rights_confirmed: Annotated[bool, Form()] = False,
    files: list[UploadFile] = File(default=[]),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(session_dependency),
) -> RecordResponse:
    if len(text_input) > MAX_TEXT_CHARS:
        raise HTTPException(status_code=413, detail="텍스트는 5천 자까지 입력할 수 있습니다.")
    try:
        calendar_context = json.loads(calendar_context_json)
        validated_calendar = [
            CalendarEventSchema.model_validate(item).model_dump(mode="json")
            for item in calendar_context
        ]
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="선택 일정 형식이 올바르지 않습니다.") from exc
    try:
        upload_tokens = json.loads(uploaded_files_json)
        if not isinstance(upload_tokens, list) or not all(
            isinstance(item, str) for item in upload_tokens
        ):
            raise ValueError
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="업로드 파일 정보가 올바르지 않습니다."
        ) from exc

    direct_uploads: list[dict[str, Any]] = []
    for token in upload_tokens:
        upload_payload = _signer(request).verify(token, "upload")
        if (
            upload_payload.get("user_id") != user.id
            or not str(upload_payload.get("key", "")).startswith(
                f"pending/{user.id}/"
            )
        ):
            raise HTTPException(status_code=403, detail="업로드 권한이 없습니다.")
        direct_uploads.append(upload_payload)

    if direct_uploads and _storage(request).mode != "s3":
        raise HTTPException(
            status_code=422, detail="현재 환경에서는 직접 업로드를 사용할 수 없습니다."
        )
    has_media = bool(files or direct_uploads)
    if not text_input.strip() and not has_media and not validated_calendar:
        raise HTTPException(status_code=422, detail="기록을 하나 이상 추가해 주세요.")
    if has_media and not rights_confirmed:
        raise HTTPException(
            status_code=422,
            detail="파일 사용 권한과 등장 인물 공개 동의를 확인해 주세요.",
        )

    record = StoryRecord(
        user_id=user.id,
        title=(text_input.strip().splitlines()[0][:120] or "오늘의 기록")
        if text_input.strip()
        else "오늘의 기록",
        calendar_context=validated_calendar,
    )
    session.add(record)
    await session.flush()
    normalized_parts: list[str] = []
    if text_input.strip():
        session.add(
            SourceAsset(
                record_id=record.id,
                type="text",
                text=text_input.strip(),
                size_bytes=len(text_input.encode()),
                rights_confirmed=True,
                retention_until=utc_now() + timedelta(days=180),
            )
        )
        normalized_parts.append(text_input.strip())

    materialized_uploads: list[MaterializedUpload] = []
    stored_references: list[str] = []
    audio_duration = 0
    video_duration = 0
    audio_bytes = 0
    video_bytes = 0
    try:
        local_directory = (
            _settings(request).storage_path / user.id / record.id
            if _storage(request).mode == "local"
            else _settings(request).storage_path / "temp" / record.id
        )
        for upload in files:
            content_type = upload.content_type or ""
            filename = Path(upload.filename or "upload").name[:255]
            target, size = await save_upload(upload, local_directory)
            materialized_uploads.append(
                MaterializedUpload(
                    filename=filename,
                    content_type=content_type,
                    size=size,
                    path=target,
                )
            )
        for direct in direct_uploads:
            target, size = await _storage(request).materialize_pending(
                direct["key"],
                int(direct["size_bytes"]),
                direct["content_type"],
                local_directory,
            )
            materialized_uploads.append(
                MaterializedUpload(
                    filename=Path(direct["filename"]).name[:255],
                    content_type=direct["content_type"],
                    size=size,
                    path=target,
                    pending_key=direct["key"],
                )
            )

        validate_upload_batch(
            [(item.content_type, item.size) for item in materialized_uploads]
        )
        stored_assets: list[tuple[SourceAsset, MaterializedUpload]] = []
        for item in materialized_uploads:
            asset_type = classify_content_type(item.content_type)
            target = item.path
            size = item.size
            duration_ms = (
                await probe_duration_ms(target)
                if asset_type in {"audio", "video"}
                else None
            )
            if asset_type == "audio":
                audio_bytes += size
                audio_duration += duration_ms or 0
                if audio_bytes > MAX_AUDIO_BYTES or (
                    duration_ms is not None and audio_duration > MAX_MEDIA_DURATION_MS
                ):
                    raise HTTPException(status_code=413, detail="음성은 합계 3분까지입니다.")
            if asset_type == "video":
                video_bytes += size
                video_duration += duration_ms or 0
                if video_bytes > MAX_VIDEO_BYTES or (
                    duration_ms is not None and video_duration > MAX_MEDIA_DURATION_MS
                ):
                    raise HTTPException(
                        status_code=413, detail="영상은 합계 3분·200MB까지입니다."
                    )
            asset = SourceAsset(
                record_id=record.id,
                type=asset_type,
                filename=item.filename,
                content_type=item.content_type,
                storage_path=None,
                size_bytes=size,
                duration_ms=duration_ms,
                rights_confirmed=True,
                retention_until=utc_now() + timedelta(days=30),
            )
            session.add(asset)
            await session.flush()
            stored_assets.append((asset, item))
            if asset_type in {"audio", "video"}:
                transcription_target = target
                extracted_audio: Path | None = None
                if asset_type == "video":
                    extracted_audio = await extract_audio(target, target.parent)
                    if extracted_audio:
                        transcription_target = extracted_audio
                try:
                    transcript_text = await _provider(request).transcribe(
                        transcription_target
                    )
                finally:
                    if extracted_audio:
                        extracted_audio.unlink(missing_ok=True)
                session.add(
                    Transcript(
                        asset_id=asset.id,
                        text=transcript_text,
                        segments=[],
                        language="ko",
                    )
                )
                normalized_parts.append(transcript_text)
                if asset_type == "video":
                    frame = await extract_video_frame(target, target.parent)
                    if frame:
                        try:
                            normalized_parts.append(
                                "[영상 장면 분석: "
                                + await _provider(request).describe_image(
                                    frame, "image/jpeg"
                                )
                                + "]"
                            )
                        finally:
                            frame.unlink(missing_ok=True)
            elif asset_type == "photo":
                description = await _provider(request).describe_image(
                    target, item.content_type
                )
                normalized_parts.append(f"[사진 분석: {description}]")

        for asset, item in stored_assets:
            reference = await _storage(request).store_record_file(
                item.path,
                user.id,
                record.id,
                item.content_type,
                pending_key=item.pending_key,
            )
            asset.storage_path = reference
            stored_references.append(reference)
        normalized_parts.extend(
            f"[일정: {item['title']}]" for item in validated_calendar
        )
        record.normalized_text = "\n".join(normalized_parts)
        await _advance(session, record, "MEDIA_PROCESSED")
        await session.commit()
    except Exception:
        await session.rollback()
        for reference in stored_references:
            await _storage(request).delete(reference)
        for item in materialized_uploads:
            item.path.unlink(missing_ok=True)
        raise
    if _storage(request).mode == "s3":
        for item in materialized_uploads:
            item.path.unlink(missing_ok=True)
    await session.refresh(record)
    return await _serialize_record(session, record)


@router.get("/records/{record_id}", response_model=RecordResponse)
async def get_record(
    record_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(session_dependency),
) -> RecordResponse:
    record = await _record_for_user(session, record_id, user.id)
    return await _serialize_record(session, record)


@router.delete("/records/{record_id}", status_code=204)
async def delete_record(
    request: Request,
    record_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(session_dependency),
) -> None:
    record = await _record_for_user(session, record_id, user.id)
    assets = (
        await session.scalars(
            select(SourceAsset).where(SourceAsset.record_id == record.id)
        )
    ).all()
    exports = (
        await session.scalars(
            select(ExportPackage).where(ExportPackage.record_id == record.id)
        )
    ).all()
    for asset in assets:
        await _storage(request).delete(asset.storage_path)
    for export in exports:
        Path(export.storage_path).unlink(missing_ok=True)
    await session.delete(record)
    await session.commit()


@router.get("/records/{record_id}/questions", response_model=list[InterviewQuestion])
async def get_questions(
    record_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(session_dependency),
) -> list[InterviewQuestion]:
    record = await _record_for_user(session, record_id, user.id)
    calendar_title = (
        record.calendar_context[0]["title"] if record.calendar_context else "오늘의 기록"
    )
    return [
        InterviewQuestion(
            id="unexpected",
            text="가장 예상과 달랐던 점은 무엇이었나요?",
            purpose="구체적인 관찰 찾기",
        ),
        InterviewQuestion(
            id="meaning",
            text=f"‘{calendar_title}’ 경험이 다음 선택을 어떻게 바꿨나요?",
            purpose="사용자의 관점과 배움 찾기",
        ),
        InterviewQuestion(
            id="audience",
            text="이 이야기를 누구에게 가장 먼저 들려주고 싶나요?",
            purpose="목표 독자 확인",
        ),
    ]


@router.post(
    "/records/{record_id}/answers", response_model=list[StoryCardResponse]
)
async def submit_answers(
    request: Request,
    record_id: str,
    payload: ConversationAnswersRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(session_dependency),
) -> list[StoryCardResponse]:
    record = await _record_for_user(session, record_id, user.id)
    profile = await session.get(BrandProfile, user.id)
    if profile is None:
        profile = BrandProfile(user_id=user.id)
        session.add(profile)
    profile.topics = payload.profile.topics
    profile.audience = payload.profile.audience
    profile.tone = payload.profile.tone
    profile.taboo_topics = payload.profile.taboo_topics
    await session.execute(
        delete(ConversationLog).where(ConversationLog.record_id == record.id)
    )
    answer_parts = []
    for index, answer in enumerate(payload.answers):
        session.add(
            ConversationLog(
                record_id=record.id,
                question=answer.question,
                answer_type=answer.answer_type,
                answer_text=answer.answer_text,
                visibility=answer.visibility,
                order_index=index,
            )
        )
        if answer.visibility != "exclude":
            answer_parts.append(f"질문: {answer.question}\n답변: {answer.answer_text}")
    await _advance(session, record, "INTERVIEWED")
    context = "\n\n".join(
        [
            record.normalized_text,
            *answer_parts,
            f"목표 독자: {profile.audience}",
            f"말투: {profile.tone}",
        ]
    )
    cards = await _provider(request).create_story_cards(context)
    await session.execute(delete(StoryCard).where(StoryCard.record_id == record.id))
    source_asset = await session.scalar(
        select(SourceAsset).where(SourceAsset.record_id == record.id).limit(1)
    )
    stored: list[StoryCard] = []
    for candidate in cards.cards:
        item = StoryCard(
            record_id=record.id,
            event=candidate.event,
            observation=candidate.observation,
            emotion=candidate.emotion,
            opinion=candidate.opinion,
            evidence_level=candidate.evidence_level,
            content_angles=candidate.content_angles,
            source_refs=[
                {
                    "asset_id": source_asset.id if source_asset else "calendar",
                    "excerpt": candidate.source_excerpt,
                }
            ],
        )
        session.add(item)
        stored.append(item)
    await _advance(
        session,
        record,
        "WAITING_STORY_APPROVAL",
        model_version=_provider(request).review_model,
    )
    await session.commit()
    for item in stored:
        await session.refresh(item)
    return [
        StoryCardResponse(
            id=item.id,
            event=item.event,
            observation=item.observation,
            emotion=item.emotion,
            opinion=item.opinion,
            evidence_level=item.evidence_level,
            content_angles=item.content_angles,
            source_excerpt=item.source_refs[0]["excerpt"],
            status=item.status,
            source_refs=item.source_refs,
        )
        for item in stored
    ]


@router.get(
    "/records/{record_id}/story-cards", response_model=list[StoryCardResponse]
)
async def story_cards(
    record_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(session_dependency),
) -> list[StoryCardResponse]:
    await _record_for_user(session, record_id, user.id)
    items = (
        await session.scalars(
            select(StoryCard).where(StoryCard.record_id == record_id)
        )
    ).all()
    return [
        StoryCardResponse(
            id=item.id,
            event=item.event,
            observation=item.observation,
            emotion=item.emotion,
            opinion=item.opinion,
            evidence_level=item.evidence_level,
            content_angles=item.content_angles,
            source_excerpt=item.source_refs[0].get("excerpt", ""),
            status=item.status,
            source_refs=item.source_refs,
        )
        for item in items
    ]


@router.post(
    "/records/{record_id}/story-cards/{story_card_id}/decision",
    response_model=list[ContentPackageResponse],
)
async def decide_story_card(
    request: Request,
    record_id: str,
    story_card_id: str,
    payload: StoryCardDecisionRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(session_dependency),
) -> list[ContentPackageResponse]:
    record = await _record_for_user(session, record_id, user.id)
    card = await session.scalar(
        select(StoryCard).where(
            StoryCard.id == story_card_id, StoryCard.record_id == record.id
        )
    )
    if card is None:
        raise HTTPException(status_code=404, detail="StoryCard를 찾을 수 없습니다.")
    if payload.action == "reject":
        card.status = "rejected"
        await session.commit()
        return []
    if payload.edits:
        for field, value in payload.edits.model_dump(
            exclude={"source_excerpt"}
        ).items():
            setattr(card, field, value)
        card.source_refs[0]["excerpt"] = payload.edits.source_excerpt
    await session.execute(
        StoryCard.__table__.update()
        .where(
            StoryCard.record_id == record.id,
            StoryCard.id != card.id,
        )
        .values(status="rejected")
    )
    card.status = "approved"
    await _advance(session, record, "STORY_APPROVED")
    story_schema = StoryCardCandidate(
        event=card.event,
        observation=card.observation,
        emotion=card.emotion,
        opinion=card.opinion,
        evidence_level=card.evidence_level,
        content_angles=card.content_angles,
        source_excerpt=card.source_refs[0].get("excerpt", ""),
    )
    query_text = f"{card.event}\n{card.observation}\n{card.opinion}"
    query_embedding = await _provider(request).embed(query_text)
    card.embedding = query_embedding
    patterns = (await session.scalars(select(PatternReference))).all()
    if query_embedding and session.bind and session.bind.dialect.name == "postgresql":
        for pattern in patterns:
            if pattern.embedding is None:
                pattern.embedding = await _provider(request).embed(
                    f"{pattern.format} {pattern.hook_type} {pattern.guidance}"
                )
        await session.flush()
        patterns = (
            await session.scalars(
                select(PatternReference)
                .order_by(PatternReference.embedding.cosine_distance(query_embedding))
                .limit(6)
            )
        ).all()
    await _advance(session, record, "CONTEXT_RETRIEVED")
    profile = await session.get(BrandProfile, user.id)
    prior_packages = (
        await session.scalars(
            select(ContentPackage)
            .join(ContentBrief, ContentPackage.brief_id == ContentBrief.id)
            .join(StoryCard, ContentBrief.story_card_id == StoryCard.id)
            .join(StoryRecord, StoryCard.record_id == StoryRecord.id)
            .where(
                StoryRecord.user_id == user.id,
                ContentPackage.status == "approved",
            )
            .limit(5)
        )
    ).all()
    pattern_payload = [
        {
            "id": pattern.id,
            "format": pattern.format,
            "hook_type": pattern.hook_type,
            "structure": pattern.structure,
            "objective": pattern.objective,
            "guidance": pattern.guidance,
            "rights_basis": pattern.rights_basis,
        }
        for pattern in patterns
    ]
    generated = await _provider(request).create_packages(
        story_schema,
        {
            "topics": profile.topics if profile else [],
            "audience": profile.audience if profile else "",
            "tone": profile.tone if profile else "",
            "taboo_topics": profile.taboo_topics if profile else [],
        },
        [" ".join(item.script_or_copy) for item in prior_packages],
        pattern_payload,
    )
    brief = ContentBrief(
        story_card_id=card.id,
        audience=generated.brief.audience,
        objective=generated.brief.objective,
        core_message=generated.brief.core_message,
        proof_points=generated.brief.proof_points,
        pattern_ids=[pattern.id for pattern in patterns],
        constraints=generated.brief.constraints,
    )
    session.add(brief)
    await session.flush()
    stored_packages: list[ContentPackage] = []
    for generated_package in generated.packages:
        package = ContentPackage(
            brief_id=brief.id,
            format=generated_package.format,
            objective=generated_package.objective,
            hook_options=generated_package.hook_options,
            storyboard=[
                beat.model_dump() for beat in generated_package.storyboard
            ],
            script_or_copy=generated_package.script_or_copy,
            captions=generated_package.captions,
            cta=generated_package.cta,
            production_instructions=generated_package.production_instructions,
            source_refs=card.source_refs,
            reference_refs=[
                pattern.id
                for pattern in patterns
                if pattern.format == generated_package.format
            ],
            embedding=await _provider(request).embed(
                " ".join(generated_package.script_or_copy)
            ),
        )
        session.add(package)
        stored_packages.append(package)
    await session.flush()
    quality = await _provider(request).review(
        record.normalized_text,
        generated.packages,
        [pattern.guidance for pattern in patterns],
    )
    package_by_format = {package.format: package for package in stored_packages}
    for issue in quality.issues:
        session.add(
            QualityReview(
                package_id=package_by_format[issue.format].id,
                category=issue.category,
                severity=issue.severity,
                target_ref=issue.target_ref,
                source_ref=issue.source_ref,
                message=issue.message,
            )
        )
    await _advance(
        session,
        record,
        "WAITING_FINAL_APPROVAL",
        model_version=_provider(request).review_model,
    )
    await session.commit()
    return [
        await _serialize_package(session, package) for package in stored_packages
    ]


@router.get(
    "/records/{record_id}/packages", response_model=list[ContentPackageResponse]
)
async def get_packages(
    record_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(session_dependency),
) -> list[ContentPackageResponse]:
    await _record_for_user(session, record_id, user.id)
    packages = (
        await session.scalars(
            select(ContentPackage)
            .join(ContentBrief, ContentPackage.brief_id == ContentBrief.id)
            .join(StoryCard, ContentBrief.story_card_id == StoryCard.id)
            .where(StoryCard.record_id == record_id)
        )
    ).all()
    order = {"reel": 0, "carousel": 1, "story": 2}
    return [
        await _serialize_package(session, item)
        for item in sorted(packages, key=lambda item: order[item.format])
    ]


@router.patch("/packages/{package_id}", response_model=ContentPackageResponse)
async def update_package(
    package_id: str,
    payload: PackageUpdateRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(session_dependency),
) -> ContentPackageResponse:
    package = await _package_for_user(session, package_id, user.id)
    package.script_or_copy = payload.script_or_copy
    package.captions = payload.captions
    package.cta = payload.cta
    package.status = "waiting_for_approval"
    await session.commit()
    return await _serialize_package(session, package)


@router.post(
    "/packages/{package_id}/decision", response_model=ContentPackageResponse
)
async def decide_package(
    package_id: str,
    payload: PackageDecisionRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(session_dependency),
) -> ContentPackageResponse:
    package = await _package_for_user(session, package_id, user.id)
    package.status = "approved" if payload.action == "approve" else "waiting_for_approval"
    package.approved_copy = (
        "\n\n".join(package.script_or_copy) if payload.action == "approve" else None
    )
    await session.commit()
    return await _serialize_package(session, package)


@router.post(
    "/quality-issues/{issue_id}/resolve", response_model=QualityIssueResponse
)
async def resolve_quality_issue(
    issue_id: str,
    payload: QualityResolutionRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(session_dependency),
) -> QualityIssueResponse:
    issue = await session.scalar(
        select(QualityReview)
        .join(ContentPackage, QualityReview.package_id == ContentPackage.id)
        .join(ContentBrief, ContentPackage.brief_id == ContentBrief.id)
        .join(StoryCard, ContentBrief.story_card_id == StoryCard.id)
        .join(StoryRecord, StoryCard.record_id == StoryRecord.id)
        .where(QualityReview.id == issue_id, StoryRecord.user_id == user.id)
    )
    if issue is None:
        raise HTTPException(status_code=404, detail="품질 경고를 찾을 수 없습니다.")
    issue.resolution = payload.resolution
    await session.commit()
    package = await session.get(ContentPackage, issue.package_id)
    return QualityIssueResponse(
        id=issue.id,
        format=package.format,
        category=issue.category,
        severity=issue.severity,
        target_ref=issue.target_ref,
        source_ref=issue.source_ref,
        message=issue.message,
        resolution=issue.resolution,
    )


@router.post("/records/{record_id}/export")
async def export_packages(
    request: Request,
    record_id: str,
    payload: ExportRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(session_dependency),
) -> FileResponse:
    record = await _record_for_user(session, record_id, user.id)
    packages = [
        await _package_for_user(session, package_id, user.id)
        for package_id in payload.package_ids
    ]
    if any(package.status != "approved" for package in packages):
        raise HTTPException(status_code=409, detail="승인한 패키지만 내보낼 수 있습니다.")
    unresolved = await session.scalar(
        select(QualityReview.id)
        .where(
            QualityReview.package_id.in_([package.id for package in packages]),
            QualityReview.resolution.is_(None),
        )
        .limit(1)
    )
    if unresolved:
        raise HTTPException(
            status_code=409,
            detail="품질 경고를 수정하거나 확인한 뒤 내보내 주세요.",
        )
    serialized = [
        await _serialize_package(session, package) for package in packages
    ]
    assets = (
        await session.scalars(
            select(SourceAsset).where(SourceAsset.record_id == record.id)
        )
    ).all()
    export_id = str(uuid4())
    target = (
        _settings(request).storage_path
        / user.id
        / record.id
        / f"storilog-{export_id}.zip"
    )
    temporary_root = _settings(request).storage_path / "temp"
    temporary_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=temporary_root) as temporary_directory:
        source_paths = []
        for asset in assets:
            if not asset.storage_path:
                continue
            source_path = await _storage(request).materialize(
                asset.storage_path, Path(temporary_directory)
            )
            source_paths.append(
                (source_path, asset.filename or source_path.name)
            )
        build_export_zip(target, serialized, source_paths)
    session.add(
        ExportPackage(
            id=export_id,
            user_id=user.id,
            record_id=record.id,
            package_ids=payload.package_ids,
            storage_path=str(target),
            expires_at=utc_now() + timedelta(days=180),
        )
    )
    await _advance(session, record, "EXPORTED")
    await session.commit()
    return FileResponse(
        target,
        media_type="application/zip",
        filename=f"storilog-{record.id[:8]}.zip",
    )


@router.post(
    "/records/{record_id}/publication", response_model=PublicationResponse
)
async def confirm_publication(
    record_id: str,
    payload: PublicationRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(session_dependency),
) -> PublicationResponse:
    record = await _record_for_user(session, record_id, user.id)
    item = PublicationConfirmation(
        user_id=user.id,
        record_id=record.id,
        format=payload.format,
        published_url=str(payload.published_url),
        published_at=payload.published_at,
    )
    session.add(item)
    await _advance(session, record, "PUBLISHED_CONFIRMED")
    await session.commit()
    await session.refresh(item)
    return PublicationResponse(
        id=item.id,
        format=item.format,
        published_url=item.published_url,
        published_at=item.published_at,
    )


@router.post("/publications/{publication_id}/metrics", status_code=204)
async def save_metrics(
    publication_id: str,
    payload: MetricInput,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(session_dependency),
) -> None:
    publication = await session.scalar(
        select(PublicationConfirmation).where(
            PublicationConfirmation.id == publication_id,
            PublicationConfirmation.user_id == user.id,
        )
    )
    if publication is None:
        raise HTTPException(status_code=404, detail="게시 확인 정보를 찾을 수 없습니다.")
    existing = await session.scalar(
        select(MetricSnapshot).where(
            MetricSnapshot.publication_id == publication.id,
            MetricSnapshot.elapsed_hours == payload.elapsed_hours,
        )
    )
    if existing is None:
        existing = MetricSnapshot(
            publication_id=publication.id,
            elapsed_hours=payload.elapsed_hours,
        )
        session.add(existing)
    existing.views = payload.views
    existing.likes = payload.likes
    existing.comments = payload.comments
    existing.shares = payload.shares
    existing.saves = payload.saves
    record = await session.get(StoryRecord, publication.record_id)
    if payload.elapsed_hours == 72 and record:
        await _advance(session, record, "MEASURED")
    await session.commit()
