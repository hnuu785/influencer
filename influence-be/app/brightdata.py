import hashlib
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx2

from app.influencers import CrawlError, InfluencerProfile


EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d .()-]{7,}\d)(?!\w)")


def _canonical_profile_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", "", "")
    )


def _first_value(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value is not None and value != "":
            return value
    return None


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return max(0, int(str(value).replace(",", "")))
    except ValueError:
        return None


def _optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return None


def _redact_contact_details(value: str) -> str:
    redacted = EMAIL_PATTERN.sub("[redacted email]", value)
    return PHONE_PATTERN.sub("[redacted phone]", redacted).strip()


def _profile_record(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list):
        return payload[0] if payload and isinstance(payload[0], dict) else {}
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data")
    if isinstance(data, list):
        return data[0] if data and isinstance(data[0], dict) else {}
    if isinstance(data, dict):
        return data
    return payload


class BrightDataProfileProvider:
    def __init__(
        self,
        api_token: str,
        *,
        dataset_id: str,
        base_url: str = "https://api.brightdata.com",
        timeout_seconds: float = 60.0,
        max_response_bytes: int = 5_000_000,
        transport: Any | None = None,
    ) -> None:
        self.api_token = api_token
        self.dataset_id = dataset_id
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.transport = transport

    async def get_profile(self, url: str) -> InfluencerProfile:
        canonical_url = _canonical_profile_url(url)
        try:
            async with httpx2.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Accept": "application/json",
                },
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    "/datasets/v3/scrape",
                    params={"dataset_id": self.dataset_id, "format": "json"},
                    json=[{"url": canonical_url}],
                )
        except httpx2.TimeoutException as exc:
            raise CrawlError("timeout", "Bright Data request timed out") from exc
        except httpx2.RequestError as exc:
            raise CrawlError("network_error", "Bright Data request failed") from exc

        if len(response.content) > self.max_response_bytes:
            raise CrawlError("response_too_large", "Bright Data response is too large")
        if response.status_code in {401, 403}:
            raise CrawlError(
                "authentication_failed", "Bright Data rejected the API token"
            )
        if response.status_code == 402:
            raise CrawlError("payment_required", "Bright Data account needs credit")
        if response.status_code == 429:
            raise CrawlError("rate_limited", "Bright Data rate limit reached")
        if response.status_code >= 400:
            raise CrawlError(
                "upstream_error",
                f"Bright Data returned HTTP {response.status_code}",
            )

        try:
            record = _profile_record(response.json())
        except ValueError as exc:
            raise CrawlError(
                "invalid_response", "Bright Data returned invalid JSON"
            ) from exc
        username = _first_value(record, "user_name", "username", "account")
        if not isinstance(username, str) or not username.strip():
            raise CrawlError(
                "profile_not_detected", "Bright Data response has no username"
            )

        biography = str(_first_value(record, "biography", "bio") or "")
        return InfluencerProfile(
            profile_id=hashlib.sha256(canonical_url.encode()).hexdigest(),
            platform="instagram",
            username=username.strip().lstrip("@")[:255],
            profile_url=canonical_url,
            full_name=str(_first_value(record, "full_name", "name") or "")[:255],
            biography=_redact_contact_details(biography),
            profile_pic_url=_first_value(
                record,
                "profile_pic_url",
                "profile_image_link",
                "profile_image_url",
            ),
            follower_count=_optional_int(
                _first_value(record, "followers", "followers_count")
            ),
            following_count=_optional_int(
                _first_value(record, "following", "following_count")
            ),
            media_count=_optional_int(
                _first_value(record, "posts_count", "media_count", "posts")
            ),
            is_verified=_optional_bool(
                _first_value(record, "is_verified", "verified")
            ),
            category=(
                str(_first_value(record, "category", "category_name"))[:255]
                if _first_value(record, "category", "category_name")
                else None
            ),
            external_url=_first_value(record, "external_url", "bio_url"),
            source="brightdata",
            source_fields={"available_fields": sorted(record.keys())},
        )
