"""Unit tests for the crawl entry point: main._parse_args/run_crawl/main."""

import asyncio

import httpx
import pytest

from core import config
from main import _parse_args, main, run_crawl
from storage.persistence import ResultsWriter


def _run(coro):
    """Run an async coroutine synchronously, without depending on pytest-asyncio."""
    return asyncio.run(coro)


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class TestParseArgs:
    """Success and failure scenarios for _parse_args."""

    def test_defaults_to_config_root_url(self):
        args = _parse_args([])
        assert args.start_url == config.ROOT_URL

    def test_accepts_a_positional_start_url(self):
        args = _parse_args(["https://custom.example.com"])
        assert args.start_url == "https://custom.example.com"

    def test_defaults_max_depth_to_none(self):
        args = _parse_args([])
        assert args.max_depth is None

    def test_accepts_max_depth_flag(self):
        args = _parse_args(["https://custom.example.com", "--max-depth", "2"])
        assert args.max_depth == 2

    def test_rejects_non_integer_max_depth(self):
        with pytest.raises(SystemExit):
            _parse_args(["https://custom.example.com", "--max-depth", "not-a-number"])


class TestRunCrawl:
    """Success and failure scenarios for run_crawl."""

    def test_records_a_node_for_the_start_page(self, tmp_path):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<p>Nothing sensitive here.</p>")

        async def scenario() -> ResultsWriter:
            writer = ResultsWriter(path=tmp_path / "results.json")
            async with _mock_client(handler) as client:
                return await run_crawl("https://example.com", writer=writer, client=client)

        writer = _run(scenario())
        assert writer.node_count == 1
        assert writer.secret_count == 0

    def test_follows_discovered_links_and_records_edges(self, tmp_path):
        def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url) == "https://example.com/":
                return httpx.Response(200, text='<a href="/child">child</a>')
            return httpx.Response(200, text="<p>leaf page</p>")

        async def scenario() -> ResultsWriter:
            writer = ResultsWriter(path=tmp_path / "results.json")
            async with _mock_client(handler) as client:
                return await run_crawl("https://example.com/", writer=writer, client=client)

        writer = _run(scenario())
        assert writer.node_count == 2

    def test_records_secret_and_flags_node(self, tmp_path):
        secret_value = "VISUALPING{0123456789abcdef}"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=f"<p>{secret_value}</p>")

        async def scenario() -> ResultsWriter:
            writer = ResultsWriter(path=tmp_path / "results.json")
            async with _mock_client(handler) as client:
                return await run_crawl("https://example.com", writer=writer, client=client)

        writer = _run(scenario())
        assert writer.secret_count == 1

    def test_respects_max_depth(self, tmp_path):
        # A -> B -> C chain: max_depth=1 should reach A (depth 0) and B
        # (depth 1), but never enqueue C (depth 2).
        pages = {
            "https://example.com/a": '<a href="/b">b</a>',
            "https://example.com/b": '<a href="/c">c</a>',
            "https://example.com/c": "leaf",
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=pages[str(request.url)])

        async def scenario() -> ResultsWriter:
            writer = ResultsWriter(path=tmp_path / "results.json")
            async with _mock_client(handler) as client:
                return await run_crawl(
                    "https://example.com/a", writer=writer, client=client, max_depth=1
                )

        writer = _run(scenario())
        assert writer.node_count == 2

    def test_records_node_with_none_status_when_fetch_fails(self, tmp_path):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        async def scenario() -> ResultsWriter:
            writer = ResultsWriter(path=tmp_path / "results.json")
            async with _mock_client(handler) as client:
                return await run_crawl(
                    "https://example.com",
                    writer=writer,
                    client=client,
                    max_retries=0,
                    sleep=lambda seconds: asyncio.sleep(0),
                )

        writer = _run(scenario())
        assert writer.node_count == 1
        assert writer.secret_count == 0


class TestMain:
    """Success and failure scenarios for the main() CLI entry point."""

    def test_returns_1_when_report_generation_fails(self, tmp_path, monkeypatch):
        async def fake_run_crawl(start_url, *, max_depth=None):
            return ResultsWriter(path=tmp_path / "local_data" / "results.json")

        import main as main_module

        monkeypatch.setattr(main_module, "run_crawl", fake_run_crawl)
        # Force generate_report's failure path directly, independent of
        # real filesystem state (ui.template.TEMPLATE_PATH is anchored to
        # the package's own location, so it can't be made "missing" by
        # just changing the working directory).
        monkeypatch.setattr(main_module, "generate_report", lambda: False)
        exit_code = main(["https://example.com"])
        assert exit_code == 1
