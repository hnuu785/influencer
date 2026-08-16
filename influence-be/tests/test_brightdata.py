import asyncio
import json

import httpx2
import pytest
from fastapi.testclient import TestClient

from app.brightdata import BrightDataProfileProvider
from app.config import Settings
from app.influencers import CrawlError
from app.main import create_app


def test_brightdata_provider_maps_profile_and_uses_bearer_token():
    async def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "POST"
        assert request.url.path == "/datasets/v3/scrape"
        assert request.url.params["dataset_id"] == "profile-dataset"
        assert request.url.params["format"] == "json"
        assert request.headers["authorization"] == "Bearer secret-token"
        assert json.loads(request.content) == [
            {"url": "https://www.instagram.com/creator/"}
        ]
        return httpx2.Response(
            200,
            json=[
                {
                    "user_name": "creator",
                    "full_name": "Creator Name",
                    "biography": "Contact creator@example.com or +82 10-1234-5678",
                    "followers": 12500,
                    "following": 230,
                    "posts_count": 84,
                    "is_verified": True,
                    "profile_pic_url": "https://cdn.example/profile.jpg",
                    "category_name": "Digital creator",
                    "external_url": "https://creator.example",
                }
            ],
        )

    provider = BrightDataProfileProvider(
        "secret-token",
        dataset_id="profile-dataset",
        transport=httpx2.MockTransport(handler),
    )
    profile = asyncio.run(
        provider.get_profile(
            "https://www.instagram.com/creator/?igsh=tracking&utm_source=qr"
        )
    )

    assert profile.username == "creator"
    assert profile.profile_url == "https://www.instagram.com/creator/"
    assert profile.follower_count == 12500
    assert profile.following_count == 230
    assert profile.media_count == 84
    assert profile.is_verified is True
    assert profile.source == "brightdata"
    assert "creator@example.com" not in profile.biography
    assert "10-1234-5678" not in profile.biography


@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    [
        (401, "authentication_failed"),
        (402, "payment_required"),
        (429, "rate_limited"),
        (500, "upstream_error"),
    ],
)
def test_brightdata_provider_maps_upstream_errors(status_code, expected_code):
    async def handler(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(status_code)

    provider = BrightDataProfileProvider(
        "secret-token",
        dataset_id="profile-dataset",
        transport=httpx2.MockTransport(handler),
    )

    with pytest.raises(CrawlError) as error:
        asyncio.run(
            provider.get_profile("https://www.instagram.com/creator/")
        )

    assert error.value.code == expected_code


def test_brightdata_provider_rejects_response_without_username():
    async def handler(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"data": {"followers": 100}})

    provider = BrightDataProfileProvider(
        "secret-token",
        dataset_id="profile-dataset",
        transport=httpx2.MockTransport(handler),
    )

    with pytest.raises(CrawlError) as error:
        asyncio.run(
            provider.get_profile("https://www.instagram.com/creator/")
        )

    assert error.value.code == "profile_not_detected"


def test_brightdata_provider_requires_token_before_endpoint_call():
    app = create_app(
        Settings(
            collector_admin_key="collector-secret",
            influencer_provider="brightdata",
        ),
        engine=object(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/admin/influencers/crawl",
            headers={"X-Collector-Key": "collector-secret"},
            json={"urls": ["https://www.instagram.com/creator/"]},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "BRIGHTDATA_API_TOKEN is not configured"


def test_unknown_influencer_provider_is_rejected_at_startup():
    with pytest.raises(ValueError, match="INFLUENCER_PROVIDER"):
        create_app(Settings(influencer_provider="unknown"), engine=object())
