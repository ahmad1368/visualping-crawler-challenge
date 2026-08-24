"""Unit tests for the page processing pipeline: pipeline.process_page/build_page_processor."""

import asyncio

import httpx
import pytest

from fetcher import create_http_client
from models import SecretLocation
from pipeline import build_page_processor, process_page

BODY_SECRET = "VISUALPING{0123456789abcdef}"
HEADER_SECRET = "VISUALPING{fedcba9876543210}"
COOKIE_SECRET = "VISUALPING{1111111111111111}"


def _run(coro):
    """Run an async coroutine synchronously, without depending on pytest-asyncio."""
    return asyncio.run(coro)


class RecordingSink:
    """Fake secret sink that records every Secret it is invoked with."""

    def __init__(self) -> None:
        self.secrets: list = []

    def __call__(self, secret) -> None:
        self.secrets.append(secret)


class AsyncRecordingSink:
    """Fake async secret sink that records every Secret it is invoked with."""

    def __init__(self) -> None:
        self.secrets: list = []

    async def __call__(self, secret) -> None:
        self.secrets.append(secret)


def _client_for(handler) -> httpx.AsyncClient:
    return create_http_client(transport=httpx.MockTransport(handler))


class TestProcessPage:
    """Success and failure scenarios for process_page."""

    def test_returns_links_extracted_from_the_page(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text='<a href="/child">child</a>')

        async def scenario() -> list[str]:
            sink = RecordingSink()
            async with _client_for(handler) as client:
                return await process_page(client, "https://example.com", 0, on_secret_found=sink)

        links = _run(scenario())
        assert links == ["https://example.com/child"]

    def test_reports_secret_found_in_body(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=f"<p>{BODY_SECRET}</p>")

        async def scenario():
            sink = RecordingSink()
            async with _client_for(handler) as client:
                await process_page(client, "https://example.com", 0, on_secret_found=sink)
            return sink

        sink = _run(scenario())
        assert [s.value for s in sink.secrets] == [BODY_SECRET]

    def test_reports_secret_found_in_header(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, headers={"X-Debug": HEADER_SECRET}, text="ok")

        async def scenario():
            sink = RecordingSink()
            async with _client_for(handler) as client:
                await process_page(client, "https://example.com", 0, on_secret_found=sink)
            return sink

        sink = _run(scenario())
        assert [s.value for s in sink.secrets] == [HEADER_SECRET]

    def test_reports_secret_found_in_cookie(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, headers={"Set-Cookie": f"debug={COOKIE_SECRET}; Path=/"}, text="ok"
            )

        async def scenario():
            sink = RecordingSink()
            async with _client_for(handler) as client:
                await process_page(client, "https://example.com", 0, on_secret_found=sink)
            return sink

        sink = _run(scenario())
        # The Set-Cookie header carries the same secret value into both the
        # raw headers dict and the parsed cookie jar, so it is legitimately
        # reported twice: once per location (HTTP_HEADER and COOKIE).
        locations = {s.location for s in sink.secrets if s.value == COOKIE_SECRET}
        assert locations == {SecretLocation.HTTP_HEADER, SecretLocation.COOKIE}

    def test_reports_secrets_from_all_scanners_in_one_page(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"X-Debug": HEADER_SECRET, "Set-Cookie": f"debug={COOKIE_SECRET}"},
                text=f"<p>{BODY_SECRET}</p>",
            )

        async def scenario():
            sink = RecordingSink()
            async with _client_for(handler) as client:
                await process_page(client, "https://example.com", 0, on_secret_found=sink)
            return sink

        sink = _run(scenario())
        assert {s.value for s in sink.secrets} == {BODY_SECRET, HEADER_SECRET, COOKIE_SECRET}

    def test_supports_async_secret_sink(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=f"<p>{BODY_SECRET}</p>")

        async def scenario():
            sink = AsyncRecordingSink()
            async with _client_for(handler) as client:
                await process_page(client, "https://example.com", 0, on_secret_found=sink)
            return sink

        sink = _run(scenario())
        assert [s.value for s in sink.secrets] == [BODY_SECRET]

    def test_returns_empty_links_and_reports_nothing_when_fetch_exhausts_retries(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        async def scenario():
            sink = RecordingSink()
            async with _client_for(handler) as client:
                links = await process_page(
                    client,
                    "https://example.com",
                    0,
                    on_secret_found=sink,
                    max_retries=0,
                    sleep=lambda seconds: asyncio.sleep(0),
                )
            return links, sink

        links, sink = _run(scenario())
        assert links == []
        assert sink.secrets == []

    def test_no_secrets_reported_when_page_is_clean(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<p>Nothing sensitive here.</p>")

        async def scenario():
            sink = RecordingSink()
            async with _client_for(handler) as client:
                await process_page(client, "https://example.com", 0, on_secret_found=sink)
            return sink

        sink = _run(scenario())
        assert sink.secrets == []


class TestBuildPageProcessor:
    """Success scenarios for build_page_processor's crawler.PageProcessor adapter."""

    def test_returned_processor_matches_process_page_behavior(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text='<a href="/child">child</a>')

        async def scenario() -> list[str]:
            sink = RecordingSink()
            async with _client_for(handler) as client:
                processor = build_page_processor(client, sink)
                return await processor("https://example.com", 0)

        links = _run(scenario())
        assert links == ["https://example.com/child"]
