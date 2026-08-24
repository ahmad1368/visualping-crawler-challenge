"""Headers, cookies, and script/asset content scanner.

Scans HTTP response headers, cookies, and script content (inline
`<script>` tags or the already-fetched body of a linked JS/CSS asset)
for embedded secrets, recording the exact header name or cookie key that
carried the secret directly in the finding's context snippet.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from core.models import Secret, SecretLocation
from parsers.secret_finder import find_secrets


def scan_headers(headers: dict[str, str], url: str) -> list[Secret]:
    """Scan HTTP response headers (including Set-Cookie) for embedded secrets.

    Each header is scanned as `"<name>: <value>"`, so a discovered
    secret's snippet naturally captures which header name carried it.
    """
    secrets: list[Secret] = []
    for name, value in headers.items():
        secrets += find_secrets(
            f"{name}: {value}", url=url, location=SecretLocation.HTTP_HEADER
        )
    return secrets


def scan_cookies(cookies: dict[str, str], url: str) -> list[Secret]:
    """Scan response cookies for embedded secrets.

    Each cookie is scanned as `"<key>=<value>"`, so a discovered secret's
    snippet naturally captures which cookie key carried it.
    """
    secrets: list[Secret] = []
    for key, value in cookies.items():
        secrets += find_secrets(f"{key}={value}", url=url, location=SecretLocation.COOKIE)
    return secrets


def scan_script(script_text: str, url: str) -> list[Secret]:
    """Scan raw JavaScript/CSS text for embedded secrets.

    Used both for inline `<script>` tag content (via
    `scan_inline_scripts`) and for the already-fetched body of a linked
    JS/CSS asset. Fetching the asset itself is the caller's
    responsibility (via `fetcher`/`retry`); this function only scans
    already-retrieved text.
    """
    return find_secrets(script_text, url=url, location=SecretLocation.SCRIPT)


def scan_inline_scripts(html_body: str, url: str) -> list[Secret]:
    """Scan every inline `<script>` tag's content for embedded secrets."""
    soup = BeautifulSoup(html_body, "html.parser")
    script_text = "\n".join(script.get_text() for script in soup.find_all("script"))
    return scan_script(script_text, url=url)
