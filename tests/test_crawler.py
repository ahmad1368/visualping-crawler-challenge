"""Unit tests for the BFS traversal loop controller: crawler.crawl."""

import asyncio

import pytest

from crawler import crawl
from state import StateManager


def _run(coro):
    """Run an async coroutine synchronously, without depending on pytest-asyncio."""
    return asyncio.run(coro)


class RecordingProcessor:
    """Fake page processor that records call order and returns a fixed link graph."""

    def __init__(self, link_graph: dict[str, list[str]]) -> None:
        self._link_graph = link_graph
        self.calls: list[tuple[str, int]] = []

    async def __call__(self, url: str, depth: int) -> list[str]:
        self.calls.append((url, depth))
        return self._link_graph.get(url, [])


class TestCrawl:
    """Success and failure scenarios for crawl."""

    def test_processes_single_page_with_no_links(self):
        processor = RecordingProcessor({})
        state = _run(crawl("https://a.com", processor))
        assert processor.calls == [("https://a.com", 0)]
        assert state.visited_count == 1
        assert state.has_pending() is False

    def test_processes_pages_in_breadth_first_order(self):
        link_graph = {
            "https://a.com": ["https://b.com", "https://c.com"],
            "https://b.com": ["https://d.com"],
            "https://c.com": [],
            "https://d.com": [],
        }
        processor = RecordingProcessor(link_graph)
        state = _run(crawl("https://a.com", processor))

        assert processor.calls == [
            ("https://a.com", 0),
            ("https://b.com", 1),
            ("https://c.com", 1),
            ("https://d.com", 2),
        ]
        assert state.visited_count == 4

    def test_does_not_revisit_a_url_discovered_more_than_once(self):
        link_graph = {
            "https://a.com": ["https://b.com", "https://c.com"],
            "https://b.com": ["https://c.com"],
            "https://c.com": [],
        }
        processor = RecordingProcessor(link_graph)
        state = _run(crawl("https://a.com", processor))

        assert processor.calls.count(("https://c.com", 1)) == 1
        assert state.visited_count == 3

    def test_prevents_infinite_loop_on_cyclic_links(self):
        link_graph = {
            "https://a.com": ["https://b.com"],
            "https://b.com": ["https://a.com"],
        }
        processor = RecordingProcessor(link_graph)
        state = _run(crawl("https://a.com", processor))

        assert state.visited_count == 2
        assert processor.calls == [("https://a.com", 0), ("https://b.com", 1)]

    def test_respects_max_depth_boundary(self):
        link_graph = {
            "https://a.com": ["https://b.com"],
            "https://b.com": ["https://c.com"],
            "https://c.com": [],
        }
        processor = RecordingProcessor(link_graph)
        state = _run(crawl("https://a.com", processor, max_depth=1))

        assert ("https://c.com", 2) not in processor.calls
        assert state.visited_count == 2

    def test_continues_crawl_after_a_page_processor_error(self):
        async def flaky_processor(url: str, depth: int) -> list[str]:
            if url == "https://bad.com":
                raise RuntimeError("network error")
            if url == "https://a.com":
                return ["https://bad.com", "https://good.com"]
            return []

        state = _run(crawl("https://a.com", flaky_processor))

        assert state.is_visited("https://bad.com")
        assert state.is_visited("https://good.com")

    def test_uses_externally_provided_state(self):
        processor = RecordingProcessor({})
        state = StateManager()
        returned_state = _run(crawl("https://a.com", processor, state=state))
        assert returned_state is state

    def test_raises_on_blank_start_url(self):
        processor = RecordingProcessor({})
        with pytest.raises(ValueError):
            _run(crawl("   ", processor))
