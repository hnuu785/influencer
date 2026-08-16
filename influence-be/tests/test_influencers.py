import asyncio
import gzip

import httpx2
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.influencers import (
    CrawlError,
    CrawlItem,
    InfluencerCrawlerService,
    InfluencerCrawlRequest,
    InfluencerCrawlResult,
    InfluencerProfile,
)
from app.main import create_app
from app.web_crawler import PublicProfileCrawler, parse_profile_html


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


class FakeCrawlerService:
    def __init__(self):
        self.received: list[str] = []

    async def crawl(self, urls: list[str]) -> InfluencerCrawlResult:
        self.received = urls
        return InfluencerCrawlResult(
            requested=len(urls),
            collected=len(urls),
            failed=0,
            items=[
                CrawlItem(
                    url=url,
                    status="collected",
                    profile_id=str(index),
                )
                for index, url in enumerate(urls, start=1)
            ],
        )


class FakeStore:
    def __init__(self):
        self.filters = None
        self.schema_ready = False
        self.saved: list[InfluencerProfile] = []

    async def ensure_schema(self):
        self.schema_ready = True

    async def upsert_many(self, profiles):
        self.saved = profiles

    async def list_profiles(self, **filters):
        self.filters = filters
        return [
            InfluencerProfile(
                profile_id="42",
                platform="website",
                username="creator",
                profile_url="https://creator.example/",
                follower_count=12_000,
                is_verified=True,
            )
        ]


class FakeProfileCrawler:
    async def get_profile(self, url: str) -> InfluencerProfile:
        if url.endswith("missing/"):
            raise CrawlError("not_found", "missing")
        return InfluencerProfile(
            profile_id="profile-1",
            platform="website",
            username="creator",
            profile_url=url,
        )


async def public_resolver(_hostname: str) -> list[str]:
    return ["93.184.216.34"]


def make_client(*, crawler=None, store=None) -> TestClient:
    settings = Settings(collector_admin_key="collector-secret")
    app = create_app(
        settings,
        engine=FakeEngine(),
        crawler_service=crawler,
        influencer_store=store,
    )
    return TestClient(app)


def test_public_profile_mapping_uses_json_ld_and_redacts_contact_details():
    html = """
    <html><head>
      <meta property="og:title" content="Fallback Creator">
      <meta property="og:description" content="12.5K Followers, 230 Following, 84 Posts">
      <meta property="og:image" content="https://cdn.example/creator.jpg">
      <script type="application/ld+json">
        {
          "@type": "Person",
          "name": "Creator Name",
          "alternateName": "@creator",
          "description": "Builder creator@example.com +82 10-1234-5678",
          "jobTitle": "Video creator",
          "sameAs": ["https://youtube.com/@creator"]
        }
      </script>
    </head></html>
    """

    profile = parse_profile_html(html, "https://creator.example/profile/")

    assert profile.username == "creator"
    assert profile.full_name == "Creator Name"
    assert profile.follower_count == 12_500
    assert profile.following_count == 230
    assert profile.media_count == 84
    assert profile.category == "Video creator"
    assert profile.external_url == "https://youtube.com/@creator"
    assert "creator@example.com" not in profile.biography
    assert "10-1234-5678" not in profile.biography


def test_crawl_request_normalizes_and_deduplicates_https_urls():
    request = InfluencerCrawlRequest(
        urls=[
            "https://Creator.Example/profile#about",
            "https://creator.example/profile",
            "https://second.example/creator",
        ]
    )

    assert request.urls == [
        "https://creator.example/profile",
        "https://second.example/creator",
    ]


def test_crawl_request_rejects_non_https_urls():
    with pytest.raises(ValueError, match="https"):
        InfluencerCrawlRequest(urls=["http://creator.example/profile"])


def test_public_crawler_obeys_robots_and_parses_allowed_page():
    requests: list[str] = []

    async def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request.url.path)
        assert request.headers["user-agent"] == "InfluenceCrawler/1.0"
        if request.url.path == "/robots.txt":
            return httpx2.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx2.Response(
            200,
            headers={"content-type": "text/html"},
            text=(
                '<meta property="og:title" content="Creator">'
                '<meta property="og:description" content="1.2M Followers">'
            ),
        )

    crawler = PublicProfileCrawler(
        user_agent="InfluenceCrawler/1.0",
        request_delay_seconds=0,
        transport=httpx2.MockTransport(handler),
        resolver=public_resolver,
    )
    profile = asyncio.run(crawler.get_profile("https://creator.example/profile"))

    assert requests == ["/robots.txt", "/profile"]
    assert profile.follower_count == 1_200_000


def test_public_crawler_treats_missing_robots_file_as_no_rules():
    async def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/robots.txt":
            return httpx2.Response(404)
        return httpx2.Response(
            200,
            headers={"content-type": "text/html"},
            text='<meta property="og:title" content="Creator">',
        )

    crawler = PublicProfileCrawler(
        user_agent="InfluenceCrawler/1.0",
        request_delay_seconds=0,
        transport=httpx2.MockTransport(handler),
        resolver=public_resolver,
    )

    profile = asyncio.run(crawler.get_profile("https://creator.example/profile"))

    assert profile.full_name == "Creator"


def test_public_crawler_handles_compressed_html_without_double_decoding():
    async def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/robots.txt":
            return httpx2.Response(200, text="User-agent: *\nAllow: /\n")
        body = gzip.compress(
            b'<meta property="og:title" content="Compressed Creator">'
        )
        return httpx2.Response(
            200,
            headers={
                "content-type": "text/html",
                "content-encoding": "gzip",
            },
            content=body,
        )

    crawler = PublicProfileCrawler(
        user_agent="InfluenceCrawler/1.0",
        request_delay_seconds=0,
        transport=httpx2.MockTransport(handler),
        resolver=public_resolver,
    )

    profile = asyncio.run(crawler.get_profile("https://creator.example/profile"))

    assert profile.full_name == "Compressed Creator"


def test_public_crawler_stops_when_robots_disallows_profile():
    requests: list[str] = []

    async def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request.url.path)
        return httpx2.Response(200, text="User-agent: *\nDisallow: /\n")

    crawler = PublicProfileCrawler(
        user_agent="InfluenceCrawler/1.0",
        request_delay_seconds=0,
        transport=httpx2.MockTransport(handler),
        resolver=public_resolver,
    )

    with pytest.raises(CrawlError) as error:
        asyncio.run(crawler.get_profile("https://creator.example/profile"))

    assert error.value.code == "robots_denied"
    assert requests == ["/robots.txt"]


def test_public_crawler_rejects_oversized_page_before_reading_body():
    async def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/robots.txt":
            return httpx2.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx2.Response(
            200,
            headers={
                "content-type": "text/html",
                "content-length": "3000000",
            },
            text="small test body",
        )

    crawler = PublicProfileCrawler(
        user_agent="InfluenceCrawler/1.0",
        request_delay_seconds=0,
        transport=httpx2.MockTransport(handler),
        resolver=public_resolver,
    )

    with pytest.raises(CrawlError) as error:
        asyncio.run(crawler.get_profile("https://creator.example/profile"))

    assert error.value.code == "response_too_large"


def test_public_crawler_rejects_private_network_target():
    async def private_resolver(_hostname: str) -> list[str]:
        return ["127.0.0.1"]

    crawler = PublicProfileCrawler(
        user_agent="InfluenceCrawler/1.0",
        request_delay_seconds=0,
        resolver=private_resolver,
    )

    with pytest.raises(CrawlError) as error:
        asyncio.run(crawler.get_profile("https://internal.example/profile"))

    assert error.value.code == "private_address"


def test_crawler_service_saves_successes_and_reports_per_url_failures():
    store = FakeStore()
    service = InfluencerCrawlerService(FakeProfileCrawler(), store)
    result = asyncio.run(
        service.crawl(
            ["https://creator.example/", "https://creator.example/missing/"]
        )
    )

    assert result.collected == 1
    assert result.failed == 1
    assert result.items[1].error_code == "not_found"
    assert store.schema_ready is True
    assert len(store.saved) == 1


def test_crawl_endpoint_requires_admin_key():
    crawler = FakeCrawlerService()
    with make_client(crawler=crawler) as client:
        response = client.post(
            "/api/admin/influencers/crawl",
            json={"urls": ["https://creator.example/profile"]},
        )

    assert response.status_code == 401
    assert crawler.received == []


def test_crawl_endpoint_runs_injected_crawler():
    crawler = FakeCrawlerService()
    with make_client(crawler=crawler) as client:
        response = client.post(
            "/api/admin/influencers/crawl",
            headers={"X-Collector-Key": "collector-secret"},
            json={
                "urls": [
                    "https://Creator.Example/profile#about",
                    "https://creator.example/profile",
                ]
            },
        )

    assert response.status_code == 200
    assert response.json()["collected"] == 1
    assert crawler.received == ["https://creator.example/profile"]


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
