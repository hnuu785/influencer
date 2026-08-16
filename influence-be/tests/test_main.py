import ssl

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class FakeConnection:
    async def execute(self, _statement):
        return None


class FakeConnectionContext:
    def __init__(self, *, fail: bool = False):
        self.fail = fail

    async def __aenter__(self):
        if self.fail:
            raise RuntimeError("database unavailable")
        return FakeConnection()

    async def __aexit__(self, _exc_type, _exc, _traceback):
        return None


class FakeEngine:
    def __init__(self, *, fail: bool = False):
        self.fail = fail

    def connect(self):
        return FakeConnectionContext(fail=self.fail)


class FakeRedis:
    def __init__(self, *, fail: bool = False):
        self.fail = fail

    async def ping(self):
        if self.fail:
            raise RuntimeError("redis unavailable")
        return True


def make_client(*, db_fails: bool = False, redis=None) -> TestClient:
    settings = Settings(cors_origins=("https://main.example.amplifyapp.com",))
    app = create_app(
        settings,
        engine=FakeEngine(fail=db_fails),
        redis_client=redis,
    )
    return TestClient(app)


def test_health_is_liveness_only():
    with make_client(db_fails=True) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_succeeds_when_database_is_available_and_redis_is_not_configured():
    with make_client() as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "services": {"postgres": "ok", "redis": "not_configured"},
    }


def test_ready_fails_when_database_is_unavailable():
    with make_client(db_fails=True) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["services"]["postgres"] == "unavailable"


def test_ready_fails_when_configured_redis_is_unavailable():
    with make_client(redis=FakeRedis(fail=True)) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["services"]["redis"] == "unavailable"


def test_cors_allows_configured_origin():
    with make_client() as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "https://main.example.amplifyapp.com",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://main.example.amplifyapp.com"
    )


def test_cors_does_not_allow_unknown_origin():
    with make_client() as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "https://attacker.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert "access-control-allow-origin" not in response.headers


def test_story_card_uses_only_submitted_source_content():
    payload = {
        "event": "오늘 회의에서 큰 기능보다 한 가지 행동을 먼저 검증하기로 했다.",
        "unexpected": "아이디어가 많아도 작은 실험에 더 빠르게 합의했다.",
        "lesson": "좋은 시작은 한 가지 가설을 끝까지 검증하는 데서 나온다.",
        "audience": "처음 제품을 만드는 사람",
        "channels": ["LinkedIn", "X", "Instagram"],
    }

    with make_client() as client:
        response = client.post("/api/story-cards", json=payload)

    assert response.status_code == 200
    story = response.json()
    assert story["status"] == "STORY_MINED"
    assert story["visibility"] == "PRIVATE"
    assert story["source_refs"][0]["excerpt"] == payload["event"]
    assert [draft["channel"] for draft in story["drafts"]] == [
        "LinkedIn",
        "X",
        "Instagram",
    ]
    assert all(draft["status"] == "NEEDS_REVIEW" for draft in story["drafts"])


def test_story_card_rejects_too_short_source():
    with make_client() as client:
        response = client.post(
            "/api/story-cards",
            json={"event": "짧음", "lesson": "배움"},
        )

    assert response.status_code == 422


def test_database_ssl_require_enables_encryption_context():
    connect_args = Settings(db_ssl="require").database_connect_args()

    assert connect_args["ssl"].verify_mode == ssl.CERT_NONE
    assert connect_args["ssl"].check_hostname is False


def test_database_ssl_rejects_unknown_mode():
    with pytest.raises(ValueError, match="DB_SSL"):
        Settings(db_ssl="sometimes").database_connect_args()
