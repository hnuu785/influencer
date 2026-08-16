from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any


CATALOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "AI_Instagram_Influencers_58_2026-08-16.json"
)

COUNTRY_ALIASES = {
    "Brazil": "브라질",
    "Canada": "캐나다",
    "Finland": "핀란드",
    "Germany": "독일",
    "India": "인도",
    "Japan": "일본",
    "Mexico": "멕시코",
    "Morocco": "모로코",
    "Netherlands": "네덜란드",
    "Portugal": "포르투갈",
    "Spain": "스페인",
    "Turkey": "튀르키예 터키",
    "United Kingdom": "영국",
    "United States": "미국",
}

CATEGORY_ALIASES = {
    "art": "예술",
    "beauty": "뷰티 미용",
    "comedy": "코미디",
    "digital art": "디지털 아트",
    "entertainment": "엔터테인먼트",
    "fashion": "패션",
    "fitness": "피트니스",
    "gaming": "게임",
    "lifestyle": "라이프스타일",
    "music": "음악",
    "retail": "리테일 유통",
    "sports": "스포츠",
    "technology": "기술 테크",
    "travel": "여행",
}

PROFILE_TYPE_ALIASES = {
    "ai_character": "AI 캐릭터",
    "animated_virtual_character": "애니메이션 가상 캐릭터",
    "brand_virtual_mascot": "브랜드 가상 마스코트",
    "cgi_virtual_influencer": "CGI 가상 인플루언서",
    "generative_ai_character": "생성형 AI 캐릭터",
    "realtime_virtual_avatar": "실시간 가상 아바타",
}


def _observed_date(value: str) -> tuple[date | None, str]:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return date.fromisoformat(value), "day"
    if re.fullmatch(r"\d{4}-\d{2}", value):
        year, month = (int(part) for part in value.split("-"))
        return date(year, month, 1), "month"
    if re.fullmatch(r"\d{4}", value):
        return date(int(value), 1, 1), "year"
    return None, "unspecified"


def _split_values(value: str | None, separator: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(separator) if part.strip()]


def _retrieval_text(record: dict[str, Any], categories: list[str], countries: list[str]) -> str:
    category_aliases = [CATEGORY_ALIASES.get(item, "") for item in categories]
    country_aliases = [COUNTRY_ALIASES.get(item, "") for item in countries]
    return " ".join(
        part
        for part in [
            record["full_name"],
            f"@{record['username']}",
            record["platform"],
            record["profile_type"],
            PROFILE_TYPE_ALIASES.get(record["profile_type"], ""),
            *categories,
            *category_aliases,
            *countries,
            *country_aliases,
            record.get("creator_or_manager") or "",
        ]
        if part
    )


def normalize_catalog_record(record: dict[str, Any], dataset_version: str) -> dict[str, Any]:
    required = {
        "rank_by_follower_snapshot",
        "platform",
        "username",
        "profile_url",
        "full_name",
        "follower_count",
        "category",
        "profile_type",
        "observed_at",
        "confidence",
        "account_status",
        "source_url",
    }
    missing = sorted(required - record.keys())
    if missing:
        raise ValueError(f"Influencer record is missing fields: {', '.join(missing)}")
    categories = _split_values(record["category"], ",")
    countries = _split_values(record.get("country"), "/")
    observed_date, observed_precision = _observed_date(record["observed_at"])
    return {
        "dataset_version": dataset_version,
        "rank_by_follower_snapshot": record["rank_by_follower_snapshot"],
        "platform": record["platform"].lower(),
        "username": record["username"].lower(),
        "profile_url": record["profile_url"],
        "full_name": record["full_name"],
        "follower_count": record["follower_count"],
        "following_count": record.get("following_count"),
        "media_count": record.get("media_count"),
        "engagement_rate_percent": record.get("engagement_rate_percent"),
        "categories": categories,
        "profile_type": record["profile_type"],
        "countries": countries,
        "creator_or_manager": record.get("creator_or_manager"),
        "observed_at": record["observed_at"],
        "observed_date": observed_date,
        "observed_precision": observed_precision,
        "confidence": record["confidence"],
        "account_status": record["account_status"],
        "source_url": record["source_url"],
        "secondary_source_urls": record.get("secondary_source_urls", []),
        "source_rank": record.get("source_rank"),
        "follower_growth_3mo_percent": record.get(
            "follower_growth_3mo_percent"
        ),
        "retrieval_text": _retrieval_text(record, categories, countries),
        "rights_basis": "source_terms_unverified",
    }


def load_catalog(path: Path = CATALOG_PATH) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    dataset_version = payload.get("dataset_version")
    records = payload.get("records")
    if not dataset_version or not isinstance(records, list):
        raise ValueError("Influencer catalog metadata is invalid")
    expected_count = payload.get("scope", {}).get("record_count")
    if expected_count != len(records):
        raise ValueError("Influencer catalog record count does not match metadata")
    normalized = [
        normalize_catalog_record(record, dataset_version) for record in records
    ]
    keys = [(item["platform"], item["username"]) for item in normalized]
    if len(set(keys)) != len(keys):
        raise ValueError("Influencer catalog contains duplicate accounts")
    return normalized


def keyword_score(retrieval_text: str, query: str) -> int:
    terms = re.findall(r"[\w.@-]+", query.casefold())
    haystack = retrieval_text.casefold()
    return sum(2 if term.startswith("@") else 1 for term in terms if term in haystack)


def _matches_value(value: str, query: str, aliases: dict[str, str]) -> bool:
    normalized = query.strip().casefold()
    candidates = {value.casefold(), *aliases.get(value, "").casefold().split()}
    return normalized in candidates


def matches_category(categories: list[str], query: str) -> bool:
    return any(_matches_value(value, query, CATEGORY_ALIASES) for value in categories)


def matches_country(countries: list[str], query: str) -> bool:
    return any(_matches_value(value, query, COUNTRY_ALIASES) for value in countries)
