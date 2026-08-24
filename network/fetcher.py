"""Async HTTP client factory for the crawler.

Provides a single entry point for creating a pre-configured
`httpx.AsyncClient`: standard headers (User-Agent, Accept) and request
timeouts sourced from `config`. The returned client maintains its own
cookie jar, so cookies set by one response are automatically attached to
subsequent requests made through the same client instance.
"""

from __future__ import annotations

import httpx

from core import config

DEFAULT_USER_AGENT = "VisualpingCrawler/1.0 (+https://visualping.io)"

DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def create_http_client(
    transport: httpx.AsyncBaseTransport | None = None,
    auth: httpx.Auth | tuple[str, str] | None = None,
) -> httpx.AsyncClient:
    """Build an `httpx.AsyncClient` configured for crawling.

    The returned client applies the project's standard headers and network
    timeouts, and persists cookies across requests via its built-in cookie
    jar. `transport` is exposed for dependency injection (e.g. tests using
    `httpx.MockTransport`, or a future retry-aware transport); it defaults
    to httpx's normal network transport when omitted. `auth` is forwarded
    to `httpx.AsyncClient` as-is: pass an `(username, password)` tuple for
    HTTP Basic Auth on every request, or any `httpx.Auth` instance for a
    different scheme (e.g. `httpx.DigestAuth`).

    Callers are responsible for closing the client, e.g.:
        async with create_http_client() as client:
            ...
    """
    timeout = httpx.Timeout(config.READ_TIMEOUT, connect=config.CONNECT_TIMEOUT)
    return httpx.AsyncClient(
        headers=DEFAULT_HEADERS, timeout=timeout, transport=transport, auth=auth
    )
