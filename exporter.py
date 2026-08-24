"""Output JSON schema and report model for the crawler's final results.

Defines the top-level report shape (`secrets`, `nodes`, `edges`, and
`summary`) written to `local_data/results.json`, and the serialization
method that turns it into a JSON-ready dictionary. Atomically writing
that dictionary to disk is a separate concern, handled by a dedicated
persistence module.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from models import CrawledNode, Edge, Secret


class CrawlSummary(BaseModel):
    """Execution metadata for a single crawl run."""

    start_time: datetime
    end_time: datetime
    total_pages_scanned: int
    total_secrets_found: int

    @model_validator(mode="after")
    def _validate(self) -> "CrawlSummary":
        """Reject negative counts and an end time before the start time."""
        if self.total_pages_scanned < 0:
            raise ValueError("total_pages_scanned must be non-negative")
        if self.total_secrets_found < 0:
            raise ValueError("total_secrets_found must be non-negative")
        if self.end_time < self.start_time:
            raise ValueError("end_time must not be before start_time")
        return self


class CrawlReport(BaseModel):
    """Top-level crawl report: discovered secrets, the link graph, and summary metadata."""

    secrets: list[Secret] = Field(default_factory=list)
    nodes: list[CrawledNode] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    summary: CrawlSummary

    def to_json_dict(self) -> dict:
        """Serialize this report into a JSON-ready dictionary.

        Uses Pydantic's `model_dump(mode="json")` so nested types that are
        not natively JSON-serializable (datetimes, enums) are converted to
        their JSON-safe representations (ISO-8601 strings, plain enum
        values) up front, leaving callers free to pass the result straight
        to `json.dumps`.
        """
        return self.model_dump(mode="json")


def build_report(
    *,
    secrets: list[Secret],
    nodes: list[CrawledNode],
    edges: list[Edge],
    start_time: datetime,
    end_time: datetime,
) -> CrawlReport:
    """Assemble a CrawlReport from crawl results, deriving summary counts.

    `total_pages_scanned`/`total_secrets_found` are computed from `nodes`
    and `secrets` themselves, rather than accepted as separate arguments,
    so the summary can never drift out of sync with the actual result
    lists.
    """
    summary = CrawlSummary(
        start_time=start_time,
        end_time=end_time,
        total_pages_scanned=len(nodes),
        total_secrets_found=len(secrets),
    )
    return CrawlReport(secrets=secrets, nodes=nodes, edges=edges, summary=summary)
