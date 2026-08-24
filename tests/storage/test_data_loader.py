"""Unit tests for the data loader/recovery module: data_loader.load_results."""

from datetime import datetime, timezone

from core.models import CrawledNode, Edge, Secret, SecretLocation
from storage.data_loader import load_results
from storage.exporter import build_report
from storage.persistence import write_json_atomic

START = datetime(2026, 8, 23, 10, 0, 0, tzinfo=timezone.utc)
END = datetime(2026, 8, 23, 10, 5, 0, tzinfo=timezone.utc)


class TestLoadResults:
    """Success and failure scenarios for load_results."""

    def test_returns_empty_report_when_file_missing(self, tmp_path):
        report = load_results(path=tmp_path / "does_not_exist.json")
        assert report.secrets == []
        assert report.nodes == []
        assert report.edges == []

    def test_returns_empty_report_for_empty_file(self, tmp_path):
        target = tmp_path / "results.json"
        target.write_text("", encoding="utf-8")
        report = load_results(path=target)
        assert report.secrets == []

    def test_returns_empty_report_for_whitespace_only_file(self, tmp_path):
        target = tmp_path / "results.json"
        target.write_text("   \n  ", encoding="utf-8")
        report = load_results(path=target)
        assert report.secrets == []

    def test_returns_empty_report_for_invalid_json(self, tmp_path):
        target = tmp_path / "results.json"
        target.write_text("{not valid json", encoding="utf-8")
        report = load_results(path=target)
        assert report.secrets == []

    def test_returns_empty_report_for_json_not_matching_schema(self, tmp_path):
        target = tmp_path / "results.json"
        target.write_text('{"unexpected": "shape"}', encoding="utf-8")
        report = load_results(path=target)
        assert report.secrets == []

    def test_loads_a_valid_results_file(self, tmp_path):
        target = tmp_path / "results.json"
        secret = Secret(
            value="VISUALPING{0123456789abcdef}",
            url="https://example.com",
            location=SecretLocation.HTML_BODY,
            snippet="ctx",
        )
        node = CrawledNode(url="https://example.com", depth=0)
        edge = Edge(source="https://example.com", target="https://example.com/child")
        original = build_report(
            secrets=[secret], nodes=[node], edges=[edge], start_time=START, end_time=END
        )
        write_json_atomic(original.to_json_dict(), path=target)

        loaded = load_results(path=target)
        assert len(loaded.secrets) == 1
        assert loaded.secrets[0].value == "VISUALPING{0123456789abcdef}"
        assert len(loaded.nodes) == 1
        assert len(loaded.edges) == 1
        assert loaded.summary.total_secrets_found == 1
        assert loaded.summary.total_pages_scanned == 1

    def test_loads_a_valid_empty_results_file(self, tmp_path):
        target = tmp_path / "results.json"
        original = build_report(
            secrets=[], nodes=[], edges=[], start_time=START, end_time=END
        )
        write_json_atomic(original.to_json_dict(), path=target)

        loaded = load_results(path=target)
        assert loaded.secrets == []
        assert loaded.summary.total_pages_scanned == 0
