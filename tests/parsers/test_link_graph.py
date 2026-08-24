"""Unit tests for the LinkGraph class: edge tracking and duplicate prevention."""

import pytest
from pydantic import ValidationError

from core.models import Edge
from parsers.link_graph import LinkGraph


class TestAddEdge:
    """Success and failure scenarios for LinkGraph.add_edge."""

    def test_adds_new_edge(self):
        graph = LinkGraph()
        assert graph.add_edge("https://a.com", "https://b.com") is True
        assert graph.edge_count == 1

    def test_skips_duplicate_edge(self):
        graph = LinkGraph()
        graph.add_edge("https://a.com", "https://b.com")
        assert graph.add_edge("https://a.com", "https://b.com") is False
        assert graph.edge_count == 1

    def test_treats_reversed_direction_as_distinct_edge(self):
        graph = LinkGraph()
        graph.add_edge("https://a.com", "https://b.com")
        assert graph.add_edge("https://b.com", "https://a.com") is True
        assert graph.edge_count == 2

    def test_tracks_multiple_children_of_same_source(self):
        graph = LinkGraph()
        graph.add_edge("https://a.com", "https://b.com")
        graph.add_edge("https://a.com", "https://c.com")
        assert graph.edge_count == 2

    def test_rejects_blank_source(self):
        graph = LinkGraph()
        with pytest.raises(ValidationError):
            graph.add_edge("   ", "https://b.com")

    def test_rejects_blank_target(self):
        graph = LinkGraph()
        with pytest.raises(ValidationError):
            graph.add_edge("https://a.com", "")


class TestGetEdges:
    """Success scenarios for LinkGraph.get_edges."""

    def test_returns_empty_list_for_empty_graph(self):
        graph = LinkGraph()
        assert graph.get_edges() == []

    def test_returns_recorded_edges(self):
        graph = LinkGraph()
        graph.add_edge("https://a.com", "https://b.com")
        edges = graph.get_edges()
        assert edges == [Edge(source="https://a.com", target="https://b.com")]

    def test_does_not_duplicate_edges_in_returned_list(self):
        graph = LinkGraph()
        graph.add_edge("https://a.com", "https://b.com")
        graph.add_edge("https://a.com", "https://b.com")
        assert len(graph.get_edges()) == 1
