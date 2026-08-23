"""Unit tests for the async HTTP client factory: fetcher.create_http_client."""

import asyncio

import httpx
import pytest

import config
from fetcher import DEFAULT_HEADERS, create_http_client


def _run(coro):
    """Run an async coroutine synchronously, without depending on pytest-asyncio."""
    return asyncio.run(coro)


class TestCreateHttpClient:
    """Success and failure scenarios for create_http_client."""

    def test_returns_async_client(self):
        client = create_http_client()
        try:
            assert isinstance(client, httpx.AsyncClient)
        finally:
            _run(client.aclose())

    def test_applies_default_headers(self):
        client = create_http_client()
        try:
            assert client.headers["User-Agent"] == DEFAULT_HEADERS["User-Agent"]
            assert client.headers["Accept"] == DEFAULT_HEADERS["Accept"]
        finally:
            _run(client.aclose())

    def test_applies_configured_timeouts(self):
        client = create_http_client()
        try:
            assert client.timeout.connect == config.CONNECT_TIMEOUT
            assert client.timeout.read == config.READ_TIMEOUT
        finally:
            _run(client.aclose())

    def test_persists_cookies_across_requests(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if "session=abc123" in request.headers.get("cookie", ""):
                return httpx.Response(200, text="authenticated")
            return httpx.Response(200, headers={"Set-Cookie": "session=abc123; Path=/"})

        async def scenario() -> httpx.Response:
            client = create_http_client(transport=httpx.MockTransport(handler))
            try:
                await client.get("https://example.com/login")
                return await client.get("https://example.com/dashboard")
            finally:
                await client.aclose()

        response = _run(scenario())
        assert response.text == "authenticated"

    def test_propagates_network_errors(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        async def scenario() -> None:
            client = create_http_client(transport=httpx.MockTransport(handler))
            try:
                await client.get("https://example.com")
            finally:
                await client.aclose()

        with pytest.raises(httpx.ConnectError):
            _run(scenario())
