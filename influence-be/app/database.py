from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Request
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from app.models import (
    Base,
    ExportPackage,
    PatternReference,
    SourceAsset,
    StoryRecord,
    User,
)


PATTERN_SEEDS = [
    {
        "id": "pattern-reel-contrast",
        "format": "reel",
        "hook_type": "contrast",
        "structure": ["hook", "context", "demo", "takeaway", "cta"],
        "objective": "discovery",
        "topic_tags": ["AI", "product", "experiment"],
        "guidance": "예상과 실제의 차이를 2초 훅으로 보여주고 개인 실험 근거를 짧게 시연한다.",
    },
    {
        "id": "pattern-carousel-checklist",
        "format": "carousel",
        "hook_type": "checklist",
        "structure": ["promise", "problem", "principle", "steps", "summary", "cta"],
        "objective": "save_and_share",
        "topic_tags": ["AI", "how-to", "learning"],
        "guidance": "한 가지 배움을 5~7개의 짧은 슬라이드와 실행 체크리스트로 나눈다.",
    },
    {
        "id": "pattern-story-poll",
        "format": "story",
        "hook_type": "question",
        "structure": ["context", "question", "poll", "takeaway", "next"],
        "objective": "relationship",
        "topic_tags": ["AI", "opinion", "feedback"],
        "guidance": "개인 경험을 짧게 공개하고 양자택일 투표와 다음 이야기 예고로 반응을 받는다.",
    },
]


async def initialize_database(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if engine.dialect.name == "postgresql":
        async with engine.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.run_sync(Base.metadata.create_all)
    else:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        existing = await session.scalar(select(PatternReference.id).limit(1))
        if existing is None:
            session.add_all(PatternReference(**seed) for seed in PATTERN_SEEDS)
            await session.commit()


async def cleanup_expired_data(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    cutoff = now or datetime.now(timezone.utc)
    removed = {"assets": 0, "exports": 0, "users": 0}
    async with session_factory() as session:
        assets = (
            await session.scalars(
                select(SourceAsset).where(SourceAsset.retention_until <= cutoff)
            )
        ).all()
        for asset in assets:
            if asset.storage_path:
                Path(asset.storage_path).unlink(missing_ok=True)
            await session.delete(asset)
        removed["assets"] = len(assets)

        exports = (
            await session.scalars(
                select(ExportPackage).where(ExportPackage.expires_at <= cutoff)
            )
        ).all()
        for export in exports:
            Path(export.storage_path).unlink(missing_ok=True)
            await session.delete(export)
        removed["exports"] = len(exports)

        expired_users = (
            await session.scalars(select(User).where(User.expires_at <= cutoff))
        ).all()
        if expired_users:
            user_ids = [user.id for user in expired_users]
            user_assets = (
                await session.scalars(
                    select(SourceAsset)
                    .join(StoryRecord, SourceAsset.record_id == StoryRecord.id)
                    .where(StoryRecord.user_id.in_(user_ids))
                )
            ).all()
            for asset in user_assets:
                if asset.storage_path:
                    Path(asset.storage_path).unlink(missing_ok=True)
            user_exports = (
                await session.scalars(
                    select(ExportPackage).where(ExportPackage.user_id.in_(user_ids))
                )
            ).all()
            for export in user_exports:
                Path(export.storage_path).unlink(missing_ok=True)
            await session.execute(delete(User).where(User.id.in_(user_ids)))
        removed["users"] = len(expired_users)
        await session.commit()
    return removed


async def session_dependency(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session
