"""Regex-based route finder for raw text, inline scripts, and code comments.

Scans non-tag text (page body text, inline/external JavaScript, HTML
comments) for relative route-like strings using the shared
`config.ROUTE_PATTERN`, filters out noise, and normalizes surviving
matches into absolute URLs ready for the BFS traversal queue.
"""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup, Comment

from core import config

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


def find_routes_in_html(html_body: str, base_url: str) -> list[str]:
    """Find hidden routes embedded in an HTML document's non-tag text.

    `find_routes` operates on plain text; calling it directly against
    raw HTML markup is unsafe, since HTML tags themselves can produce
    false matches (e.g. a closing tag like `</a>` matches the route
    pattern as `/a`, since the pattern has no way to know it is looking
    at markup rather than a path). This wrapper first extracts the
    document's visible body text, every inline `<script>` tag's content,
    and every HTML comment via BeautifulSoup -- the same non-tag
    surfaces `html_scanner`/`asset_scanner` scan for secrets -- and runs
    `find_routes` over their combined text instead.
    """
    soup = BeautifulSoup(html_body, "html.parser")

    script_text = "\n".join(script.get_text() for script in soup.find_all("script"))
    comment_text = "\n".join(soup.find_all(string=lambda node: isinstance(node, Comment)))
    body_text = soup.get_text()

    combined_text = "\n".join([body_text, script_text, comment_text])
    return find_routes(combined_text, base_url)


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
