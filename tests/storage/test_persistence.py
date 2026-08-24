"""Unit tests for atomic JSON persistence: persistence.write_json_atomic / ResultsWriter."""

import json

from core.models import CrawledNode, Edge, Secret, SecretLocation
from storage.persistence import ResultsWriter, write_json_atomic


def _secret(value: str = "VISUALPING{0123456789abcdef}") -> Secret:
    return Secret(
        value=value, url="https://example.com", location=SecretLocation.HTML_BODY, snippet="ctx"
    )


class TestWriteJsonAtomic:
    """Success and failure scenarios for write_json_atomic."""

    def test_writes_data_to_new_file(self, tmp_path):
        target = tmp_path / "results.json"
        assert write_json_atomic({"a": 1}, path=target) is True
        assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}

    def test_creates_missing_parent_directory(self, tmp_path):
        target = tmp_path / "nested" / "local_data" / "results.json"
        assert write_json_atomic({"a": 1}, path=target) is True
        assert target.exists()

    def test_overwrites_existing_file_completely(self, tmp_path):
        target = tmp_path / "results.json"
        write_json_atomic({"a": 1}, path=target)
        write_json_atomic({"b": 2}, path=target)
        assert json.loads(target.read_text(encoding="utf-8")) == {"b": 2}

    def test_leaves_no_temporary_file_behind_after_success(self, tmp_path):
        target = tmp_path / "results.json"
        write_json_atomic({"a": 1}, path=target)
        remaining = list(tmp_path.iterdir())
        assert remaining == [target]

    def test_returns_false_and_preserves_prior_file_on_serialization_failure(self, tmp_path):
        target = tmp_path / "results.json"
        write_json_atomic({"a": 1}, path=target)

        unserializable = {"bad": {1, 2, 3}}
        assert write_json_atomic(unserializable, path=target) is False
        assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}

    def test_does_not_raise_on_serialization_failure(self, tmp_path):
        target = tmp_path / "results.json"
        write_json_atomic({"bad": object()}, path=target)


class TestResultsWriter:
    """Success scenarios for ResultsWriter's incremental persistence."""

    def test_counts_start_at_zero(self, tmp_path):
        writer = ResultsWriter(path=tmp_path / "results.json")
        assert writer.node_count == 0
        assert writer.secret_count == 0

    def test_node_count_and_secret_count_reflect_recorded_items(self, tmp_path):
        writer = ResultsWriter(path=tmp_path / "results.json")
        writer.record_node(CrawledNode(url="https://a.com", depth=0))
        writer.record_node(CrawledNode(url="https://b.com", depth=1))
        writer.record_secret(_secret())
        assert writer.node_count == 2
        assert writer.secret_count == 1

    def test_persists_a_secret_immediately(self, tmp_path):
        target = tmp_path / "results.json"
        writer = ResultsWriter(path=target)
        assert writer.record_secret(_secret()) is True

        payload = json.loads(target.read_text(encoding="utf-8"))
        assert len(payload["secrets"]) == 1
        assert payload["secrets"][0]["value"] == "VISUALPING{0123456789abcdef}"
        assert payload["summary"]["total_secrets_found"] == 1

    def test_persists_growing_secret_list_across_calls(self, tmp_path):
        target = tmp_path / "results.json"
        writer = ResultsWriter(path=target)
        writer.record_secret(_secret("VISUALPING{0123456789abcdef}"))
        writer.record_secret(_secret("VISUALPING{fedcba9876543210}"))

        payload = json.loads(target.read_text(encoding="utf-8"))
        assert len(payload["secrets"]) == 2
        assert payload["summary"]["total_secrets_found"] == 2

    def test_includes_recorded_nodes_and_edges_in_next_flush(self, tmp_path):
        target = tmp_path / "results.json"
        writer = ResultsWriter(path=target)
        writer.record_node(CrawledNode(url="https://example.com", depth=0))
        writer.record_edge(
            Edge(source="https://example.com", target="https://example.com/child")
        )
        writer.record_secret(_secret())

        payload = json.loads(target.read_text(encoding="utf-8"))
        assert len(payload["nodes"]) == 1
        assert len(payload["edges"]) == 1
        assert payload["summary"]["total_pages_scanned"] == 1

    def test_recording_a_node_alone_does_not_write_a_file(self, tmp_path):
        target = tmp_path / "results.json"
        writer = ResultsWriter(path=target)
        writer.record_node(CrawledNode(url="https://example.com", depth=0))
        assert target.exists() is False

    def test_explicit_flush_persists_nodes_and_edges_with_zero_secrets(self, tmp_path):
        # Regression test: a clean crawl (no secrets found) previously
        # never wrote anything to disk at all, since only record_secret
        # triggered a flush. A caller must be able to flush explicitly
        # once the crawl is done.
        target = tmp_path / "results.json"
        writer = ResultsWriter(path=target)
        writer.record_node(CrawledNode(url="https://example.com", depth=0))
        writer.record_edge(
            Edge(source="https://example.com", target="https://example.com/child")
        )
        assert target.exists() is False

        assert writer.flush() is True

        payload = json.loads(target.read_text(encoding="utf-8"))
        assert len(payload["nodes"]) == 1
        assert len(payload["edges"]) == 1
        assert payload["secrets"] == []
        assert payload["summary"]["total_pages_scanned"] == 1
        assert payload["summary"]["total_secrets_found"] == 0
