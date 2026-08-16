import asyncio

import httpx2
from fastapi.testclient import TestClient

from app.config import Settings
from app.influencers import (
    CollectionItem,
    HikerAPIClient,
    InfluencerCollectionRequest,
    InfluencerCollectionResult,
    InfluencerProfile,
)
from app.main import create_app


class FakeConnection:
    async def execute(self, _statement):
        return None


class FakeConnectionContext:
    async def __aenter__(self):
        return FakeConnection()

    async def __aexit__(self, _exc_type, _exc, _traceback):
        return None


class FakeEngine:
    def connect(self):
        return FakeConnectionContext()


class FakeCollector:
    def __init__(self):
        self.received: list[str] = []

    async def collect(self, usernames: list[str]) -> InfluencerCollectionResult:
        self.received = usernames
        return InfluencerCollectionResult(
            requested=len(usernames),
            collected=len(usernames),
            failed=0,
            items=[
                CollectionItem(
                    username=username,
                    status="collected",
                    instagram_user_id=str(index),
                )
                for index, username in enumerate(usernames, start=1)
            ],
        )


class FakeStore:
    def __init__(self):
        self.filters = None
        self.schema_ready = False

    async def ensure_schema(self):
        self.schema_ready = True

    async def list_profiles(self, **filters):
        self.filters = filters
        return [
            InfluencerProfile(
                instagram_user_id="42",
                username="creator",
                follower_count=12_000,
                is_verified=True,
            )
        ]


def make_client(*, collector=None, store=None) -> TestClient:
    settings = Settings(
        collector_admin_key="collector-secret",
        hikerapi_access_key="hiker-secret",
    )
    app = create_app(
        settings,
        engine=FakeEngine(),
        collector_service=collector,
        influencer_store=store,
    )
    return TestClient(app)


def test_hiker_profile_mapping_keeps_only_required_public_fields():
    payload = {
        "pk": "12345678901234567890",
        "username": "Creator.Name",
        "full_name": "Creator Name",
        "biography": "Public bio",
        "follower_count": 15000,
        "following_count": 230,
        "media_count": 84,
        "is_verified": True,
        "is_business": True,
        "business_category_name": "Digital creator",
        "public_email": "must-not-be-stored@example.com",
        "contact_phone_number": "010-0000-0000",
    }

    profile = InfluencerProfile.from_hiker(payload)

    assert profile.instagram_user_id == payload["pk"]
    assert profile.username == "Creator.Name"
    assert profile.follower_count == 15000
    assert profile.category == "Digital creator"
    assert "public_email" not in profile.model_dump()
    assert "contact_phone_number" not in profile.model_dump()


def test_hiker_client_uses_access_header_and_v2_profile_endpoint():
    async def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["x-access-key"] == "secret"
        assert request.url.path == "/v2/user/by/username"
        assert request.url.params["username"] == "creator"
        assert request.url.params["safe_int"] == "true"
        return httpx2.Response(
            200,
            json={"pk": "77", "username": "creator", "follower_count": 99},
        )

    client = HikerAPIClient("secret", transport=httpx2.MockTransport(handler))
    profile = asyncio.run(client.get_profile("creator"))

    assert profile.instagram_user_id == "77"
    assert profile.follower_count == 99


def test_collection_request_normalizes_and_deduplicates_usernames():
    request = InfluencerCollectionRequest(
        usernames=["@Creator.Name", "creator.name", "second_creator"]
    )

    assert request.usernames == ["creator.name", "second_creator"]


def test_collection_endpoint_requires_admin_key():
    collector = FakeCollector()
    with make_client(collector=collector) as client:
        response = client.post(
            "/api/admin/influencers/collect",
            json={"usernames": ["creator"]},
        )

    assert response.status_code == 401
    assert collector.received == []


def test_collection_endpoint_runs_injected_collector():
    collector = FakeCollector()
    with make_client(collector=collector) as client:
        response = client.post(
            "/api/admin/influencers/collect",
            headers={"X-Collector-Key": "collector-secret"},
            json={"usernames": ["@Creator", "second.creator"]},
        )

    assert response.status_code == 200
    assert response.json()["collected"] == 2
    assert collector.received == ["creator", "second.creator"]


def test_influencer_list_passes_filters_to_store():
    store = FakeStore()
    with make_client(store=store) as client:
        response = client.get(
            "/api/influencers?min_followers=10000&verified=true&limit=20&offset=5"
        )

    assert response.status_code == 200
    assert response.json()[0]["username"] == "creator"
    assert store.schema_ready is True
    assert store.filters == {
        "min_followers": 10000,
        "verified": True,
        "limit": 20,
        "offset": 5,
    }
