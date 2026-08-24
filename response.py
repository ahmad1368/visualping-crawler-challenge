"""Raw network response wrapper for the crawler.

Wraps a single HTTP response returned by `fetcher`/`retry` into a
provider-agnostic snapshot (HTML body, response headers, cookies, status
code, and elapsed time), decoupling downstream parser modules (link
extraction, secret matching, HTML/header scanning) from `httpx.Response`
internals.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel, ConfigDict, field_validator


def _require_non_blank(value: str) -> str:
    """Raise ValueError if the given string is empty or whitespace-only."""
    if not value.strip():
        raise ValueError("must not be blank")
    return value


class RawResponse(BaseModel):
    """A provider-agnostic snapshot of a single completed HTTP response."""

    model_config = ConfigDict(frozen=True)

    url: str
    status_code: int
    html_body: str
    headers: dict[str, str]
    cookies: dict[str, str]
    elapsed_time: float

    @field_validator("url")
    @classmethod
    def _validate_url_not_blank(cls, value: str) -> str:
        """Reject empty or whitespace-only URLs."""
        return _require_non_blank(value)

    @field_validator("status_code")
    @classmethod
    def _validate_status_code_range(cls, value: int) -> int:
        """Reject status codes outside the valid HTTP range."""
        if not 100 <= value <= 599:
            raise ValueError("status_code must be between 100 and 599")
        return value

    @field_validator("elapsed_time")
    @classmethod
    def _validate_elapsed_time_non_negative(cls, value: float) -> float:
        """Reject negative elapsed times."""
        if value < 0:
            raise ValueError("elapsed_time must be non-negative")
        return value

    @classmethod
    def from_httpx_response(cls, response: httpx.Response) -> "RawResponse":
        """Build a RawResponse snapshot from a completed httpx.Response.

        Flattens `response.headers`/`response.cookies` into plain dicts and
        reads `response.elapsed` (time between sending the request and
        receiving the response), so downstream parser modules never need to
        depend on `httpx` types directly.
        """
        return cls(
            url=str(response.url),
            status_code=response.status_code,
            html_body=response.text,
            headers=dict(response.headers),
            cookies=dict(response.cookies),
            elapsed_time=response.elapsed.total_seconds(),
        )

    def get_header(self, name: str, default: str | None = None) -> str | None:
        """Case-insensitively look up a response header by name."""
        target = name.lower()
        for key, value in self.headers.items():
            if key.lower() == target:
                return value
        return default

    def get_cookie(self, name: str, default: str | None = None) -> str | None:
        """Look up a cookie value by name."""
        return self.cookies.get(name, default)
