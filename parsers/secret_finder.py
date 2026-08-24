"""Regex-based secret snippet extractor.

Scans raw text for `VISUALPING{...}` secret tokens using the shared
`config.SECRET_PATTERN`, and captures a sanitized snippet of surrounding
context for reviewer visibility in the generated report.
"""

from __future__ import annotations

import re

from core import config
from core.models import Secret, SecretLocation

# Number of characters of surrounding context to capture on each side of a
# matched secret.
SNIPPET_CONTEXT_CHARS = 30

# Collapses runs of whitespace (including invisible/control whitespace such
# as tabs, newlines, and non-breaking spaces) into a single space.
_WHITESPACE_PATTERN = re.compile(r"\s+")


def find_secrets(text: str, url: str, location: SecretLocation) -> list[Secret]:
    """Find every VISUALPING secret token embedded in raw text.

    Scans `text` with `config.SECRET_PATTERN`. For each match, captures a
    sanitized snippet spanning up to `SNIPPET_CONTEXT_CHARS` characters of
    context on either side of the matched value (clamped to the bounds of
    `text`), with runs of whitespace and invisible characters collapsed to
    single spaces and leading/trailing whitespace trimmed.

    `url` and `location` are attached to every returned `Secret` so callers
    can trace a finding back to the page and part of the response it came
    from.
    """
    secrets: list[Secret] = []

    for match in config.SECRET_PATTERN.finditer(text):
        start = max(0, match.start() - SNIPPET_CONTEXT_CHARS)
        end = min(len(text), match.end() + SNIPPET_CONTEXT_CHARS)
        snippet = _sanitize(text[start:end])

        secrets.append(
            Secret(value=match.group(0), url=url, location=location, snippet=snippet)
        )

    return secrets


def _sanitize(snippet: str) -> str:
    """Collapse whitespace/invisible characters and trim snippet edges."""
    return _WHITESPACE_PATTERN.sub(" ", snippet).strip()
