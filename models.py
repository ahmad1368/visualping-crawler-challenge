"""Data models for the Visualping crawler: discovered secrets and the link graph.

All models are Pydantic BaseModels for automatic validation and easy JSON
serialization (used by the exporter module). Graph models (CrawledNode, Edge)
are frozen so they can be stored in sets/dicts for O(1) deduplication.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _require_non_blank(value: str) -> str:
    """Raise ValueError if the given string is empty or whitespace-only."""
    if not value.strip():
        raise ValueError("must not be blank")
    return value


class SecretLocation(str, Enum):
    """Where a secret was discovered within a crawled page."""

    HTML_BODY = "html_body"
    HTML_COMMENT = "html_comment"
    HTTP_HEADER = "http_header"
    COOKIE = "cookie"
    SCRIPT = "script"


class Secret(BaseModel):
    """A single secret discovered during crawling, with context for review."""

    value: str
    url: str
    location: SecretLocation
    snippet: str
    found_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("value", "url")
    @classmethod
    def _validate_not_blank(cls, value: str) -> str:
        """Reject empty or whitespace-only secret values and URLs."""
        return _require_non_blank(value)


class CrawledNode(BaseModel):
    """A single page visited by the crawler, represented as a graph node."""

    model_config = ConfigDict(frozen=True)

    url: str
    depth: int = 0
    status_code: int | None = None
    has_secret: bool = False

    @field_validator("url")
    @classmethod
    def _validate_url_not_blank(cls, value: str) -> str:
        """Reject empty or whitespace-only URLs."""
        return _require_non_blank(value)

    @field_validator("depth")
    @classmethod
    def _validate_depth_non_negative(cls, value: int) -> int:
        """Reject negative BFS depth values."""
        if value < 0:
            raise ValueError("depth must be non-negative")
        return value


class Edge(BaseModel):
    """A directed link (source -> target) between two crawled pages."""

    model_config = ConfigDict(frozen=True)

    source: str
    target: str

    @field_validator("source", "target")
    @classmethod
    def _validate_not_blank(cls, value: str) -> str:
        """Reject empty or whitespace-only URLs."""
        return _require_non_blank(value)
