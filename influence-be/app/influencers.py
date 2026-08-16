from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    Text,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine


metadata = MetaData()

influencer_profiles = Table(
    "influencer_profiles",
    metadata,
    Column("profile_id", String(64), primary_key=True),
    Column("platform", String(32), nullable=False, index=True),
    Column("username", String(255), nullable=False, index=True),
    Column("profile_url", Text, nullable=False, unique=True),
    Column("full_name", String(255), nullable=False, server_default=""),
    Column("biography", Text, nullable=False, server_default=""),
    Column("profile_pic_url", Text),
    Column("follower_count", BigInteger, index=True),
    Column("following_count", BigInteger),
    Column("media_count", BigInteger),
    Column("is_verified", Boolean, index=True),
    Column("category", String(255)),
    Column("external_url", Text),
    Column("source", String(32), nullable=False, server_default="public_web"),
    Column("source_fields", JSON, nullable=False, server_default="{}"),
    Column(
        "first_collected_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    Column(
        "last_collected_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    ),
)


class InfluencerProfile(BaseModel):
    profile_id: str
    platform: str
    username: str
    profile_url: str
    full_name: str = ""
    biography: str = ""
    profile_pic_url: str | None = None
    follower_count: int | None = Field(default=None, ge=0)
    following_count: int | None = Field(default=None, ge=0)
    media_count: int | None = Field(default=None, ge=0)
    is_verified: bool | None = None
    category: str | None = None
    external_url: str | None = None
    source: str = "public_web"
    source_fields: dict[str, Any] = Field(default_factory=dict)
    first_collected_at: datetime | None = None
    last_collected_at: datetime | None = None


class InfluencerCrawlRequest(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=50)

    @field_validator("urls")
    @classmethod
    def normalize_urls(cls, urls: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in urls:
            parts = urlsplit(value.strip())
            if parts.scheme != "https" or not parts.hostname:
                raise ValueError("profile URLs must use public https URLs")
            if parts.username or parts.password:
                raise ValueError("profile URLs must not contain credentials")
            clean = urlunsplit(
                ("https", parts.netloc.lower(), parts.path or "/", parts.query, "")
            )
            if clean not in normalized:
                normalized.append(clean)
        return normalized


class CrawlItem(BaseModel):
    url: str
    status: str
    profile_id: str | None = None
    error_code: str | None = None


class InfluencerCrawlResult(BaseModel):
    requested: int
    collected: int
    failed: int
    items: list[CrawlItem]


class CrawlError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class InfluencerStore:
    def __init__(self, engine: AsyncEngine | Any):
        self.engine = engine

    async def ensure_schema(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(metadata.create_all)

    async def upsert_many(self, profiles: list[InfluencerProfile]) -> None:
        if not profiles:
            return

        collected_at = datetime.now(timezone.utc)
        values = [
            profile.model_dump(
                exclude={"first_collected_at", "last_collected_at"}
            )
            | {"last_collected_at": collected_at}
            for profile in profiles
        ]
        statement = pg_insert(influencer_profiles).values(values)
        update_columns = {
            column.name: getattr(statement.excluded, column.name)
            for column in influencer_profiles.columns
            if column.name not in {"profile_id", "first_collected_at"}
        }
        statement = statement.on_conflict_do_update(
            index_elements=[influencer_profiles.c.profile_id],
            set_=update_columns,
        )

        async with self.engine.begin() as connection:
            await connection.execute(statement)

    async def list_profiles(
        self,
        *,
        min_followers: int = 0,
        verified: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[InfluencerProfile]:
        statement = select(influencer_profiles)
        if min_followers > 0:
            statement = statement.where(
                influencer_profiles.c.follower_count >= min_followers
            )
        if verified is not None:
            statement = statement.where(
                influencer_profiles.c.is_verified == verified
            )
        statement = (
            statement.order_by(
                influencer_profiles.c.follower_count.desc().nullslast(),
                influencer_profiles.c.full_name,
            )
            .limit(limit)
            .offset(offset)
        )

        async with self.engine.connect() as connection:
            rows = (await connection.execute(statement)).mappings().all()
        return [InfluencerProfile.model_validate(dict(row)) for row in rows]


class InfluencerCrawlerService:
    def __init__(self, crawler: Any, store: InfluencerStore | Any):
        self.crawler = crawler
        self.store = store

    async def crawl(self, urls: list[str]) -> InfluencerCrawlResult:
        # Check the database before making any external requests.
        await self.store.ensure_schema()

        profiles: list[InfluencerProfile] = []
        items: list[CrawlItem] = []
        for url in urls:
            try:
                profile = await self.crawler.get_profile(url)
                profiles.append(profile)
                items.append(
                    CrawlItem(
                        url=url,
                        status="collected",
                        profile_id=profile.profile_id,
                    )
                )
            except CrawlError as exc:
                items.append(
                    CrawlItem(url=url, status="failed", error_code=exc.code)
                )

        await self.store.upsert_many(profiles)
        return InfluencerCrawlResult(
            requested=len(urls),
            collected=len(profiles),
            failed=len(urls) - len(profiles),
            items=items,
        )
