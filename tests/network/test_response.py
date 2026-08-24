"""Unit tests for the raw network response wrapper: response.RawResponse."""

import asyncio
from datetime import timedelta

import httpx
import pytest
from pydantic import ValidationError

from network.fetcher import create_http_client
from network.response import RawResponse


def _run(coro):
    """Run an async coroutine synchronously, without depending on pytest-asyncio."""
    return asyncio.run(coro)


def _fetch(handler) -> httpx.Response:
    """Perform a single GET request against a mocked transport.

    `httpx.MockTransport` responses built with a pre-set `text=`/`content=`
    body never pass through the real network stream, so `response.elapsed`
    is never populated the way it would be for a genuine network transport.
    It is set manually here to keep `RawResponse.from_httpx_response` free
    to rely on it unconditionally.
    """

    async def scenario() -> httpx.Response:
        async with create_http_client(transport=httpx.MockTransport(handler)) as client:
            return await client.get("https://example.com/page")

    response = _run(scenario())
    response.elapsed = timedelta(seconds=0.01)
    return response


class TestFromHttpxResponse:
    """Success and failure scenarios for RawResponse.from_httpx_response."""

    def test_captures_html_body(self):
        response = _fetch(lambda request: httpx.Response(200, text="<html>hi</html>"))
        raw = RawResponse.from_httpx_response(response)
        assert raw.html_body == "<html>hi</html>"

    def test_captures_status_code(self):
        response = _fetch(lambda request: httpx.Response(404, text="not found"))
        raw = RawResponse.from_httpx_response(response)
        assert raw.status_code == 404

    def test_captures_url(self):
        response = _fetch(lambda request: httpx.Response(200, text="ok"))
        raw = RawResponse.from_httpx_response(response)
        assert raw.url == "https://example.com/page"

    def test_captures_response_headers(self):
        response = _fetch(
            lambda request: httpx.Response(200, headers={"X-Custom": "value"}, text="ok")
        )
        raw = RawResponse.from_httpx_response(response)
        assert raw.headers["x-custom"] == "value"

    def test_captures_cookies(self):
        response = _fetch(
            lambda request: httpx.Response(
                200, headers={"Set-Cookie": "session=abc123; Path=/"}, text="ok"
            )
        )
        raw = RawResponse.from_httpx_response(response)
        assert raw.cookies["session"] == "abc123"

    def test_captures_non_negative_elapsed_time(self):
        response = _fetch(lambda request: httpx.Response(200, text="ok"))
        raw = RawResponse.from_httpx_response(response)
        assert raw.elapsed_time >= 0


class TestExtractionMethods:
    """Success and failure scenarios for get_header and get_cookie."""

    def _build(self, **overrides) -> RawResponse:
        fields = dict(
            url="https://example.com",
            status_code=200,
            html_body="<html></html>",
            headers={"Content-Type": "text/html"},
            cookies={"session": "abc123"},
            elapsed_time=0.1,
        )
        fields.update(overrides)
        return RawResponse(**fields)

    def test_get_header_is_case_insensitive(self):
        raw = self._build()
        assert raw.get_header("content-type") == "text/html"

    def test_get_header_missing_returns_default(self):
        raw = self._build()
        assert raw.get_header("X-Missing", default="fallback") == "fallback"

    def test_get_cookie_returns_value(self):
        raw = self._build()
        assert raw.get_cookie("session") == "abc123"

    def test_get_cookie_missing_returns_none(self):
        raw = self._build()
        assert raw.get_cookie("missing") is None


class TestValidation:
    """Failure scenarios for RawResponse field validation."""

    def _fields(self, **overrides) -> dict:
        fields = dict(
            url="https://example.com",
            status_code=200,
            html_body="<html></html>",
            headers={},
            cookies={},
            elapsed_time=0.1,
        )
        fields.update(overrides)
        return fields

    def test_rejects_blank_url(self):
        with pytest.raises(ValidationError):
            RawResponse(**self._fields(url="   "))

    def test_rejects_status_code_below_range(self):
        with pytest.raises(ValidationError):
            RawResponse(**self._fields(status_code=99))

    def test_rejects_status_code_above_range(self):
        with pytest.raises(ValidationError):
            RawResponse(**self._fields(status_code=600))

    def test_rejects_negative_elapsed_time(self):
        with pytest.raises(ValidationError):
            RawResponse(**self._fields(elapsed_time=-1.0))

    def test_is_frozen(self):
        raw = RawResponse(**self._fields())
        with pytest.raises(ValidationError):
            raw.status_code = 500
