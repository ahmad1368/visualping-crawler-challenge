"""BFS traversal loop controller for the crawler.

Drives the breadth-first crawl over a `StateManager`'s queue, invoking an
injected async page processor for each dequeued URL and enqueuing any
newly-discovered links it returns, bounded by an optional maximum depth.
Fetching, parsing, and scanning are entirely the page processor's
responsibility (see the page-processing pipeline module) — this
controller only owns traversal order, duplicate-visit prevention, and
depth boundaries.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from state import StateManager

logger = logging.getLogger(__name__)

# Given a URL and its BFS depth, fetches/parses that page and returns the
# list of links discovered on it.
PageProcessor = Callable[[str, int], Awaitable[list[str]]]


async def crawl(
    start_url: str,
    process_page: PageProcessor,
    *,
    state: StateManager | None = None,
    max_depth: int | None = None,
) -> StateManager:
    """Run a breadth-first crawl starting from `start_url`.

    Seeds `state` (a fresh `StateManager` if none is given) with
    `start_url` at depth 0, then repeatedly dequeues the next pending URL
    and awaits `process_page(url, depth)` for it. Each link the processor
    returns is enqueued at `depth + 1`, unless it has already been seen
    (`StateManager.enqueue` marks a URL visited as soon as it is
    enqueued, which is what prevents revisits and infinite loops) or
    `max_depth` is set and `depth + 1` would exceed it.

    A page whose processing raises is logged and skipped, without
    interrupting the rest of the crawl.

    Returns the `StateManager` instance that drove the crawl, so the
    caller can inspect `visited_count`/`pending_count` afterward.

    Raises ValueError if `start_url` is blank.
    """
    if not start_url.strip():
        raise ValueError("start_url must not be blank")

    if state is None:
        state = StateManager()

    state.enqueue(start_url, depth=0)

    while state.has_pending():
        item = state.dequeue()
        if item is None:
            break
        url, depth = item

        logger.info("Processing %s at depth %d", url, depth)
        try:
            discovered_links = await process_page(url, depth)
        except Exception as exc:
            logger.error("Failed to process %s at depth %d: %s", url, depth, exc)
            continue

        next_depth = depth + 1
        if max_depth is not None and next_depth > max_depth:
            logger.debug(
                "Depth boundary %d reached; not enqueuing links from %s", max_depth, url
            )
            continue

        for link in discovered_links:
            state.enqueue(link, depth=next_depth)

    return state
