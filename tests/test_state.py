"""Unit tests for the StateManager class: BFS queue and visited-URL tracking."""

import pytest

from state import StateManager


class TestEnqueue:
    """Success and failure scenarios for StateManager.enqueue."""

    def test_enqueues_new_url(self):
        state = StateManager()
        assert state.enqueue("https://example.com", depth=0) is True
        assert state.pending_count == 1
        assert state.visited_count == 1

    def test_skips_duplicate_url(self):
        state = StateManager()
        state.enqueue("https://example.com")
        assert state.enqueue("https://example.com") is False
        assert state.pending_count == 1
        assert state.visited_count == 1

    def test_prevents_cycle_via_visited_set(self):
        state = StateManager()
        state.enqueue("https://a.com", depth=0)
        state.dequeue()
        assert state.enqueue("https://a.com", depth=1) is False

    def test_rejects_blank_url(self):
        state = StateManager()
        with pytest.raises(ValueError):
            state.enqueue("   ")

    def test_rejects_negative_depth(self):
        state = StateManager()
        with pytest.raises(ValueError):
            state.enqueue("https://example.com", depth=-1)


class TestDequeue:
    """Success and failure scenarios for StateManager.dequeue."""

    def test_dequeues_in_fifo_order(self):
        state = StateManager()
        state.enqueue("https://a.com", depth=0)
        state.enqueue("https://b.com", depth=1)
        assert state.dequeue() == ("https://a.com", 0)
        assert state.dequeue() == ("https://b.com", 1)

    def test_dequeue_empty_queue_returns_none(self):
        state = StateManager()
        assert state.dequeue() is None


class TestStateInspection:
    """Success scenarios for the is_visited/has_pending inspection helpers."""

    def test_is_visited_reflects_enqueued_urls(self):
        state = StateManager()
        assert state.is_visited("https://example.com") is False
        state.enqueue("https://example.com")
        assert state.is_visited("https://example.com") is True

    def test_has_pending_reflects_queue_state(self):
        state = StateManager()
        assert state.has_pending() is False
        state.enqueue("https://example.com")
        assert state.has_pending() is True
        state.dequeue()
        assert state.has_pending() is False
