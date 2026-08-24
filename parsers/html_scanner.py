"""HTML body and comments scanner.

Scans a parsed HTML document for embedded secrets in two distinct
locations: the page's rendered/visible body text, and its HTML comments
(`<!-- ... -->`), recording the precise discovery location on each
`Secret` found.
"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup, Comment

from core.models import Secret, SecretLocation
from parsers.secret_finder import find_secrets

logger = logging.getLogger(__name__)


def scan_html(html_body: str, url: str) -> list[Secret]:
    """Scan an HTML document's visible body text and comments for secrets.

    Parses `html_body` with BeautifulSoup and runs `secret_finder.find_secrets`
    over two distinct pieces of text: the page's rendered/visible text
    (tagged `SecretLocation.HTML_BODY`) and the concatenated content of
    every HTML comment (tagged `SecretLocation.HTML_COMMENT`).

    `soup.get_text()` already excludes `<script>`/`<style>` content and
    comment nodes (BeautifulSoup tags them internally as non-navigable
    text), so it reflects exactly what a user would see rendered on the
    page, without double-counting a secret found inside a comment.

    Returns an empty list, and logs a warning, if `html_body` cannot be
    parsed.
    """
    try:
        soup = BeautifulSoup(html_body, "html.parser")
    except Exception as exc:
        logger.warning("Failed to parse HTML for secret scanning from %s: %s", url, exc)
        return []

    secrets = find_secrets(soup.get_text(), url=url, location=SecretLocation.HTML_BODY)

    comment_text = "\n".join(soup.find_all(string=lambda node: isinstance(node, Comment)))
    secrets += find_secrets(comment_text, url=url, location=SecretLocation.HTML_COMMENT)

    return secrets
