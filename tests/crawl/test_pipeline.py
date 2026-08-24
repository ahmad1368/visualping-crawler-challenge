"""Unit tests for the page processing pipeline: pipeline.process_page/build_page_processor."""

import asyncio

import httpx
import pytest

from core.models import SecretLocation
from crawl.pipeline import build_page_processor, process_page
from network.fetcher import create_http_client

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


class RecordingPageProcessedCallback:
    """Fake on_page_processed callback that records every call it receives."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int, int | None, bool]] = []

    def __call__(self, url: str, depth: int, status_code: int | None, has_secret: bool) -> None:
        self.calls.append((url, depth, status_code, has_secret))


class TestOnPageProcessed:
    """Success and failure scenarios for the on_page_processed callback."""

    def test_called_with_status_code_and_no_secret_on_clean_page(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<p>Nothing sensitive here.</p>")

        async def scenario():
            callback = RecordingPageProcessedCallback()
            async with _client_for(handler) as client:
                await process_page(
                    client,
                    "https://example.com",
                    2,
                    on_secret_found=RecordingSink(),
                    on_page_processed=callback,
                )
            return callback

        callback = _run(scenario())
        assert callback.calls == [("https://example.com", 2, 200, False)]

    def test_called_with_has_secret_true_when_a_secret_is_found(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=f"<p>{BODY_SECRET}</p>")

        async def scenario():
            callback = RecordingPageProcessedCallback()
            async with _client_for(handler) as client:
                await process_page(
                    client,
                    "https://example.com",
                    0,
                    on_secret_found=RecordingSink(),
                    on_page_processed=callback,
                )
            return callback

        callback = _run(scenario())
        assert callback.calls == [("https://example.com", 0, 200, True)]

    def test_called_with_none_status_code_when_fetch_fails(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        async def scenario():
            callback = RecordingPageProcessedCallback()
            async with _client_for(handler) as client:
                await process_page(
                    client,
                    "https://example.com",
                    0,
                    on_secret_found=RecordingSink(),
                    on_page_processed=callback,
                    max_retries=0,
                    sleep=lambda seconds: asyncio.sleep(0),
                )
            return callback

        callback = _run(scenario())
        assert callback.calls == [("https://example.com", 0, None, False)]

    def test_not_required_and_defaults_to_none(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="ok")

        async def scenario() -> list[str]:
            async with _client_for(handler) as client:
                return await process_page(
                    client, "https://example.com", 0, on_secret_found=RecordingSink()
                )

        links = _run(scenario())
        assert links == []


class TestInlineScriptAndAssetScanning:
    """Success and failure scenarios for scanning inline scripts and linked JS/CSS assets."""

    def test_reports_secret_found_in_inline_script(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=f"<script>var t = '{BODY_SECRET}';</script>")

        async def scenario():
            sink = RecordingSink()
            async with _client_for(handler) as client:
                await process_page(client, "https://example.com", 0, on_secret_found=sink)
            return sink

        sink = _run(scenario())
        assert [s.value for s in sink.secrets] == [BODY_SECRET]

    def test_reports_secret_found_in_linked_js_asset(self):
        asset_secret = "VISUALPING{349a583fba34c301}"

        def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url) == "https://example.com/static/app.js":
                return httpx.Response(200, text=f"var ADMIN = '{asset_secret}';")
            return httpx.Response(200, text='<script src="/static/app.js"></script>')

        async def scenario():
            sink = RecordingSink()
            async with _client_for(handler) as client:
                await process_page(client, "https://example.com", 0, on_secret_found=sink)
            return sink

        sink = _run(scenario())
        assert [s.value for s in sink.secrets] == [asset_secret]

    def test_includes_hidden_route_found_in_page_text(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<body><p>See /api/hidden-report</p></body>")

        async def scenario() -> list[str]:
            sink = RecordingSink()
            async with _client_for(handler) as client:
                return await process_page(client, "https://example.com", 0, on_secret_found=sink)

        links = _run(scenario())
        assert "https://example.com/api/hidden-report" in links

    def test_includes_hidden_route_found_in_linked_js_asset(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url) == "https://example.com/static/nav.js":
                return httpx.Response(200, text='var MENU = [{ path: "/wiki/hidden-page" }];')
            return httpx.Response(200, text='<script src="/static/nav.js"></script>')

        async def scenario() -> list[str]:
            sink = RecordingSink()
            async with _client_for(handler) as client:
                return await process_page(client, "https://example.com", 0, on_secret_found=sink)

        links = _run(scenario())
        assert "https://example.com/wiki/hidden-page" in links

    def test_does_not_refetch_same_asset_across_pages_sharing_a_processor(self):
        asset_fetch_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal asset_fetch_count
            if str(request.url) == "https://example.com/static/shared.js":
                asset_fetch_count += 1
                return httpx.Response(200, text="// shared asset, no secrets")
            return httpx.Response(200, text='<script src="/static/shared.js"></script>')

        async def scenario() -> int:
            sink = RecordingSink()
            async with _client_for(handler) as client:
                processor = build_page_processor(client, sink)
                await processor("https://example.com/a", 0)
                await processor("https://example.com/b", 0)
            return asset_fetch_count

        count = _run(scenario())
        assert count == 1

    def test_asset_fetch_failure_does_not_break_page_processing(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url) == "https://example.com/static/broken.js":
                raise httpx.ConnectError("connection refused", request=request)
            return httpx.Response(200, text='<script src="/static/broken.js"></script>')

        async def scenario() -> list[str]:
            sink = RecordingSink()
            async with _client_for(handler) as client:
                return await process_page(
                    client,
                    "https://example.com",
                    0,
                    on_secret_found=sink,
                    max_retries=0,
                    sleep=lambda seconds: asyncio.sleep(0),
                )

        links = _run(scenario())
        assert links == []


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

    def test_forwards_on_page_processed_to_process_page(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="ok")

        async def scenario():
            callback = RecordingPageProcessedCallback()
            async with _client_for(handler) as client:
                processor = build_page_processor(
                    client, RecordingSink(), on_page_processed=callback
                )
                await processor("https://example.com", 3)
            return callback

        callback = _run(scenario())
        assert callback.calls == [("https://example.com", 3, 200, False)]
