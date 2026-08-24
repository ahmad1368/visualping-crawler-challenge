"""Unit tests for the output JSON schema/report model in exporter.py."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from exporter import CrawlReport, CrawlSummary, build_report
from models import CrawledNode, Edge, Secret, SecretLocation

START = datetime(2026, 8, 23, 10, 0, 0, tzinfo=timezone.utc)
END = START + timedelta(minutes=5)


def _secret() -> Secret:
    return Secret(
        value="VISUALPING{0123456789abcdef}",
        url="https://example.com",
        location=SecretLocation.HTML_BODY,
        snippet="context",
    )


def _node() -> CrawledNode:
    return CrawledNode(url="https://example.com", depth=0, status_code=200)


def _edge() -> Edge:
    return Edge(source="https://example.com", target="https://example.com/child")


class TestCrawlSummary:
    """Success and failure scenarios for CrawlSummary validation."""

    def test_accepts_valid_summary(self):
        summary = CrawlSummary(
            start_time=START, end_time=END, total_pages_scanned=3, total_secrets_found=1
        )
        assert summary.total_pages_scanned == 3

    def test_rejects_negative_pages_scanned(self):
        with pytest.raises(ValidationError):
            CrawlSummary(
                start_time=START, end_time=END, total_pages_scanned=-1, total_secrets_found=0
            )

    def test_rejects_negative_secrets_found(self):
        with pytest.raises(ValidationError):
            CrawlSummary(
                start_time=START, end_time=END, total_pages_scanned=0, total_secrets_found=-1
            )

    def test_rejects_end_time_before_start_time(self):
        with pytest.raises(ValidationError):
            CrawlSummary(
                start_time=END, end_time=START, total_pages_scanned=0, total_secrets_found=0
            )


class TestBuildReport:
    """Success scenarios for build_report."""

    def test_derives_total_pages_scanned_from_nodes(self):
        report = build_report(
            secrets=[], nodes=[_node(), _node()], edges=[], start_time=START, end_time=END
        )
        assert report.summary.total_pages_scanned == 2

    def test_derives_total_secrets_found_from_secrets(self):
        report = build_report(
            secrets=[_secret()], nodes=[], edges=[], start_time=START, end_time=END
        )
        assert report.summary.total_secrets_found == 1

    def test_builds_empty_report(self):
        report = build_report(secrets=[], nodes=[], edges=[], start_time=START, end_time=END)
        assert report.secrets == []
        assert report.nodes == []
        assert report.edges == []
        assert report.summary.total_pages_scanned == 0
        assert report.summary.total_secrets_found == 0

    def test_includes_provided_edges(self):
        report = build_report(
            secrets=[], nodes=[], edges=[_edge()], start_time=START, end_time=END
        )
        assert report.edges == [_edge()]


class TestToJsonDict:
    """Success scenarios for CrawlReport.to_json_dict."""

    def test_has_primary_top_level_keys(self):
        report = build_report(
            secrets=[_secret()], nodes=[_node()], edges=[_edge()], start_time=START, end_time=END
        )
        payload = report.to_json_dict()
        assert set(payload.keys()) == {"secrets", "nodes", "edges", "summary"}

    def test_summary_timestamps_are_json_serializable_strings(self):
        report = build_report(secrets=[], nodes=[], edges=[], start_time=START, end_time=END)
        payload = report.to_json_dict()
        assert isinstance(payload["summary"]["start_time"], str)
        assert isinstance(payload["summary"]["end_time"], str)

    def test_secret_location_enum_is_serialized_to_its_plain_value(self):
        report = build_report(
            secrets=[_secret()], nodes=[], edges=[], start_time=START, end_time=END
        )
        payload = report.to_json_dict()
        assert payload["secrets"][0]["location"] == "html_body"

    def test_result_round_trips_through_json_dumps(self):
        report = build_report(
            secrets=[_secret()], nodes=[_node()], edges=[_edge()], start_time=START, end_time=END
        )
        serialized = json.dumps(report.to_json_dict())
        assert json.loads(serialized)["summary"]["total_pages_scanned"] == 1

    def test_empty_report_serializes_without_error(self):
        report = build_report(secrets=[], nodes=[], edges=[], start_time=START, end_time=END)
        assert json.dumps(report.to_json_dict())
