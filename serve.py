"""Local HTTP server entry point: serve the live secret-scan report.

Usage:
    python serve.py

Serves the report at http://localhost:<APP_PORT>/ (see
`core.config.APP_PORT`). Refreshing that page re-fetches the latest
persisted results from `GET /api/secrets`; clicking "Re-scan" in the
page triggers `POST /api/scan`, which runs a fresh crawl on demand
before returning updated results -- so live data is available without
re-running `python main.py` by hand for every scan.
"""

from __future__ import annotations

from ui.server import run_server

if __name__ == "__main__":
    run_server()
