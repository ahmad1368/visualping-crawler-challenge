"""Data loader and recovery module for the crawler's results file.

Reads and validates `local_data/results.json` back into a `CrawlReport`,
giving the HTML rendering and reporting layers a single, always-valid
entry point that never raises for a missing, empty, or corrupted file.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from exporter import CrawlReport, build_report
from persistence import DEFAULT_RESULTS_PATH

logger = logging.getLogger(__name__)


def load_results(path: Path | str = DEFAULT_RESULTS_PATH) -> CrawlReport:
    """Load and validate the crawl results file into a CrawlReport.

    Returns an empty CrawlReport (all lists empty, both summary
    timestamps set to the current time) rather than raising, for every
    recoverable failure case: the file does not exist, cannot be read,
    is empty, holds invalid JSON, or holds JSON that does not match the
    CrawlReport schema. Each such case is logged so the underlying cause
    stays visible, without ever interrupting a caller such as the HTML
    report generator.
    """
    path = Path(path)

    if not path.exists():
        logger.info("Results file %s does not exist; returning an empty report.", path)
        return _empty_report()

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to read results file %s: %s", path, exc)
        return _empty_report()

    if not raw_text.strip():
        logger.warning("Results file %s is empty; returning an empty report.", path)
        return _empty_report()

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning("Results file %s contains invalid JSON: %s", path, exc)
        return _empty_report()

    try:
        return CrawlReport.model_validate(data)
    except ValidationError as exc:
        logger.warning("Results file %s does not match the expected schema: %s", path, exc)
        return _empty_report()


def _empty_report() -> CrawlReport:
    """Build a schema-valid CrawlReport with no results, for recovery paths."""
    now = datetime.now(timezone.utc)
    return build_report(secrets=[], nodes=[], edges=[], start_time=now, end_time=now)
