"""Retry logic with exponential backoff for outbound HTTP requests.

Wraps a single request made through an `httpx.AsyncClient`, retrying on
network errors and 5xx server responses using exponential backoff. All
other outcomes (successful responses and non-retryable 4xx client errors)
are returned as-is, and every exhausted-retry path is logged rather than
raised, so a single bad URL never interrupts the crawl.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

import httpx

from core import config

logger = logging.getLogger(__name__)

# Base delay, in seconds, before the first retry; doubles on each subsequent attempt.
BACKOFF_BASE_SECONDS = 0.5

# Server error status codes treated as transient and therefore retryable.
# 4xx client errors are not retried: retrying an unchanged request will not
# change a client-side error result.
RETRYABLE_STATUS_CODES = frozenset(range(500, 600))


async def fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    method: str = "GET",
    max_retries: int | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> httpx.Response | None:
    """Perform an HTTP request with exponential backoff retry.

    Retries on network errors (connection failures, timeouts) and 5xx
    responses, waiting `BACKOFF_BASE_SECONDS * 2**attempt` seconds between
    attempts. Any other response (2xx, 3xx, or 4xx) is returned immediately
    without retrying.

    If every attempt fails with a network error, logs the final error and
    returns None. If every attempt returns a retryable 5xx status, logs it
    and returns that last response so the caller can inspect its status
    code.

    `max_retries` defaults to `config.MAX_RETRIES` additional attempts
    after the first. `sleep` is exposed for dependency injection in tests.
    """
    attempts = (max_retries if max_retries is not None else config.MAX_RETRIES) + 1

    for attempt in range(attempts):
        is_last_attempt = attempt + 1 >= attempts

        try:
            response = await client.request(method, url)
        except httpx.RequestError as exc:
            if is_last_attempt:
                logger.error("Exhausted retries for %s after a network error: %s", url, exc)
                return None
            logger.warning("Request error on attempt %d/%d for %s: %s", attempt + 1, attempts, url, exc)
            await sleep(BACKOFF_BASE_SECONDS * (2**attempt))
            continue

        if response.status_code not in RETRYABLE_STATUS_CODES:
            return response

        if is_last_attempt:
            logger.error(
                "Exhausted retries for %s after repeated %d responses.", url, response.status_code
            )
            return response

        logger.warning(
            "Retryable status %d on attempt %d/%d for %s", response.status_code, attempt + 1, attempts, url
        )
        await sleep(BACKOFF_BASE_SECONDS * (2**attempt))

    return None
