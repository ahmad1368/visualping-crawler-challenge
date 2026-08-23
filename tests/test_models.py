"""Unit tests for the data models: Secret, CrawledNode, and Edge."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from models import CrawledNode, Edge, Secret, SecretLocation


class TestSecret:
    """Success and failure scenarios for the Secret model."""

    def test_creates_with_required_fields(self):
        secret = Secret(
            value="VISUALPING{0123456789abcdef}",
            url="https://example.com/page",
            location=SecretLocation.HTML_BODY,
            snippet="...before VISUALPING{0123456789abcdef} after...",
        )
        assert secret.value == "VISUALPING{0123456789abcdef}"
        assert secret.url == "https://example.com/page"
        assert secret.location == SecretLocation.HTML_BODY
        assert isinstance(secret.found_at, datetime)
        assert secret.found_at.tzinfo is not None

    def test_found_at_defaults_to_now_utc(self):
        before = datetime.now(timezone.utc)
        secret = Secret(
            value="VISUALPING{0123456789abcdef}",
            url="https://example.com",
            location=SecretLocation.HTTP_HEADER,
            snippet="snippet",
        )
        after = datetime.now(timezone.utc)
        assert before <= secret.found_at <= after

    def test_found_at_can_be_explicitly_set(self):
        timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        secret = Secret(
            value="VISUALPING{0123456789abcdef}",
            url="https://example.com",
            location=SecretLocation.COOKIE,
            snippet="snippet",
            found_at=timestamp,
        )
        assert secret.found_at == timestamp

    def test_rejects_blank_value(self):
        with pytest.raises(ValidationError):
            Secret(value="   ", url="https://example.com", location=SecretLocation.SCRIPT, snippet="s")

    def test_rejects_blank_url(self):
        with pytest.raises(ValidationError):
            Secret(value="v", url="", location=SecretLocation.SCRIPT, snippet="s")

    def test_rejects_invalid_location(self):
        with pytest.raises(ValidationError):
            Secret(value="v", url="https://example.com", location="not_a_real_location", snippet="s")

    def test_serializes_to_json_dict(self):
        secret = Secret(
            value="VISUALPING{0123456789abcdef}",
            url="https://example.com",
            location=SecretLocation.HTML_COMMENT,
            snippet="snippet",
        )
        dumped = secret.model_dump(mode="json")
        assert dumped["value"] == "VISUALPING{0123456789abcdef}"
        assert dumped["location"] == "html_comment"
        assert isinstance(dumped["found_at"], str)


class TestCrawledNode:
    """Success and failure scenarios for the CrawledNode model."""

    def test_creates_with_defaults(self):
        node = CrawledNode(url="https://example.com")
        assert node.url == "https://example.com"
        assert node.depth == 0
        assert node.status_code is None
        assert node.has_secret is False

    def test_creates_with_all_fields(self):
        node = CrawledNode(url="https://example.com/page", depth=2, status_code=200, has_secret=True)
        assert node.depth == 2
        assert node.status_code == 200
        assert node.has_secret is True

    def test_rejects_blank_url(self):
        with pytest.raises(ValidationError):
            CrawledNode(url="   ")

    def test_rejects_negative_depth(self):
        with pytest.raises(ValidationError):
            CrawledNode(url="https://example.com", depth=-1)

    def test_is_frozen_and_hashable(self):
        node_a = CrawledNode(url="https://example.com", depth=1)
        node_b = CrawledNode(url="https://example.com", depth=1)
        node_c = CrawledNode(url="https://example.com", depth=2)
        assert hash(node_a) == hash(node_b)
        assert {node_a, node_b, node_c} == {node_a, node_c}
        with pytest.raises(ValidationError):
            node_a.depth = 5


class TestEdge:
    """Success and failure scenarios for the Edge model."""

    def test_creates_with_source_and_target(self):
        edge = Edge(source="https://example.com", target="https://example.com/child")
        assert edge.source == "https://example.com"
        assert edge.target == "https://example.com/child"

    def test_rejects_blank_source(self):
        with pytest.raises(ValidationError):
            Edge(source="", target="https://example.com")

    def test_rejects_blank_target(self):
        with pytest.raises(ValidationError):
            Edge(source="https://example.com", target="   ")

    def test_is_frozen_and_hashable_for_deduplication(self):
        edge_a = Edge(source="https://example.com", target="https://example.com/child")
        edge_b = Edge(source="https://example.com", target="https://example.com/child")
        edge_c = Edge(source="https://example.com", target="https://example.com/other")
        seen = {edge_a}
        seen.add(edge_b)  # duplicate, should not grow the set
        seen.add(edge_c)
        assert len(seen) == 2
        with pytest.raises(ValidationError):
            edge_a.target = "https://example.com/mutated"
