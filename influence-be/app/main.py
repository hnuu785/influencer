from contextlib import asynccontextmanager
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import Settings


Channel = Literal["LinkedIn", "X", "Instagram"]


class StoryCardRequest(BaseModel):
    event: str = Field(min_length=10, max_length=2_000)
    unexpected: str = Field(default="", max_length=1_000)
    lesson: str = Field(min_length=3, max_length=1_000)
    audience: str = Field(default="비슷한 고민을 하는 사람", min_length=2, max_length=100)
    channels: list[Channel] = Field(
        default_factory=lambda: ["LinkedIn", "X", "Instagram"],
        min_length=1,
        max_length=3,
    )


class SourceReference(BaseModel):
    label: str
    excerpt: str


class StoryAngle(BaseModel):
    id: str
    label: str
    focus: str


class ChannelDraft(BaseModel):
    channel: Channel
    content: str
    status: Literal["NEEDS_REVIEW"] = "NEEDS_REVIEW"
    source_refs: list[str]


class QualityCheck(BaseModel):
    facts_grounded: bool
    source_visible: bool
    human_approval_required: bool
    note: str


class StoryCard(BaseModel):
    id: str
    status: Literal["STORY_MINED"] = "STORY_MINED"
    visibility: Literal["PRIVATE"] = "PRIVATE"
    title: str
    event: str
    observation: str
    lesson: str
    source_refs: list[SourceReference]
    angles: list[StoryAngle]
    drafts: list[ChannelDraft]
    quality_check: QualityCheck


def clip(value: str, limit: int) -> str:
    value = value.strip()
    return value if len(value) <= limit else f"{value[: limit - 1].rstrip()}…"


def build_draft(channel: Channel, story: StoryCardRequest) -> str:
    event = story.event.strip()
    unexpected = story.unexpected.strip()
    lesson = story.lesson.strip()

    if channel == "LinkedIn":
        blocks = [
            event,
            f"예상과 달랐던 지점은 {unexpected}" if unexpected else "",
            f"이 경험에서 얻은 교훈은 {lesson}",
            f"{story.audience.strip()}에게도 이 경험이 작은 참고가 되길 바랍니다.",
        ]
        return "\n\n".join(block for block in blocks if block)

    if channel == "X":
        blocks = [clip(event, 105)]
        if unexpected:
            blocks.append(f"뜻밖의 지점: {clip(unexpected, 70)}")
        blocks.append(f"오늘의 교훈: {clip(lesson, 80)}")
        return "\n\n".join(blocks)

    blocks = [
        event,
        f"✦ 예상과 달랐던 점\n{unexpected}" if unexpected else "",
        f"✦ 오늘 남기고 싶은 것\n{lesson}",
        "#오늘의기록 #배운점 #스토리로그",
    ]
    return "\n\n".join(block for block in blocks if block)

def create_app(
    settings: Settings | None = None,
    *,
    engine: AsyncEngine | Any | None = None,
    redis_client: Redis | Any | None = None,
) -> FastAPI:
    app_settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        owns_engine = engine is None
        owns_redis = redis_client is None and app_settings.redis_url is not None

        app.state.db = engine or create_async_engine(
            app_settings.database_url,
            connect_args=app_settings.database_connect_args(),
            pool_pre_ping=True,
        )
        app.state.redis = redis_client
        if app.state.redis is None and app_settings.redis_url is not None:
            app.state.redis = Redis.from_url(app_settings.redis_url)

        yield

        if owns_redis and app.state.redis is not None:
            await app.state.redis.aclose()
        if owns_engine:
            await app.state.db.dispose()

    application = FastAPI(
        title="Storylog API",
        description="실제 경험을 근거가 보이는 스토리 카드와 채널별 초안으로 바꾸는 API",
        version="0.4.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(app_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/")
    async def root() -> dict[str, str]:
        return {"message": "Storylog API", "docs": "/docs"}

    @application.post("/api/story-cards", response_model=StoryCard)
    async def create_story_card(story: StoryCardRequest) -> StoryCard:
        source_reference = SourceReference(
            label="오늘의 텍스트 기록",
            excerpt=clip(story.event, 220),
        )
        angle_source = story.unexpected.strip() or story.event.strip()

        return StoryCard(
            id=f"story_{uuid4().hex[:10]}",
            title=clip(story.lesson.rstrip(".!?。！？"), 48),
            event=story.event.strip(),
            observation=story.unexpected.strip() or "별도로 기록하지 않음",
            lesson=story.lesson.strip(),
            source_refs=[source_reference],
            angles=[
                StoryAngle(
                    id="lesson",
                    label="배운 점 중심",
                    focus=clip(story.lesson, 90),
                ),
                StoryAngle(
                    id="turning-point",
                    label="예상 밖의 지점",
                    focus=clip(angle_source, 90),
                ),
            ],
            drafts=[
                ChannelDraft(
                    channel=channel,
                    content=build_draft(channel, story),
                    source_refs=[source_reference.label],
                )
                for channel in story.channels
            ],
            quality_check=QualityCheck(
                facts_grounded=True,
                source_visible=True,
                human_approval_required=True,
                note="입력한 기록만 재구성했습니다. 공개 전 사실·표현·민감 정보를 직접 확인해 주세요.",
            ),
        )

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/ready")
    async def ready() -> JSONResponse:
        db = application.state.db
        redis = application.state.redis
        services = {
            "postgres": "ok",
            "redis": "ok" if redis is not None else "not_configured",
        }

        try:
            async with db.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception:
            services["postgres"] = "unavailable"

        if redis is not None:
            try:
                await redis.ping()
            except Exception:
                services["redis"] = "unavailable"

        healthy = services["postgres"] == "ok" and services["redis"] in {
            "ok",
            "not_configured",
        }
        return JSONResponse(
            status_code=200 if healthy else 503,
            content={
                "status": "ok" if healthy else "degraded",
                "services": services,
            },
        )

    return application


app = create_app()
