import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.ai import create_ai_provider
from app.api import router as api_router
from app.config import Settings
from app.database import cleanup_expired_data, initialize_database
from app.storage import MediaStorage


async def _retention_worker(
    session_factory: async_sessionmaker, storage: MediaStorage
) -> None:
    while True:
        try:
            await cleanup_expired_data(session_factory, storage)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Retention cleanup must not take the API down; the next run retries.
            pass
        await asyncio.sleep(6 * 60 * 60)

def create_app(
    settings: Settings | None = None,
    *,
    engine: AsyncEngine | Any | None = None,
    redis_client: Redis | Any | None = None,
    storage: MediaStorage | Any | None = None,
    initialize_schema: bool | None = None,
) -> FastAPI:
    app_settings = settings or Settings.from_env()
    should_initialize_schema = engine is None if initialize_schema is None else initialize_schema

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
        app.state.settings = app_settings
        app.state.storage = storage or MediaStorage(app_settings)
        app.state.session_factory = async_sessionmaker(
            app.state.db, expire_on_commit=False
        )
        app.state.ai_provider = create_ai_provider(app_settings)
        app_settings.storage_path.mkdir(parents=True, exist_ok=True)
        if should_initialize_schema:
            await initialize_database(app.state.db, app.state.session_factory)

        retention_task = (
            asyncio.create_task(
                _retention_worker(app.state.session_factory, app.state.storage)
            )
            if should_initialize_schema
            else None
        )

        yield

        if retention_task is not None:
            retention_task.cancel()
            try:
                await retention_task
            except asyncio.CancelledError:
                pass
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
    application.include_router(api_router)

    @application.get("/")
    async def root() -> dict[str, str]:
        return {"message": "Influence API"}

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
