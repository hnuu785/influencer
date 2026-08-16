import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import create_async_engine

from app.config import Settings
from app.influencers import InfluencerProfile, InfluencerStore


DATA_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "ai_virtual_influencers_2026-08-16.json"
)


def load_seed_profiles(path: Path = DATA_PATH) -> list[InfluencerProfile]:
    records: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    profiles: list[InfluencerProfile] = []
    for record in records:
        username = record["username"].strip().lstrip("@").lower()
        profile_url = f"https://www.instagram.com/{username}/"
        source_fields = {
            key: value
            for key, value in record.items()
            if key
            not in {
                "username",
                "full_name",
                "follower_count",
                "following_count",
                "media_count",
                "category",
            }
        }
        source_fields["metric_type"] = "third_party_public_snapshot"
        source_fields["direct_instagram_fetch"] = "not_attempted"
        profiles.append(
            InfluencerProfile(
                profile_id=hashlib.sha256(profile_url.encode()).hexdigest(),
                platform="instagram",
                username=username,
                profile_url=profile_url,
                full_name=record["full_name"],
                follower_count=record.get("follower_count"),
                following_count=record.get("following_count"),
                media_count=record.get("media_count"),
                category=record.get("category"),
                source="public_research",
                source_fields=source_fields,
            )
        )
    return profiles


async def import_seed_profiles() -> int:
    settings = Settings.from_env()
    engine = create_async_engine(
        settings.database_url,
        connect_args=settings.database_connect_args(),
        pool_pre_ping=True,
    )
    try:
        profiles = load_seed_profiles()
        store = InfluencerStore(engine)
        await store.ensure_schema()
        await store.upsert_many(profiles)
        return len(profiles)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    imported = asyncio.run(import_seed_profiles())
    print(f"Imported {imported} public-research AI virtual influencer profiles")
