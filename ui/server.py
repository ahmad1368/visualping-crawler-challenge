"""Local HTTP server for live secret-scan reporting.

Wraps the existing static report generator (`ui.reporter`) and crawl
entry point (`main.run_crawl`) in a small `aiohttp` app so the report
page can be served live instead of only via `python main.py`:

- `GET /` serves the current report page (generating it first if it
  does not exist yet).
- `GET /api/secrets` returns the latest persisted results as JSON, for
  the page's client-side script to refresh its KPI cards, secrets
  table, and link graph without a full reload.
- `POST /api/scan` runs a fresh crawl of `core.config.ROOT_URL` on
  demand, regenerates the report page, and returns the updated results
  -- this is the only route that triggers new outbound network
  requests; visiting or refreshing `/` on its own only reads the
  latest already-persisted results.

Also applies `_cors_middleware` to the two `/api/*` routes, since the
generated `index.html` is a static file that can end up served by
something other than this app (e.g. an editor's static preview server
on a different port) while its client-side script still calls back
into this API -- a cross-origin request the browser will only allow
once this server sends back a matching `Access-Control-Allow-Origin`.
"""

from __future__ import annotations

import logging
import re

from aiohttp import web

from core import config
from main import run_crawl
from storage.data_loader import load_results
from ui.reporter import DEFAULT_OUTPUT_PATH, build_report_payload, generate_report

logger = logging.getLogger(__name__)

# Matches an `Origin` header from a browser tab served over plain HTTP from
# the local machine, regardless of port (e.g. an editor's static preview
# server) -- the only kind of cross-origin caller this local dev tool grants
# access to.
_LOCAL_ORIGIN_PATTERN = re.compile(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$")


@web.middleware
async def _cors_middleware(request: web.Request, handler):
    """Allow cross-origin `/api/*` requests from another local dev server.

    The generated report page is a static file and may be previewed via
    something other than this app (see module docstring), so its own
    origin won't always match this server's. Reflects the request's
    `Origin` back as `Access-Control-Allow-Origin` when it's a plain-HTTP
    localhost/127.0.0.1 origin (any port); every other origin is left
    without the header, so the browser's default same-origin policy
    still applies.
    """
    response = await handler(request)

    origin = request.headers.get("Origin")
    if origin and _LOCAL_ORIGIN_PATTERN.match(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"

    return response


async def handle_index(request: web.Request) -> web.Response:
    """Regenerate the report page from the latest persisted results, then serve it.

    Regenerating on every request only re-renders from the already-
    persisted `local_data/results.json` (cheap, no network I/O), so a
    plain browser refresh always reflects the latest results even
    before the page's own client-side fetch runs. It does not trigger a
    new crawl -- that only happens via the explicit `POST /api/scan`.
    """
    generate_report()

    if not DEFAULT_OUTPUT_PATH.exists():
        return web.Response(status=404, text="Report not generated yet.")

    return web.Response(
        text=DEFAULT_OUTPUT_PATH.read_text(encoding="utf-8"), content_type="text/html"
    )


async def handle_api_secrets(request: web.Request) -> web.Response:
    """Return the latest persisted crawl results as JSON."""
    return web.json_response(build_report_payload(load_results()))


async def handle_api_scan(request: web.Request) -> web.Response:
    """Run a fresh crawl on demand, regenerate the report page, and return the updated results.

    Runs synchronously and awaits the full crawl before responding,
    since this endpoint is only ever triggered by an explicit user
    action (e.g. a "Re-scan" button), not by every page load/refresh.
    """
    try:
        await run_crawl(config.ROOT_URL)
    except Exception as exc:
        logger.error("On-demand scan failed: %s", exc)
        return web.json_response({"error": "Scan failed; see server logs."}, status=500)

    generate_report()
    return web.json_response(build_report_payload(load_results()))


def create_app() -> web.Application:
    """Build the aiohttp application with the report page and API routes registered."""
    app = web.Application(middlewares=[_cors_middleware])
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/secrets", handle_api_secrets)
    app.router.add_post("/api/scan", handle_api_scan)
    return app


def run_server() -> None:
    """Start the live reporting server on `core.config.APP_PORT`."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    web.run_app(create_app(), port=config.APP_PORT)
