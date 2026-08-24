"""In-memory link graph builder for the crawler's traversal.

Tracks parent-child (source -> target) relationships between crawled URLs
as `Edge` records, preventing the same edge from being recorded twice no
matter how many times the crawl rediscovers the same link.
"""

from __future__ import annotations

import logging

from models import Edge

logger = logging.getLogger(__name__)


class LinkGraph:
    """Centralized, in-memory link graph for a single crawl execution.

    Stores discovered links as `Edge(source, target)` records in a set,
    giving O(1) duplicate detection regardless of how many times the crawl
    encounters the same source/target pair.
    """

    def __init__(self) -> None:
        self._edges: set[Edge] = set()

    @property
    def edge_count(self) -> int:
        """Number of distinct edges recorded so far."""
        return len(self._edges)

    def add_edge(self, source: str, target: str) -> bool:
        """Record a source -> target link if it has not been seen before.

        Returns True if a new edge was recorded, False if it was a
        duplicate and was therefore skipped.

        Raises:
            ValidationError: If `source` or `target` is blank, via `Edge`'s
                own field validation.
        """
        edge = Edge(source=source, target=target)
        if edge in self._edges:
            logger.debug("Skipping duplicate edge: %s -> %s", source, target)
            return False

        self._edges.add(edge)
        return True

    def get_edges(self) -> list[Edge]:
        """Return all recorded edges as a list, in no guaranteed order."""
        return list(self._edges)
