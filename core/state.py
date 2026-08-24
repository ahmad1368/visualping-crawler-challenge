"""In-memory state manager for the crawler's BFS traversal.

Tracks which URLs have been seen (queued or processed) to prevent duplicate
traversals and cycles, and maintains the BFS queue of URLs pending crawl.
All state lives in a single instance's memory and is not shared across
processes.
"""

from __future__ import annotations

import logging
from collections import deque

logger = logging.getLogger(__name__)


class StateManager:
    """Centralized, in-memory state for a single crawl execution.

    Combines a `visited_urls` set (O(1) membership checks) with a `deque`
    queue to drive breadth-first traversal, guaranteeing that no URL is
    enqueued or processed more than once.
    """

    def __init__(self) -> None:
        self._visited_urls: set[str] = set()
        self._queue: deque[tuple[str, int]] = deque()

    @property
    def visited_count(self) -> int:
        """Number of URLs that have been seen (queued or processed)."""
        return len(self._visited_urls)

    @property
    def pending_count(self) -> int:
        """Number of URLs currently waiting in the BFS queue."""
        return len(self._queue)

    def is_visited(self, url: str) -> bool:
        """Return True if the URL has already been seen (queued or processed)."""
        return url in self._visited_urls

    def enqueue(self, url: str, depth: int = 0) -> bool:
        """Add a URL to the BFS queue if it has not been seen before.

        Marks the URL as visited immediately, rather than on dequeue, so
        that rediscovering the same URL later in the crawl does not create
        a duplicate queue entry or a traversal cycle.

        Returns True if the URL was newly enqueued, False if it was a
        duplicate and was therefore skipped.

        Raises:
            ValueError: If `url` is blank or `depth` is negative.
        """
        if not url.strip():
            raise ValueError("url must not be blank")
        if depth < 0:
            raise ValueError("depth must be non-negative")

        if url in self._visited_urls:
            logger.debug("Skipping duplicate URL: %s", url)
            return False

        self._visited_urls.add(url)
        self._queue.append((url, depth))
        return True

    def dequeue(self) -> tuple[str, int] | None:
        """Remove and return the next (url, depth) pair from the BFS queue.

        Returns None if the queue is empty.
        """
        if not self._queue:
            return None
        return self._queue.popleft()

    def has_pending(self) -> bool:
        """Return True if there are URLs still waiting to be crawled."""
        return bool(self._queue)
