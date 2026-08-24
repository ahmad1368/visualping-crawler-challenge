"""Page processing pipeline: fetch, extract links, and scan for secrets.

Integrates the async fetcher/retry layer with the link extractor, the
secret scanners (HTML body/comments, HTTP headers, cookies, inline
scripts, linked JS/CSS assets), and the hidden-route finder into a
single per-page pipeline compatible with `crawler.crawl`'s
`PageProcessor` callback: given a URL, fetch it, concurrently scan it
(and its linked assets) for secrets (persisting each one immediately via
an injected sink), and return every link discovered -- via `<a>` tags,
via routes embedded in raw text/scripts, or via a route referenced only
in a fetched JS/CSS asset -- for the BFS queue to continue traversing.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

import httpx

from core.models import Secret
from crawl.crawler import PageProcessor
from network.response import RawResponse
from network.retry import fetch_with_retry
from parsers.asset_scanner import (
    extract_asset_urls,
    scan_cookies,
    scan_headers,
    scan_inline_scripts,
    scan_script,
)
from parsers.html_scanner import scan_html
from parsers.link_extractor import extract_links
from parsers.route_finder import find_routes, find_routes_in_html

logger = logging.getLogger(__name__)

# Invoked with each Secret as soon as it is discovered, e.g. to append it
# to the results file. May be sync or async.
SecretSink = Callable[[Secret], Awaitable[None] | None]

# Invoked once a page has finished processing, with (url, depth,
# status_code, has_secret) -- status_code is None if the fetch failed
# outright. Lets a caller (e.g. main.py) record full node metadata for
# the report without duplicating the fetch/scan logic itself.
PageProcessedCallback = Callable[[str, int, int | None, bool], None]


async def process_page(
    client: httpx.AsyncClient,
    url: str,
    depth: int,
    *,
    on_secret_found: SecretSink,
    on_page_processed: PageProcessedCallback | None = None,
    max_retries: int | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    scanned_assets: set[str] | None = None,
) -> list[str]:
    """Fetch a single page, scan it (and its linked assets) for secrets,
    and return every link discovered.

    Fetches `url` through `client` (with retry/backoff via
    `network.retry.fetch_with_retry`). If the fetch fails outright (exhausted
    retries after a network error), logs it, invokes `on_page_processed`
    (if given) with a `None` status code and `has_secret=False`, and
    returns an empty link list rather than raising, so one unreachable
    page never stops the crawl.

    On any completed response, wraps it in a `RawResponse` and
    concurrently runs two things:

    1. The page's own scanners (body/comments, headers, cookies, inline
       `<script>` tags), reporting each `Secret` to `on_secret_found` the
       instant its scanner finds it, rather than batching until the
       whole page is done.
    2. Every linked JS/CSS asset (`<script src>`, `<link rel=stylesheet
       href>`): fetched, scanned for secrets the same way, and scanned
       for hidden routes via `route_finder.find_routes` -- some sites
       only reference a route from client-side JS (e.g. a nav menu built
       by DOM manipulation), never from any page's raw HTML, so a purely
       HTML-based crawl would never discover it otherwise. `scanned_assets`
       (shared across the whole crawl via `build_page_processor`) is
       checked first, since the same handful of assets are typically
       linked from every page and refetching/rescanning them each time
       would be pure waste.

    Once both finish, invokes `on_page_processed` (if given) with the
    response's status code and whether *either* found a secret. Finally
    combines links from `<a>` tags, from hidden routes embedded directly
    in the page's own text/scripts, and from hidden routes found in its
    assets -- deduplicated, preserving first-seen order -- for the
    caller to enqueue.
    """
    response = await fetch_with_retry(client, url, max_retries=max_retries, sleep=sleep)
    if response is None:
        logger.warning("Skipping %s at depth %d: request failed after retries", url, depth)
        if on_page_processed is not None:
            on_page_processed(url, depth, None, False)
        return []

    raw = RawResponse.from_httpx_response(response)

    async def _scan_page() -> bool:
        results = await asyncio.gather(
            _scan_and_report(lambda: scan_html(raw.html_body, raw.url), on_secret_found),
            _scan_and_report(lambda: scan_headers(raw.headers, raw.url), on_secret_found),
            _scan_and_report(lambda: scan_cookies(raw.cookies, raw.url), on_secret_found),
            _scan_and_report(
                lambda: scan_inline_scripts(raw.html_body, raw.url), on_secret_found
            ),
        )
        return any(results)

    async def _scan_assets() -> tuple[bool, list[str]]:
        asset_urls = extract_asset_urls(raw.html_body, raw.url)
        if scanned_assets is not None:
            asset_urls = [u for u in asset_urls if u not in scanned_assets]
            scanned_assets.update(asset_urls)
        if not asset_urls:
            return False, []

        results = await asyncio.gather(
            *[
                _fetch_and_scan_asset(client, asset_url, on_secret_found, max_retries, sleep)
                for asset_url in asset_urls
            ]
        )
        any_secret = any(has_secret for has_secret, _ in results)
        routes = [route for _, asset_routes in results for route in asset_routes]
        return any_secret, routes

    page_has_secret, (assets_have_secret, asset_routes) = await asyncio.gather(
        _scan_page(), _scan_assets()
    )

    if on_page_processed is not None:
        on_page_processed(url, depth, raw.status_code, page_has_secret or assets_have_secret)

    links = extract_links(raw.html_body, raw.url)
    page_routes = find_routes_in_html(raw.html_body, raw.url)
    return list(dict.fromkeys(links + page_routes + asset_routes))


async def _scan_and_report(scan: Callable[[], list[Secret]], on_secret_found: SecretSink) -> bool:
    """Run a synchronous scanner function, report each secret found, and return whether any were."""
    secrets = scan()
    for secret in secrets:
        result = on_secret_found(secret)
        if asyncio.iscoroutine(result):
            await result
    return bool(secrets)


async def _fetch_and_scan_asset(
    client: httpx.AsyncClient,
    asset_url: str,
    on_secret_found: SecretSink,
    max_retries: int | None,
    sleep: Callable[[float], Awaitable[None]],
) -> tuple[bool, list[str]]:
    """Fetch a linked JS/CSS asset and scan it for secrets and hidden routes.

    Returns `(has_secret, hidden_routes)`. A fetch failure is logged and
    treated as "nothing found" -- one unreachable asset never stops the
    crawl, matching `process_page`'s own resilience to a bad URL.
    """
    response = await fetch_with_retry(client, asset_url, max_retries=max_retries, sleep=sleep)
    if response is None:
        logger.warning("Skipping asset %s: request failed after retries", asset_url)
        return False, []

    asset_raw = RawResponse.from_httpx_response(response)
    has_secret = await _scan_and_report(
        lambda: scan_script(asset_raw.html_body, asset_raw.url), on_secret_found
    )
    routes = find_routes(asset_raw.html_body, asset_raw.url)
    return has_secret, routes


def build_page_processor(
    client: httpx.AsyncClient,
    on_secret_found: SecretSink,
    *,
    on_page_processed: PageProcessedCallback | None = None,
    max_retries: int | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> PageProcessor:
    """Build a `crawler.PageProcessor` bound to a shared client and secret sink.

    Wraps `process_page` into the `(url, depth) -> list[str]` shape that
    `crawler.crawl` expects, so the traversal loop stays fully decoupled
    from HTTP fetching and secret scanning. Creates one `scanned_assets`
    set here, shared across every call the returned processor makes for
    the lifetime of a single crawl, so the same linked JS/CSS asset is
    never fetched and rescanned once per page that happens to link it.
    """
    scanned_assets: set[str] = set()

    async def processor(url: str, depth: int) -> list[str]:
        return await process_page(
            client,
            url,
            depth,
            on_secret_found=on_secret_found,
            on_page_processed=on_page_processed,
            max_retries=max_retries,
            sleep=sleep,
            scanned_assets=scanned_assets,
        )

    return processor
