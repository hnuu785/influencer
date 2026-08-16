import asyncio
import hashlib
import ipaddress
import json
import re
import socket
import time
import urllib.robotparser
from collections.abc import Awaitable, Callable, Iterator
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx2

from app.influencers import CrawlError, InfluencerProfile


EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d .()-]{7,}\d)(?!\w)")
COUNT_PATTERNS = {
    "follower_count": re.compile(
        r"([\d,.]+\s*[KMB]?)\s*(?:followers?|팔로워)", re.I
    ),
    "following_count": re.compile(
        r"([\d,.]+\s*[KMB]?)\s*(?:following|팔로잉)", re.I
    ),
    "media_count": re.compile(r"([\d,.]+\s*[KMB]?)\s*(?:posts?|게시물)", re.I),
}
KNOWN_PLATFORMS = {
    "instagram.com": "instagram",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "tiktok.com": "tiktok",
    "x.com": "x",
    "twitter.com": "x",
    "twitch.tv": "twitch",
}


class MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title_parts: list[str] = []
        self.json_ld_parts: list[str] = []
        self._in_title = False
        self._in_json_ld = False

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if tag == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            content = values.get("content", "").strip()
            if key and content and key not in self.meta:
                self.meta[key] = content
        elif tag == "title":
            self._in_title = True
        elif (
            tag == "script"
            and values.get("type", "").lower() == "application/ld+json"
        ):
            self._in_json_ld = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._in_json_ld:
            self.json_ld_parts.append("\n")
            self._in_json_ld = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._in_json_ld:
            self.json_ld_parts.append(data)

    @property
    def title(self) -> str:
        return " ".join(part.strip() for part in self.title_parts if part.strip())


def _iter_json_nodes(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_json_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_json_nodes(child)


def _json_ld_profile(raw: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    profiles: list[dict[str, Any]] = []
    index = 0
    while index < len(raw):
        while index < len(raw) and raw[index].isspace():
            index += 1
        if index >= len(raw):
            break
        try:
            value, end = decoder.raw_decode(raw, index)
        except json.JSONDecodeError:
            break
        index = end
        for node in _iter_json_nodes(value):
            node_type = node.get("@type")
            types = {node_type} if isinstance(node_type, str) else set(node_type or [])
            if types & {"Person", "Organization"}:
                profiles.append(node)
            elif "ProfilePage" in types and isinstance(node.get("mainEntity"), dict):
                profiles.append(node["mainEntity"])
    return profiles[0] if profiles else {}


def _image_url(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        candidate = value.get("url") or value.get("contentUrl")
        return candidate if isinstance(candidate, str) else None
    if isinstance(value, list):
        for item in value:
            candidate = _image_url(item)
            if candidate:
                return candidate
    return None


def _parse_count(value: str) -> int | None:
    compact = value.replace(",", "").replace(" ", "").upper()
    multiplier = 1
    if compact and compact[-1] in {"K", "M", "B"}:
        multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[
            compact[-1]
        ]
        compact = compact[:-1]
    try:
        return int(float(compact) * multiplier)
    except ValueError:
        return None


def _extract_counts(*texts: str) -> dict[str, int | None]:
    combined = " ".join(text for text in texts if text)
    counts: dict[str, int | None] = {}
    for field, pattern in COUNT_PATTERNS.items():
        match = pattern.search(combined)
        counts[field] = _parse_count(match.group(1)) if match else None
    return counts


def _redact_contact_details(value: str) -> str:
    redacted = EMAIL_PATTERN.sub("[redacted email]", value)
    return PHONE_PATTERN.sub("[redacted phone]", redacted).strip()


def _normalize_url(value: str) -> str:
    parts = urlsplit(value)
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", "", "")
    )


def _platform(hostname: str) -> str:
    host = hostname.lower().removeprefix("www.")
    for domain, platform in KNOWN_PLATFORMS.items():
        if host == domain or host.endswith(f".{domain}"):
            return platform
    return "website"


def _username(profile: dict[str, Any], parser: MetadataParser, url: str) -> str:
    candidate = profile.get("alternateName") or parser.meta.get("profile:username")
    if isinstance(candidate, str) and candidate.strip():
        return candidate.strip().lstrip("@").replace(" ", "_")[:255]
    path_parts = [part for part in urlsplit(url).path.split("/") if part]
    if path_parts:
        return path_parts[-1][:255]
    return (urlsplit(url).hostname or "unknown").removeprefix("www.")[:255]


def parse_profile_html(html: str, source_url: str) -> InfluencerProfile:
    parser = MetadataParser()
    parser.feed(html)
    profile = _json_ld_profile("".join(parser.json_ld_parts))
    name = profile.get("name") if isinstance(profile.get("name"), str) else ""
    full_name = name or parser.meta.get("og:title") or parser.title
    description = (
        profile.get("description")
        if isinstance(profile.get("description"), str)
        else parser.meta.get("og:description")
        or parser.meta.get("description")
        or ""
    )
    if not any((full_name, description, profile)):
        raise CrawlError("profile_not_detected", "No public profile metadata found")

    normalized_url = _normalize_url(source_url)
    host = urlsplit(normalized_url).hostname or ""
    same_as = profile.get("sameAs", [])
    if isinstance(same_as, str):
        same_as = [same_as]
    public_links = [
        value
        for value in same_as
        if isinstance(value, str) and value.startswith("https://")
    ]
    counts = _extract_counts(description, parser.meta.get("og:description", ""))
    verified = profile.get("isVerified")

    return InfluencerProfile(
        profile_id=hashlib.sha256(normalized_url.encode()).hexdigest(),
        platform=_platform(host),
        username=_username(profile, parser, normalized_url),
        profile_url=normalized_url,
        full_name=str(full_name).strip()[:255],
        biography=_redact_contact_details(str(description)),
        profile_pic_url=_image_url(profile.get("image"))
        or parser.meta.get("og:image"),
        follower_count=counts["follower_count"],
        following_count=counts["following_count"],
        media_count=counts["media_count"],
        is_verified=verified if isinstance(verified, bool) else None,
        category=(
            str(profile.get("jobTitle"))[:255]
            if profile.get("jobTitle")
            else None
        ),
        external_url=public_links[0] if public_links else None,
        source_fields={
            "metadata": sorted(parser.meta.keys()),
            "same_as": public_links[:20],
        },
    )


async def _resolve_addresses(hostname: str) -> list[str]:
    results = await asyncio.to_thread(socket.getaddrinfo, hostname, 443)
    return sorted({result[4][0] for result in results})


class PublicProfileCrawler:
    def __init__(
        self,
        *,
        user_agent: str,
        request_delay_seconds: float = 2.0,
        allowed_domains: tuple[str, ...] = (),
        timeout_seconds: float = 20.0,
        max_response_bytes: int = 2_000_000,
        robots_cache_seconds: float = 3_600.0,
        transport: Any | None = None,
        resolver: Callable[[str], Awaitable[list[str]]] = _resolve_addresses,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.user_agent = user_agent
        self.request_delay_seconds = max(0.0, request_delay_seconds)
        self.allowed_domains = tuple(
            domain.lower().strip(".") for domain in allowed_domains
        )
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.robots_cache_seconds = max(0.0, robots_cache_seconds)
        self.transport = transport
        self.resolver = resolver
        self.sleep = sleep
        self.robots_cache: dict[
            str, tuple[urllib.robotparser.RobotFileParser, float]
        ] = {}
        self.last_request_at: dict[str, float] = {}

    async def _validate_url(self, url: str) -> str:
        parts = urlsplit(url)
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username
            or parts.password
        ):
            raise CrawlError("invalid_url", "Only public HTTPS URLs are allowed")
        hostname = parts.hostname.lower().rstrip(".")
        if self.allowed_domains and not any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in self.allowed_domains
        ):
            raise CrawlError("domain_not_allowed", "Domain is not in crawler allowlist")
        try:
            addresses = await self.resolver(hostname)
        except OSError as exc:
            raise CrawlError("dns_error", "Could not resolve profile host") from exc
        if not addresses:
            raise CrawlError("dns_error", "Could not resolve profile host")
        for address in addresses:
            if not ipaddress.ip_address(address).is_global:
                raise CrawlError(
                    "private_address", "Private network targets are blocked"
                )
        return urlunsplit(
            ("https", parts.netloc.lower(), parts.path or "/", parts.query, "")
        )

    async def _wait(self, origin: str, robots_delay: float | None = None) -> None:
        delay = max(self.request_delay_seconds, robots_delay or 0.0)
        elapsed = time.monotonic() - self.last_request_at.get(origin, 0.0)
        if elapsed < delay:
            await self.sleep(delay - elapsed)

    async def _request(
        self,
        client: httpx2.AsyncClient,
        url: str,
        *,
        robots_delay: float | None = None,
    ) -> httpx2.Response:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        await self._wait(origin, robots_delay)
        try:
            async with client.stream("GET", url) as response:
                try:
                    content_length = int(
                        response.headers.get("content-length", "0") or 0
                    )
                except ValueError:
                    content_length = 0
                if content_length > self.max_response_bytes:
                    raise CrawlError(
                        "response_too_large", "Crawler response exceeds size limit"
                    )
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > self.max_response_bytes:
                        raise CrawlError(
                            "response_too_large",
                            "Crawler response exceeds size limit",
                        )
                decoded_headers = dict(response.headers)
                for header in ("content-encoding", "content-length", "transfer-encoding"):
                    decoded_headers.pop(header, None)
                result = httpx2.Response(
                    response.status_code,
                    headers=decoded_headers,
                    content=bytes(content),
                    request=response.request,
                )
        except httpx2.TimeoutException as exc:
            raise CrawlError("timeout", "Crawler request timed out") from exc
        except httpx2.RequestError as exc:
            raise CrawlError("network_error", "Crawler request failed") from exc
        finally:
            self.last_request_at[origin] = time.monotonic()
        return result

    async def _robots(
        self, client: httpx2.AsyncClient, url: str
    ) -> urllib.robotparser.RobotFileParser:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        cached = self.robots_cache.get(origin)
        if cached and time.monotonic() - cached[1] < self.robots_cache_seconds:
            return cached[0]
        robots_url = f"{origin}/robots.txt"
        response = await self._request(client, robots_url)
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)
        if response.status_code == 404:
            parser.parse([])
        elif response.status_code == 200:
            parser.parse(response.text.splitlines())
        else:
            raise CrawlError(
                "robots_unavailable",
                f"robots.txt returned HTTP {response.status_code}",
            )
        self.robots_cache[origin] = (parser, time.monotonic())
        return parser

    async def get_profile(self, url: str) -> InfluencerProfile:
        current = await self._validate_url(url)
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml",
        }
        async with httpx2.AsyncClient(
            headers=headers,
            follow_redirects=False,
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
            for _ in range(4):
                robots = await self._robots(client, current)
                if not robots.can_fetch(self.user_agent, current):
                    raise CrawlError("robots_denied", "robots.txt disallows this URL")
                response = await self._request(
                    client,
                    current,
                    robots_delay=robots.crawl_delay(self.user_agent),
                )
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise CrawlError(
                            "invalid_redirect", "Redirect has no location"
                        )
                    current = await self._validate_url(urljoin(current, location))
                    continue
                if response.status_code == 404:
                    raise CrawlError("not_found", "Profile page was not found")
                if response.status_code in {401, 403}:
                    raise CrawlError("access_denied", "Profile page denied access")
                if response.status_code == 429:
                    raise CrawlError(
                        "rate_limited", "Profile page rate limited the crawler"
                    )
                if response.status_code >= 400:
                    raise CrawlError(
                        "upstream_error",
                        f"Profile page returned HTTP {response.status_code}",
                    )
                content_type = response.headers.get("content-type", "").lower()
                if (
                    "text/html" not in content_type
                    and "application/xhtml+xml" not in content_type
                ):
                    raise CrawlError(
                        "unsupported_content", "Profile URL is not an HTML page"
                    )
                return parse_profile_html(response.text, str(response.url))
        raise CrawlError("too_many_redirects", "Profile page redirected too many times")
