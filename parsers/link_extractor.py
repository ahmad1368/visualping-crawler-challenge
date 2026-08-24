"""Structured HTML link extractor.

Parses raw HTML with BeautifulSoup, extracts every `<a href="...">` found
within the page body, and normalizes results into absolute, deduplicated
URLs ready for the BFS traversal queue (`state.py`) and link graph builder.
"""

from __future__ import annotations

import logging
from urllib.parse import urldefrag, urljoin

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def extract_links(html_body: str, base_url: str) -> list[str]:
    """Extract and normalize all `<a>` tag links from an HTML document.

    Parses `html_body` with BeautifulSoup and scans the `<body>` content
    (falling back to the full document for a bare HTML fragment with no
    `<body>` wrapper). Every `href` found on an `<a>` tag is resolved
    against `base_url` into a fully-qualified absolute URL, and its
    fragment (`#...`) is stripped, since a fragment identifies a position
    within a page rather than a distinct crawlable resource. Links with a
    missing, empty, or fragment-only `href` (e.g. `"#top"`) are skipped.
    Duplicate URLs (after normalization) are removed while preserving
    first-seen order.

    Raises ValueError if `base_url` is blank. Returns an empty list, and
    logs a warning, if `html_body` cannot be parsed.
    """
    if not base_url.strip():
        raise ValueError("base_url must not be blank")

    try:
        soup = BeautifulSoup(html_body, "html.parser")
    except Exception as exc:
        logger.warning("Failed to parse HTML for link extraction from %s: %s", base_url, exc)
        return []

    scope = soup.body or soup

    seen: set[str] = set()
    links: list[str] = []

    for anchor in scope.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith("#"):
            continue

        absolute_url, _fragment = urldefrag(urljoin(base_url, href))
        if not absolute_url or absolute_url in seen:
            continue

        seen.add(absolute_url)
        links.append(absolute_url)

    return links
