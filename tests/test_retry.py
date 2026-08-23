"""Unit tests for the exponential backoff retry wrapper: retry.fetch_with_retry."""

import asyncio

import httpx

from fetcher import create_http_client
from retry import fetch_with_retry


def _run(coro):
    """Run an async coroutine synchronously, without depending on pytest-asyncio."""
    return asyncio.run(coro)


class FakeSleep:
    """Records delay calls instead of actually waiting, to keep tests instant."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


class TestFetchWithRetry:
    """Success and failure scenarios for fetch_with_retry."""

    def test_returns_response_on_first_success(self):
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, text="ok")

        async def scenario() -> httpx.Response | None:
            sleep = FakeSleep()
            async with create_http_client(transport=httpx.MockTransport(handler)) as client:
                return await fetch_with_retry(client, "https://example.com", sleep=sleep), sleep

        response, sleep = _run(scenario())
        assert response.status_code == 200
        assert call_count == 1
        assert sleep.calls == []

    def test_retries_on_network_error_then_succeeds(self):
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.ConnectError("connection refused", request=request)
            return httpx.Response(200, text="ok")

        async def scenario():
            sleep = FakeSleep()
            async with create_http_client(transport=httpx.MockTransport(handler)) as client:
                response = await fetch_with_retry(client, "https://example.com", sleep=sleep)
            return response, sleep

        response, sleep = _run(scenario())
        assert response is not None
        assert response.status_code == 200
        assert call_count == 2
        assert sleep.calls == [0.5]

    def test_retries_on_5xx_then_succeeds(self):
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(503)
            return httpx.Response(200, text="ok")

        async def scenario():
            sleep = FakeSleep()
            async with create_http_client(transport=httpx.MockTransport(handler)) as client:
                response = await fetch_with_retry(client, "https://example.com", sleep=sleep)
            return response, sleep

        response, sleep = _run(scenario())
        assert response.status_code == 200
        assert call_count == 2
        assert sleep.calls == [0.5]

    def test_returns_last_response_after_exhausting_retries_on_5xx(self):
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(503)

        async def scenario():
            sleep = FakeSleep()
            async with create_http_client(transport=httpx.MockTransport(handler)) as client:
                response = await fetch_with_retry(client, "https://example.com", max_retries=2, sleep=sleep)
            return response, sleep

        response, sleep = _run(scenario())
        assert response is not None
        assert response.status_code == 503
        assert call_count == 3
        assert sleep.calls == [0.5, 1.0]

    def test_returns_none_after_exhausting_retries_on_network_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        async def scenario():
            sleep = FakeSleep()
            async with create_http_client(transport=httpx.MockTransport(handler)) as client:
                response = await fetch_with_retry(client, "https://example.com", max_retries=1, sleep=sleep)
            return response, sleep

        response, sleep = _run(scenario())
        assert response is None
        assert sleep.calls == [0.5]

    def test_does_not_retry_client_error(self):
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(404)

        async def scenario():
            sleep = FakeSleep()
            async with create_http_client(transport=httpx.MockTransport(handler)) as client:
                response = await fetch_with_retry(client, "https://example.com", sleep=sleep)
            return response, sleep

        response, sleep = _run(scenario())
        assert response.status_code == 404
        assert call_count == 1
        assert sleep.calls == []
