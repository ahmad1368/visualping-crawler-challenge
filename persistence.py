"""Incremental, atomic JSON persistence for the crawler's results.

Writes the crawl report to `local_data/results.json` using a
write-to-temp-then-replace pattern, so a crash or interruption mid-write
never leaves a corrupted or partially-written results file on disk. The
`ResultsWriter` class flushes the full report immediately whenever a new
secret is recorded, so findings already on disk survive an interrupted
crawl.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from exporter import build_report
from models import CrawledNode, Edge, Secret

logger = logging.getLogger(__name__)

DEFAULT_RESULTS_PATH = Path("local_data") / "results.json"


def write_text_atomic(content: str, path: Path | str = DEFAULT_RESULTS_PATH) -> bool:
    """Atomically write `content` as UTF-8 text to `path`.

    Creates `path`'s parent directory if it does not already exist.
    Writes to a temporary file in that same directory first, then
    replaces `path` with it via `os.replace`, which is atomic on both
    POSIX and Windows as long as source and destination share a
    filesystem/drive (guaranteed here since the temp file lives in
    `path`'s own parent directory). As a result, a crash mid-write can
    never leave `path` truncated or corrupted: it is either the previous
    complete file or the new complete file, never something in between.

    Returns True on success. On any failure (e.g. a permissions error),
    logs the error, cleans up the temporary file, and returns False
    rather than raising, so a single failed save never crashes the crawl.
    """
    path = Path(path)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=path.parent)
    except OSError as exc:
        logger.error("Failed to prepare temporary file for %s: %s", path, exc)
        return False

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(content)
        os.replace(tmp_path, path)
    except OSError as exc:
        logger.error("Failed to write to %s: %s", path, exc)
        os.remove(tmp_path)
        return False

    return True


def write_json_atomic(data: dict, path: Path | str = DEFAULT_RESULTS_PATH) -> bool:
    """Atomically write `data` as JSON to `path`.

    Serializes `data` to a JSON string first, so a serialization failure
    (e.g. an unserializable type) is caught before anything ever touches
    disk, then delegates to `write_text_atomic` for the actual atomic
    write. Returns False, and logs the error, if `data` cannot be
    serialized, rather than raising.
    """
    try:
        content = json.dumps(data, indent=2)
    except (TypeError, ValueError) as exc:
        logger.error("Failed to serialize results for %s: %s", path, exc)
        return False

    return write_text_atomic(content, path=path)


class ResultsWriter:
    """Incrementally persists crawl results to a JSON results file.

    Accumulates discovered secrets, visited nodes, and link graph edges
    in memory, and atomically rewrites the entire results file every
    time `record_secret` is called, so a secret found midway through a
    long crawl is already durable on disk before the crawl continues.
    """

    def __init__(self, path: Path | str = DEFAULT_RESULTS_PATH) -> None:
        self._path = Path(path)
        self._secrets: list[Secret] = []
        self._nodes: list[CrawledNode] = []
        self._edges: list[Edge] = []
        self._start_time = datetime.now(timezone.utc)

    def record_secret(self, secret: Secret) -> bool:
        """Record a newly discovered secret and persist the results file immediately."""
        self._secrets.append(secret)
        return self._flush()

    def record_node(self, node: CrawledNode) -> None:
        """Record a visited page as a graph node, without triggering a flush."""
        self._nodes.append(node)

    def record_edge(self, edge: Edge) -> None:
        """Record a discovered link as a graph edge, without triggering a flush."""
        self._edges.append(edge)

    def _flush(self) -> bool:
        """Atomically write the current in-memory results to disk."""
        report = build_report(
            secrets=self._secrets,
            nodes=self._nodes,
            edges=self._edges,
            start_time=self._start_time,
            end_time=datetime.now(timezone.utc),
        )
        return write_json_atomic(report.to_json_dict(), path=self._path)
