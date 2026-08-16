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
    collector_admin_key: str | None = None
    crawler_user_agent: str = "InfluenceCrawler/1.0"
    crawler_request_delay_seconds: float = 2.0
    crawler_allowed_domains: tuple[str, ...] = ()
    influencer_provider: str = "public_web"
    brightdata_api_token: str | None = None
    brightdata_profile_dataset_id: str = "gd_l1vikfch901nx3by4"
    brightdata_base_url: str = "https://api.brightdata.com"

    @classmethod
    def from_env(cls) -> "Settings":
        redis_url = os.getenv("REDIS_URL")
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
            collector_admin_key=(
                collector_admin_key if collector_admin_key else None
            ),
            crawler_user_agent=os.getenv(
                "CRAWLER_USER_AGENT", "InfluenceCrawler/1.0"
            ),
            crawler_request_delay_seconds=float(
                os.getenv("CRAWLER_REQUEST_DELAY_SECONDS", "2.0")
            ),
            crawler_allowed_domains=_split_csv(
                os.getenv("CRAWLER_ALLOWED_DOMAINS", "")
            ),
            influencer_provider=os.getenv(
                "INFLUENCER_PROVIDER", "public_web"
            ).lower(),
            brightdata_api_token=os.getenv("BRIGHTDATA_API_TOKEN") or None,
            brightdata_profile_dataset_id=os.getenv(
                "BRIGHTDATA_INSTAGRAM_PROFILE_DATASET_ID",
                "gd_l1vikfch901nx3by4",
            ),
            brightdata_base_url=os.getenv(
                "BRIGHTDATA_BASE_URL", "https://api.brightdata.com"
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
