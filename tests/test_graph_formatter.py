"""Unit tests for the vis-network graph formatter: graph_formatter.format_graph_data."""

from datetime import datetime, timezone

from exporter import build_report
from graph_formatter import (
    DEFAULT_NODE_COLOR,
    MAX_LABEL_LENGTH,
    SECRET_NODE_COLOR,
    format_graph_data,
)
from models import CrawledNode, Edge, Secret, SecretLocation

START = datetime(2026, 8, 23, 10, 0, 0, tzinfo=timezone.utc)
END = START


def _report(secrets=None, nodes=None, edges=None):
    return build_report(
        secrets=secrets or [], nodes=nodes or [], edges=edges or [], start_time=START, end_time=END
    )


class TestFormatGraphData:
    """Success and failure scenarios for format_graph_data."""

    def test_returns_empty_arrays_for_empty_report(self):
        data = format_graph_data(_report())
        assert data == {"nodes": [], "edges": []}

    def test_assigns_node_id_as_url(self):
        node = CrawledNode(url="https://example.com/page", depth=0)
        data = format_graph_data(_report(nodes=[node]))
        assert data["nodes"][0]["id"] == "https://example.com/page"

    def test_shortens_label_from_url(self):
        node = CrawledNode(url="https://example.com/page", depth=0)
        data = format_graph_data(_report(nodes=[node]))
        assert data["nodes"][0]["label"] == "example.com/page"

    def test_truncates_long_labels_with_ellipsis(self):
        long_path = "/" + "a" * 50
        node = CrawledNode(url=f"https://example.com{long_path}", depth=0)
        data = format_graph_data(_report(nodes=[node]))
        label = data["nodes"][0]["label"]
        assert len(label) == MAX_LABEL_LENGTH
        assert label.endswith("…")

    def test_tooltip_title_includes_full_url_and_depth(self):
        node = CrawledNode(url="https://example.com/page", depth=2, status_code=200)
        data = format_graph_data(_report(nodes=[node]))
        title = data["nodes"][0]["title"]
        assert "https://example.com/page" in title
        assert "Depth: 2" in title
        assert "Status: 200" in title

    def test_flags_node_via_own_has_secret_field(self):
        node = CrawledNode(url="https://example.com/page", depth=0, has_secret=True)
        data = format_graph_data(_report(nodes=[node]))
        assert data["nodes"][0]["color"] == SECRET_NODE_COLOR
        assert "Secret discovered" in data["nodes"][0]["title"]

    def test_flags_node_via_matching_secret_url(self):
        node = CrawledNode(url="https://example.com/page", depth=0, has_secret=False)
        secret = Secret(
            value="VISUALPING{0123456789abcdef}",
            url="https://example.com/page",
            location=SecretLocation.HTML_BODY,
            snippet="ctx",
        )
        data = format_graph_data(_report(secrets=[secret], nodes=[node]))
        assert data["nodes"][0]["color"] == SECRET_NODE_COLOR

    def test_does_not_flag_node_without_a_secret(self):
        node = CrawledNode(url="https://example.com/page", depth=0)
        data = format_graph_data(_report(nodes=[node]))
        assert data["nodes"][0]["color"] == DEFAULT_NODE_COLOR
        assert "Secret discovered" not in data["nodes"][0]["title"]

    def test_formats_edges_with_from_and_to_keys(self):
        edge = Edge(source="https://a.com", target="https://b.com")
        data = format_graph_data(_report(edges=[edge]))
        assert data["edges"] == [{"from": "https://a.com", "to": "https://b.com"}]

    def test_edge_endpoints_match_node_ids(self):
        node_a = CrawledNode(url="https://a.com", depth=0)
        node_b = CrawledNode(url="https://b.com", depth=1)
        edge = Edge(source="https://a.com", target="https://b.com")
        data = format_graph_data(_report(nodes=[node_a, node_b], edges=[edge]))
        node_ids = {n["id"] for n in data["nodes"]}
        assert data["edges"][0]["from"] in node_ids
        assert data["edges"][0]["to"] in node_ids

    def test_formats_multiple_nodes_and_edges(self):
        nodes = [CrawledNode(url=f"https://example.com/{i}", depth=0) for i in range(3)]
        edges = [
            Edge(source="https://example.com/0", target="https://example.com/1"),
            Edge(source="https://example.com/1", target="https://example.com/2"),
        ]
        data = format_graph_data(_report(nodes=nodes, edges=edges))
        assert len(data["nodes"]) == 3
        assert len(data["edges"]) == 2
