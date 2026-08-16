import os
import ssl
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import URL


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    app_frontend_url: str = "http://localhost:3001"
    app_public_api_url: str = "http://localhost:8001"
    invite_code: str = "STORYLOG-BETA"
    session_secret: str = "local-development-secret-change-me"
    google_client_id: str | None = None
    google_client_secret: str | None = None
    openai_api_key: str | None = None
    openai_transcribe_model: str = "gpt-transcribe"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_generation_model: str = "gpt-5.6-terra"
    openai_review_model: str = "gpt-5.6-sol"
    storage_backend: str = "local"
    storage_dir: str = "/tmp/influence-assets"
    s3_bucket: str | None = None
    s3_region: str = "ap-northeast-2"
    s3_presign_ttl_seconds: int = 300
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "influence"
    db_user: str = "influence"
    db_password: str = "influence"
    db_ssl: str = "disable"
    db_ssl_ca_file: str | None = None
    redis_url: str | None = None
    cors_origins: tuple[str, ...] = ("http://localhost:3001",)

    @classmethod
    def from_env(cls) -> "Settings":
        redis_url = os.getenv("REDIS_URL")
        google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            app_frontend_url=os.getenv(
                "APP_FRONTEND_URL", "http://localhost:3001"
            ).rstrip("/"),
            app_public_api_url=os.getenv(
                "APP_PUBLIC_API_URL", "http://localhost:8001"
            ).rstrip("/"),
            invite_code=os.getenv("INVITE_CODE", "STORYLOG-BETA"),
            session_secret=os.getenv(
                "SESSION_SECRET", "local-development-secret-change-me"
            ),
            google_client_id=google_client_id if google_client_id else None,
            google_client_secret=(
                google_client_secret if google_client_secret else None
            ),
            openai_api_key=openai_api_key if openai_api_key else None,
            openai_transcribe_model=os.getenv(
                "OPENAI_TRANSCRIBE_MODEL", "gpt-transcribe"
            ),
            openai_embedding_model=os.getenv(
                "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
            ),
            openai_generation_model=os.getenv(
                "OPENAI_GENERATION_MODEL", "gpt-5.6-terra"
            ),
            openai_review_model=os.getenv(
                "OPENAI_REVIEW_MODEL", "gpt-5.6-sol"
            ),
            storage_backend=os.getenv("STORAGE_BACKEND", "local"),
            storage_dir=os.getenv("STORAGE_DIR", "/tmp/influence-assets"),
            s3_bucket=os.getenv("S3_BUCKET") or None,
            s3_region=os.getenv("S3_REGION", "ap-northeast-2"),
            s3_presign_ttl_seconds=int(
                os.getenv("S3_PRESIGN_TTL_SECONDS", "300")
            ),
            db_host=os.getenv("DB_HOST", "localhost"),
            db_port=int(os.getenv("DB_PORT", "5432")),
            db_name=os.getenv("DB_NAME", "influence"),
            db_user=os.getenv("DB_USER", "influence"),
            db_password=os.getenv("DB_PASSWORD", "influence"),
            db_ssl=os.getenv("DB_SSL", "disable"),
            db_ssl_ca_file=os.getenv("DB_SSL_CA_FILE"),
            redis_url=redis_url if redis_url else None,
            cors_origins=_split_csv(
                os.getenv("CORS_ORIGINS", "http://localhost:3001")
            ),
        )

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def google_redirect_uri(self) -> str:
        return f"{self.app_public_api_url}/api/auth/google/callback"

    @property
    def calendar_redirect_uri(self) -> str:
        return f"{self.app_public_api_url}/api/calendar/callback"

    @property
    def storage_path(self) -> Path:
        return Path(self.storage_dir)

    def validate_storage(self) -> None:
        if self.storage_backend not in {"local", "s3"}:
            raise ValueError("STORAGE_BACKEND must be one of: local, s3")
        if self.storage_backend == "s3" and not self.s3_bucket:
            raise ValueError("S3_BUCKET is required when STORAGE_BACKEND=s3")

    @property
    def database_url(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )

    def database_connect_args(self) -> dict[str, ssl.SSLContext]:
        if self.db_ssl == "disable":
            return {}

        if self.db_ssl == "require":
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            return {"ssl": context}

        if self.db_ssl == "verify-full":
            context = ssl.create_default_context(cafile=self.db_ssl_ca_file)
            return {"ssl": context}

        raise ValueError("DB_SSL must be one of: disable, require, verify-full")
