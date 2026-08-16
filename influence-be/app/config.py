import os
import ssl
from dataclasses import dataclass

from sqlalchemy import URL


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "influence"
    db_user: str = "influence"
    db_password: str = "influence"
    db_ssl: str = "disable"
    db_ssl_ca_file: str | None = None
    redis_url: str | None = None
    cors_origins: tuple[str, ...] = ("http://localhost:3001",)
    hikerapi_access_key: str | None = None
    hikerapi_base_url: str = "https://api.hikerapi.com"
    collector_admin_key: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        redis_url = os.getenv("REDIS_URL")
        hikerapi_access_key = os.getenv("HIKERAPI_ACCESS_KEY")
        collector_admin_key = os.getenv("COLLECTOR_ADMIN_KEY")
        return cls(
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
            hikerapi_access_key=(
                hikerapi_access_key if hikerapi_access_key else None
            ),
            hikerapi_base_url=os.getenv(
                "HIKERAPI_BASE_URL", "https://api.hikerapi.com"
            ),
            collector_admin_key=(
                collector_admin_key if collector_admin_key else None
            ),
        )

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
