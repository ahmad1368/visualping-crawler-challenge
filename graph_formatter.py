"""Graph data formatter for vis-network visualization.

Transforms the crawl report's `CrawledNode`/`Edge` records into the plain
node/edge array structures vis-network expects, assigning each node a
unique id, a shortened URL label, a full-detail tooltip title, and a
visual highlight for any node where a secret was discovered.
"""

from __future__ import annotations

from urllib.parse import urlparse

from exporter import CrawlReport
from models import CrawledNode, Edge

# Maximum characters kept in a node label before truncating it with an
# ellipsis, to keep vis-network's rendered labels readable at the default
# zoom level.
MAX_LABEL_LENGTH = 30

# vis-network node colors: rose to flag a node with a discovered secret,
# sky for every other node.
SECRET_NODE_COLOR = "#f43f5e"
DEFAULT_NODE_COLOR = "#38bdf8"


def format_graph_data(report: CrawlReport) -> dict:
    """Convert a CrawlReport's nodes/edges into vis-network's array structures.

    Returns a dict with `"nodes"` and `"edges"` keys, ready to hand
    directly to vis-network's `DataSet` constructors (e.g.
    `new vis.DataSet(data.nodes)`). A node is flagged as containing a
    secret if either its own `has_secret` field is set, or its URL
    matches one of `report.secrets`' URLs -- combining both keeps this
    formatter correct even if a node was persisted before its
    `has_secret` flag was set upstream.
    """
    secret_urls = {secret.url for secret in report.secrets}

    return {
        "nodes": [
            _format_node(node, has_secret=node.has_secret or node.url in secret_urls)
            for node in report.nodes
        ],
        "edges": [_format_edge(edge) for edge in report.edges],
    }


def _format_node(node: CrawledNode, *, has_secret: bool) -> dict:
    """Build a single vis-network node entry from a CrawledNode."""
    return {
        "id": node.url,
        "label": _shorten_url(node.url),
        "title": _build_tooltip(node, has_secret=has_secret),
        "color": SECRET_NODE_COLOR if has_secret else DEFAULT_NODE_COLOR,
    }


def _format_edge(edge: Edge) -> dict:
    """Build a single vis-network edge entry from an Edge."""
    return {"from": edge.source, "to": edge.target}


def _shorten_url(url: str) -> str:
    """Shorten a URL to a compact, human-readable node label.

    Strips the scheme and shows `host + path`, truncated with an
    ellipsis if it still exceeds `MAX_LABEL_LENGTH`.
    """
    parsed = urlparse(url)
    display = f"{parsed.netloc}{parsed.path}" or url
    if len(display) <= MAX_LABEL_LENGTH:
        return display
    return display[: MAX_LABEL_LENGTH - 1] + "…"


def _build_tooltip(node: CrawledNode, *, has_secret: bool) -> str:
    """Build the full-detail tooltip text shown on node hover."""
    lines = [node.url, f"Depth: {node.depth}"]
    if node.status_code is not None:
        lines.append(f"Status: {node.status_code}")
    if has_secret:
        lines.append("Secret discovered")
    return "\n".join(lines)
