import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://influence:influence@localhost:5432/influence",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = create_async_engine(DATABASE_URL)
    app.state.redis = Redis.from_url(REDIS_URL)
    yield
    await app.state.redis.aclose()
    await app.state.db.dispose()


app = FastAPI(title="Influence API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Influence API"}


@app.get("/health")
async def health() -> JSONResponse:
    db: AsyncEngine = app.state.db
    redis: Redis = app.state.redis
    services = {"postgres": "ok", "redis": "ok"}

    try:
        async with db.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        services["postgres"] = "unavailable"

    try:
        await redis.ping()
    except Exception:
        services["redis"] = "unavailable"

    healthy = all(status == "ok" for status in services.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "degraded", "services": services},
    )

