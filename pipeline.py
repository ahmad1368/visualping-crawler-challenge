"""Page processing pipeline: fetch, extract links, and scan for secrets.

Integrates the async fetcher/retry layer with the link extractor and the
secret scanners (HTML body/comments, HTTP headers, cookies) into a single
per-page pipeline compatible with `crawler.crawl`'s `PageProcessor`
callback: given a URL, fetch it, concurrently scan it for secrets
(persisting each one immediately via an injected sink), and return the
links discovered on it for the BFS queue to continue traversing.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

import httpx

from asset_scanner import scan_cookies, scan_headers
from crawler import PageProcessor
from html_scanner import scan_html
from link_extractor import extract_links
from models import Secret
from response import RawResponse
from retry import fetch_with_retry

logger = logging.getLogger(__name__)

# Invoked with each Secret as soon as it is discovered, e.g. to append it
# to the results file. May be sync or async.
SecretSink = Callable[[Secret], Awaitable[None] | None]


async def process_page(
    client: httpx.AsyncClient,
    url: str,
    depth: int,
    *,
    on_secret_found: SecretSink,
    max_retries: int | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> list[str]:
    """Fetch a single page, scan it for secrets, and return discovered links.

    Fetches `url` through `client` (with retry/backoff via
    `retry.fetch_with_retry`). If the fetch fails outright (exhausted
    retries after a network error), logs it and returns an empty link
    list rather than raising, so one unreachable page never stops the
    crawl.

    On any completed response, wraps it in a `RawResponse` and
    concurrently runs the body/comment, header, and cookie secret
    scanners via `asyncio.gather`, invoking `on_secret_found` for every
    `Secret` each one discovers as soon as that scanner finishes,
    satisfying the "persist secrets instantly" requirement rather than
    batching everything until the whole page is done. Finally extracts
    and returns the page's links via `link_extractor.extract_links`, for
    the caller to enqueue.
    """
    response = await fetch_with_retry(client, url, max_retries=max_retries, sleep=sleep)
    if response is None:
        logger.warning("Skipping %s at depth %d: request failed after retries", url, depth)
        return []

    raw = RawResponse.from_httpx_response(response)

    scan_tasks = [
        _scan_and_report(lambda: scan_html(raw.html_body, raw.url), on_secret_found),
        _scan_and_report(lambda: scan_headers(raw.headers, raw.url), on_secret_found),
        _scan_and_report(lambda: scan_cookies(raw.cookies, raw.url), on_secret_found),
    ]
    await asyncio.gather(*scan_tasks)

    return extract_links(raw.html_body, raw.url)


async def _scan_and_report(scan: Callable[[], list[Secret]], on_secret_found: SecretSink) -> None:
    """Run a synchronous scanner function and report each secret it finds."""
    for secret in scan():
        result = on_secret_found(secret)
        if asyncio.iscoroutine(result):
            await result


def build_page_processor(
    client: httpx.AsyncClient,
    on_secret_found: SecretSink,
    *,
    max_retries: int | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> PageProcessor:
    """Build a `crawler.PageProcessor` bound to a shared client and secret sink.

    Wraps `process_page` into the `(url, depth) -> list[str]` shape that
    `crawler.crawl` expects, so the traversal loop stays fully decoupled
    from HTTP fetching and secret scanning.
    """

    async def processor(url: str, depth: int) -> list[str]:
        return await process_page(
            client, url, depth, on_secret_found=on_secret_found, max_retries=max_retries, sleep=sleep
        )

    return processor
