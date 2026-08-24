"""Command-line entry point: run a full crawl and generate the HTML report.

Wires together the async HTTP client (`network.fetcher`), the BFS
traversal loop (`crawl.crawler`), the page-processing pipeline
(`crawl.pipeline`), incremental atomic persistence
(`storage.persistence`), and the HTML report generator (`ui.reporter`)
into a single runnable script.

Usage:
    python main.py [start_url] [--max-depth N] [--username USER --password PASS]

If `start_url` is omitted, `core.config.ROOT_URL` is used. `--username`/
`--password` enable HTTP Basic Auth on every request, for a target that
requires it.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Awaitable, Callable

import httpx

from core import config
from core.models import CrawledNode, Edge
from crawl.crawler import crawl
from crawl.pipeline import build_page_processor
from network.fetcher import create_http_client
from storage.persistence import ResultsWriter
from ui.reporter import DEFAULT_OUTPUT_PATH, generate_report

logger = logging.getLogger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the crawl entry point."""
    parser = argparse.ArgumentParser(
        description="Crawl a site for exposed secrets and generate an HTML report."
    )
    parser.add_argument(
        "start_url",
        nargs="?",
        default=config.ROOT_URL,
        help="URL to start crawling from (default: config.ROOT_URL).",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="Maximum BFS depth to crawl (default: unlimited).",
    )
    parser.add_argument(
        "--username",
        default=None,
        help="Username for HTTP Basic Auth, if the target requires it.",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Password for HTTP Basic Auth, if the target requires it.",
    )
    return parser.parse_args(argv)


async def run_crawl(
    start_url: str,
    *,
    max_depth: int | None = None,
    writer: ResultsWriter | None = None,
    client: httpx.AsyncClient | None = None,
    auth: httpx.Auth | tuple[str, str] | None = None,
    max_retries: int | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> ResultsWriter:
    """Run a full crawl of `start_url` and return the ResultsWriter that recorded it.

    Wires the pipeline's per-page outcome into both the results file and
    the link graph: `on_page_processed` records each visited page as a
    `CrawledNode` (url, depth, status code, whether a secret was found),
    and every link a page returns is recorded as an `Edge` before being
    handed back to `crawler.crawl` to enqueue. `writer.flush()` is called
    once more after the crawl completes, so the results file has full
    node/edge coverage even for a clean run that recorded zero secrets
    (which otherwise triggers no write at all -- see `ResultsWriter`).

    `client` is exposed for dependency injection (e.g. tests using
    `httpx.MockTransport`); when omitted, a real client is created via
    `fetcher.create_http_client` (with `auth`, if given, for a target
    requiring HTTP Basic Auth) and closed automatically. A caller-
    supplied `client`'s lifecycle remains the caller's responsibility,
    and `auth` is ignored in that case -- set it directly on the
    supplied client instead. `max_retries`/`sleep` are forwarded to
    `pipeline.build_page_processor` (and from there to
    `retry.fetch_with_retry`), for the same reason.
    """
    if writer is None:
        writer = ResultsWriter()

    def on_page_processed(
        url: str, depth: int, status_code: int | None, has_secret: bool
    ) -> None:
        writer.record_node(
            CrawledNode(url=url, depth=depth, status_code=status_code, has_secret=has_secret)
        )

    async def _crawl_with(active_client: httpx.AsyncClient) -> None:
        base_processor = build_page_processor(
            active_client,
            writer.record_secret,
            on_page_processed=on_page_processed,
            max_retries=max_retries,
            sleep=sleep,
        )

        async def processor(url: str, depth: int) -> list[str]:
            links = await base_processor(url, depth)
            for link in links:
                writer.record_edge(Edge(source=url, target=link))
            return links

        await crawl(start_url, processor, max_depth=max_depth)

    if client is not None:
        await _crawl_with(client)
    else:
        async with create_http_client(auth=auth) as owned_client:
            await _crawl_with(owned_client)

    # record_secret already flushes as it goes, but a crawl that finds
    # zero secrets never triggers a single write otherwise -- flush once
    # more here so its nodes/edges are always persisted.
    writer.flush()

    return writer


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: run the crawl, then generate the HTML report.

    Returns a process exit code (0 on success, 1 if report generation
    failed) rather than raising, so `python main.py` behaves like a
    normal command-line tool even when something goes wrong.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    args = _parse_args(argv)

    auth = httpx.BasicAuth(args.username, args.password) if args.username else None

    logger.info(
        "Starting crawl from %s (max_depth=%s, auth=%s)",
        args.start_url,
        args.max_depth,
        "enabled" if auth else "disabled",
    )
    writer = asyncio.run(run_crawl(args.start_url, max_depth=args.max_depth, auth=auth))
    logger.info(
        "Crawl finished: %d pages scanned, %d secrets found",
        writer.node_count,
        writer.secret_count,
    )

    if not generate_report():
        logger.error("Report generation failed; see warnings above.")
        return 1

    logger.info("Report written to %s", DEFAULT_OUTPUT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
