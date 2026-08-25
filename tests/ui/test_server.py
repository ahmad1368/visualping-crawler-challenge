"""Unit tests for the live reporting server: ui.server's routes and CORS handling."""

from __future__ import annotations

import asyncio

from aiohttp.test_utils import TestClient, TestServer

from ui import server as server_module


def _run(coro):
    """Run an async coroutine synchronously, without depending on pytest-asyncio."""
    return asyncio.run(coro)


async def _client(app):
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    return client


class TestCorsMiddleware:
    """Success and failure scenarios for _cors_middleware, applied via /api/secrets."""

    def test_allows_a_localhost_origin_on_any_port(self, monkeypatch):
        monkeypatch.setattr(server_module, "load_results", lambda: _empty_report())

        async def scenario():
            client = await _client(server_module.create_app())
            try:
                resp = await client.get(
                    "/api/secrets", headers={"Origin": "http://127.0.0.1:5500"}
                )
                assert resp.headers.get("Access-Control-Allow-Origin") == "http://127.0.0.1:5500"
            finally:
                await client.close()

        _run(scenario())

    def test_omits_header_for_a_non_local_origin(self, monkeypatch):
        monkeypatch.setattr(server_module, "load_results", lambda: _empty_report())

        async def scenario():
            client = await _client(server_module.create_app())
            try:
                resp = await client.get(
                    "/api/secrets", headers={"Origin": "https://evil.example.com"}
                )
                assert "Access-Control-Allow-Origin" not in resp.headers
            finally:
                await client.close()

        _run(scenario())

    def test_omits_header_when_no_origin_sent(self, monkeypatch):
        monkeypatch.setattr(server_module, "load_results", lambda: _empty_report())

        async def scenario():
            client = await _client(server_module.create_app())
            try:
                resp = await client.get("/api/secrets")
                assert "Access-Control-Allow-Origin" not in resp.headers
            finally:
                await client.close()

        _run(scenario())


class TestHandleApiScan:
    """Success and failure scenarios for POST /api/scan."""

    def test_returns_500_and_no_crash_when_crawl_raises(self, monkeypatch):
        async def failing_run_crawl(start_url):
            raise RuntimeError("network exploded")

        monkeypatch.setattr(server_module, "run_crawl", failing_run_crawl)

        async def scenario():
            client = await _client(server_module.create_app())
            try:
                resp = await client.post("/api/scan")
                assert resp.status == 500
                body = await resp.json()
                assert "error" in body
            finally:
                await client.close()

        _run(scenario())


def _empty_report():
    from datetime import datetime, timezone

    from storage.exporter import build_report

    now = datetime.now(timezone.utc)
    return build_report(secrets=[], nodes=[], edges=[], start_time=now, end_time=now)
