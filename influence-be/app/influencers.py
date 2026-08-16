import re
from datetime import datetime, timezone
from typing import Any

import httpx2
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


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._]{1,30}$")
metadata = MetaData()

influencers = Table(
    "influencers",
    metadata,
    Column("instagram_user_id", String(32), primary_key=True),
    Column("username", String(30), nullable=False, index=True),
    Column("full_name", String(255), nullable=False, server_default=""),
    Column("biography", Text, nullable=False, server_default=""),
    Column("profile_pic_url", Text),
    Column("follower_count", BigInteger, nullable=False, server_default="0", index=True),
    Column("following_count", BigInteger, nullable=False, server_default="0"),
    Column("media_count", BigInteger, nullable=False, server_default="0"),
    Column("is_private", Boolean, nullable=False, server_default="false"),
    Column("is_verified", Boolean, nullable=False, server_default="false", index=True),
    Column("is_business", Boolean, nullable=False, server_default="false"),
    Column("category", String(255)),
    Column("external_url", Text),
    Column("source", String(32), nullable=False, server_default="hikerapi"),
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
    instagram_user_id: str
    username: str
    full_name: str = ""
    biography: str = ""
    profile_pic_url: str | None = None
    follower_count: int = Field(default=0, ge=0)
    following_count: int = Field(default=0, ge=0)
    media_count: int = Field(default=0, ge=0)
    is_private: bool = False
    is_verified: bool = False
    is_business: bool = False
    category: str | None = None
    external_url: str | None = None
    source: str = "hikerapi"
    source_fields: dict[str, str] = Field(default_factory=dict)
    first_collected_at: datetime | None = None
    last_collected_at: datetime | None = None

    @classmethod
    def from_hiker(cls, payload: dict[str, Any]) -> "InfluencerProfile":
        data = payload.get("data", payload)
        if not isinstance(data, dict):
            raise HikerAPIError("invalid_response", "HikerAPI returned an invalid profile")

        user_id = data.get("pk") or data.get("id")
        username = str(data.get("username") or "").strip().lstrip("@")
        if not user_id or not USERNAME_PATTERN.fullmatch(username):
            raise HikerAPIError("invalid_response", "HikerAPI profile is missing id or username")

        category = data.get("category") or data.get("business_category_name")
        return cls(
            instagram_user_id=str(user_id),
            username=username,
            full_name=str(data.get("full_name") or ""),
            biography=str(data.get("biography") or ""),
            profile_pic_url=data.get("profile_pic_url_hd") or data.get("profile_pic_url"),
            follower_count=int(data.get("follower_count") or 0),
            following_count=int(data.get("following_count") or 0),
            media_count=int(data.get("media_count") or 0),
            is_private=bool(data.get("is_private", False)),
            is_verified=bool(data.get("is_verified", False)),
            is_business=bool(data.get("is_business", False)),
            category=str(category) if category else None,
            external_url=data.get("external_url"),
            source_fields={
                "account_type": str(data.get("account_type") or ""),
                "category_name": str(data.get("category_name") or ""),
            },
        )


class InfluencerCollectionRequest(BaseModel):
    usernames: list[str] = Field(min_length=1, max_length=50)

    @field_validator("usernames")
    @classmethod
    def normalize_usernames(cls, usernames: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in usernames:
            username = value.strip().lstrip("@").lower()
            if not USERNAME_PATTERN.fullmatch(username):
                raise ValueError(f"invalid Instagram username: {value}")
            if username not in normalized:
                normalized.append(username)
        return normalized


class CollectionItem(BaseModel):
    username: str
    status: str
    instagram_user_id: str | None = None
    error_code: str | None = None


class InfluencerCollectionResult(BaseModel):
    requested: int
    collected: int
    failed: int
    items: list[CollectionItem]


class HikerAPIError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class HikerAPIClient:
    def __init__(
        self,
        access_key: str,
        *,
        base_url: str = "https://api.hikerapi.com",
        timeout_seconds: float = 20.0,
        transport: Any | None = None,
    ):
        self.access_key = access_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def get_profile(self, username: str) -> InfluencerProfile:
        try:
            async with httpx2.AsyncClient(
                base_url=self.base_url,
                headers={"x-access-key": self.access_key},
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.get(
                    "/v2/user/by/username",
                    params={"username": username, "safe_int": "true"},
                )
                response.raise_for_status()
        except httpx2.TimeoutException as exc:
            raise HikerAPIError("timeout", "HikerAPI request timed out") from exc
        except httpx2.HTTPStatusError as exc:
            status_code = exc.response.status_code
            code = {
                401: "authentication_failed",
                403: "authentication_failed",
                404: "not_found",
                429: "rate_limited",
            }.get(status_code, "upstream_error")
            raise HikerAPIError(code, f"HikerAPI returned HTTP {status_code}") from exc
        except httpx2.RequestError as exc:
            raise HikerAPIError("network_error", "HikerAPI request failed") from exc

        try:
            return InfluencerProfile.from_hiker(response.json())
        except ValueError as exc:
            raise HikerAPIError("invalid_response", "HikerAPI returned invalid JSON") from exc


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
        statement = pg_insert(influencers).values(values)
        update_columns = {
            column.name: getattr(statement.excluded, column.name)
            for column in influencers.columns
            if column.name not in {"instagram_user_id", "first_collected_at"}
        }
        statement = statement.on_conflict_do_update(
            index_elements=[influencers.c.instagram_user_id],
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
        statement = (
            select(influencers)
            .where(influencers.c.follower_count >= min_followers)
            .order_by(influencers.c.follower_count.desc())
            .limit(limit)
            .offset(offset)
        )
        if verified is not None:
            statement = statement.where(influencers.c.is_verified == verified)

        async with self.engine.connect() as connection:
            rows = (await connection.execute(statement)).mappings().all()
        return [InfluencerProfile.model_validate(dict(row)) for row in rows]


class InfluencerCollector:
    def __init__(self, client: HikerAPIClient | Any, store: InfluencerStore | Any):
        self.client = client
        self.store = store

    async def collect(self, usernames: list[str]) -> InfluencerCollectionResult:
        # Verify database connectivity before spending paid HikerAPI requests.
        await self.store.ensure_schema()

        profiles: list[InfluencerProfile] = []
        items: list[CollectionItem] = []
        for username in usernames:
            try:
                profile = await self.client.get_profile(username)
                profiles.append(profile)
                items.append(
                    CollectionItem(
                        username=username,
                        status="collected",
                        instagram_user_id=profile.instagram_user_id,
                    )
                )
            except HikerAPIError as exc:
                items.append(
                    CollectionItem(
                        username=username,
                        status="failed",
                        error_code=exc.code,
                    )
                )

        await self.store.upsert_many(profiles)
        return InfluencerCollectionResult(
            requested=len(usernames),
            collected=len(profiles),
            failed=len(usernames) - len(profiles),
            items=items,
        )
