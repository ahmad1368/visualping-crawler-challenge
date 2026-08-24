"""Regex-based route finder for raw text, inline scripts, and code comments.

Scans non-tag text (page body text, inline/external JavaScript, HTML
comments) for relative route-like strings using the shared
`config.ROUTE_PATTERN`, filters out noise, and normalizes surviving
matches into absolute URLs ready for the BFS traversal queue.
"""

from __future__ import annotations

from urllib.parse import urljoin

import config

# Minimum length (in characters) a matched route must have to be considered
# meaningful; filters out a bare "/" and other near-empty matches.
MIN_ROUTE_LENGTH = 2


def find_routes(text: str, base_url: str) -> list[str]:
    """Find and normalize hidden route-like strings embedded in raw text.

    Scans `text` (raw HTML body text, inline/external JavaScript, or an
    HTML comment) with `config.ROUTE_PATTERN` for relative path-like
    substrings, then filters out matches that are noise rather than real
    endpoints (see `_is_relevant_route`). Surviving matches are resolved
    against `base_url` into absolute URLs, and duplicates are removed
    while preserving first-seen order.

    Raises ValueError if `base_url` is blank.
    """
    if not base_url.strip():
        raise ValueError("base_url must not be blank")

    seen: set[str] = set()
    routes: list[str] = []

    for match in config.ROUTE_PATTERN.finditer(text):
        candidate = match.group(0)
        if not _is_relevant_route(candidate):
            continue

        absolute_url = urljoin(base_url, candidate)
        if absolute_url in seen:
            continue

        seen.add(absolute_url)
        routes.append(absolute_url)

    return routes


def _is_relevant_route(candidate: str) -> bool:
    """Filter out regex matches that are noise rather than real endpoints.

    Rejects matches shorter than `MIN_ROUTE_LENGTH`, protocol-relative
    URLs (e.g. "//cdn.example.com", which are absolute, not relative
    routes), and matches made up entirely of "/" characters.
    """
    if len(candidate) < MIN_ROUTE_LENGTH:
        return False
    if candidate.startswith("//"):
        return False
    if candidate.strip("/") == "":
        return False
    return True
