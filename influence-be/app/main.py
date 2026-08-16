import secrets
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import Settings
from app.influencers import (
    HikerAPIClient,
    InfluencerCollectionRequest,
    InfluencerCollectionResult,
    InfluencerCollector,
    InfluencerProfile,
    InfluencerStore,
)


def create_app(
    settings: Settings | None = None,
    *,
    engine: AsyncEngine | Any | None = None,
    redis_client: Redis | Any | None = None,
    collector_service: InfluencerCollector | Any | None = None,
    influencer_store: InfluencerStore | Any | None = None,
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

    application = FastAPI(title="Influence API", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(app_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/")
    async def root() -> dict[str, str]:
        return {"message": "Influence API"}

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    def get_influencer_store() -> InfluencerStore | Any:
        return influencer_store or InfluencerStore(application.state.db)

    @application.post(
        "/api/admin/influencers/collect",
        response_model=InfluencerCollectionResult,
    )
    async def collect_influencers(
        request: InfluencerCollectionRequest,
        collector_key: str | None = Header(default=None, alias="X-Collector-Key"),
    ) -> InfluencerCollectionResult:
        if not app_settings.collector_admin_key:
            raise HTTPException(
                status_code=503,
                detail="COLLECTOR_ADMIN_KEY is not configured",
            )
        if not collector_key or not secrets.compare_digest(
            collector_key, app_settings.collector_admin_key
        ):
            raise HTTPException(status_code=401, detail="invalid collector key")

        service = collector_service
        if service is None:
            if not app_settings.hikerapi_access_key:
                raise HTTPException(
                    status_code=503,
                    detail="HIKERAPI_ACCESS_KEY is not configured",
                )
            service = InfluencerCollector(
                HikerAPIClient(
                    app_settings.hikerapi_access_key,
                    base_url=app_settings.hikerapi_base_url,
                ),
                get_influencer_store(),
            )

        try:
            return await service.collect(request.usernames)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="influencer collection database is unavailable",
            ) from exc

    @application.get("/api/influencers", response_model=list[InfluencerProfile])
    async def list_influencers(
        min_followers: int = Query(default=0, ge=0),
        verified: bool | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> list[InfluencerProfile]:
        store = get_influencer_store()
        try:
            await store.ensure_schema()
            return await store.list_profiles(
                min_followers=min_followers,
                verified=verified,
                limit=limit,
                offset=offset,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="influencer database is unavailable",
            ) from exc

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
