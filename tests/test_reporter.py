"""Unit tests for the HTML report generator: ui.reporter.render_report/generate_report."""

from datetime import datetime, timezone

from exporter import build_report
from models import CrawledNode, Edge, Secret, SecretLocation
from persistence import write_json_atomic
from ui.reporter import generate_report, render_report

START = datetime(2026, 8, 23, 10, 0, 0, tzinfo=timezone.utc)
END = datetime(2026, 8, 23, 10, 5, 0, tzinfo=timezone.utc)

MINIMAL_TEMPLATE = (
    "<html><body>"
    "<p>{{ GENERATED_AT }} {{ START_TIME }} {{ END_TIME }}</p>"
    "<p>{{ TOTAL_PAGES_SCANNED }} {{ TOTAL_SECRETS_FOUND }} {{ TOTAL_LINKS_DISCOVERED }}"
    " {{ MAX_CRAWL_DEPTH }}</p>"
    "<table><tbody>{{ SECRETS_TABLE_ROWS }}</tbody></table>"
    "<script>{{ GRAPH_DATA_JSON }}</script>"
    "</body></html>"
)


def _secret(value: str = "VISUALPING{0123456789abcdef}", snippet: str = "context") -> Secret:
    return Secret(
        value=value, url="https://example.com", location=SecretLocation.HTML_BODY, snippet=snippet
    )


class TestRenderReport:
    """Success and failure scenarios for render_report."""

    def test_fills_kpi_placeholders(self):
        report = build_report(
            secrets=[_secret()],
            nodes=[CrawledNode(url="https://example.com", depth=0)],
            edges=[Edge(source="https://example.com", target="https://example.com/child")],
            start_time=START,
            end_time=END,
        )
        rendered = render_report(report, MINIMAL_TEMPLATE)
        assert "{{" not in rendered
        assert ">1 1 1 0<" in rendered

    def test_computes_max_crawl_depth_from_nodes(self):
        report = build_report(
            secrets=[],
            nodes=[
                CrawledNode(url="https://a.com", depth=0),
                CrawledNode(url="https://b.com", depth=2),
                CrawledNode(url="https://c.com", depth=1),
            ],
            edges=[],
            start_time=START,
            end_time=END,
        )
        rendered = render_report(report, MINIMAL_TEMPLATE)
        assert "3 0 0 2" in rendered

    def test_max_crawl_depth_is_zero_when_no_nodes(self):
        report = build_report(secrets=[], nodes=[], edges=[], start_time=START, end_time=END)
        rendered = render_report(report, MINIMAL_TEMPLATE)
        assert "0 0 0 0" in rendered

    def test_renders_a_row_per_secret(self):
        report = build_report(
            secrets=[_secret("VISUALPING{0123456789abcdef}"), _secret("VISUALPING{fedcba9876543210}")],
            nodes=[],
            edges=[],
            start_time=START,
            end_time=END,
        )
        rendered = render_report(report, MINIMAL_TEMPLATE)
        assert rendered.count("<tr>") == 2
        assert "VISUALPING{0123456789abcdef}" in rendered
        assert "VISUALPING{fedcba9876543210}" in rendered

    def test_renders_placeholder_row_when_no_secrets(self):
        report = build_report(secrets=[], nodes=[], edges=[], start_time=START, end_time=END)
        rendered = render_report(report, MINIMAL_TEMPLATE)
        assert "No secrets discovered." in rendered

    def test_escapes_html_in_secret_fields(self):
        secret = _secret(snippet='<script>alert("xss")</script>')
        report = build_report(secrets=[secret], nodes=[], edges=[], start_time=START, end_time=END)
        rendered = render_report(report, MINIMAL_TEMPLATE)
        assert "<script>alert" not in rendered
        assert "&lt;script&gt;" in rendered

    def test_includes_secret_location_value(self):
        secret = Secret(
            value="VISUALPING{0123456789abcdef}",
            url="https://example.com",
            location=SecretLocation.COOKIE,
            snippet="ctx",
        )
        report = build_report(secrets=[secret], nodes=[], edges=[], start_time=START, end_time=END)
        rendered = render_report(report, MINIMAL_TEMPLATE)
        assert "cookie" in rendered


class TestGraphDataInjection:
    """Success and failure scenarios for the GRAPH_DATA_JSON placeholder."""

    def test_embeds_real_node_and_edge_data(self):
        node_a = CrawledNode(url="https://a.com", depth=0)
        node_b = CrawledNode(url="https://b.com", depth=1)
        edge = Edge(source="https://a.com", target="https://b.com")
        report = build_report(
            secrets=[], nodes=[node_a, node_b], edges=[edge], start_time=START, end_time=END
        )
        rendered = render_report(report, MINIMAL_TEMPLATE)
        assert '"https://a.com"' in rendered
        assert '"from": "https://a.com"' in rendered

    def test_embeds_empty_arrays_for_empty_report(self):
        report = build_report(secrets=[], nodes=[], edges=[], start_time=START, end_time=END)
        rendered = render_report(report, MINIMAL_TEMPLATE)
        assert '"nodes": []' in rendered
        assert '"edges": []' in rendered

    def test_escapes_closing_script_tag_in_node_title(self):
        node = CrawledNode(url="https://example.com/</script><script>alert(1)</script>", depth=0)
        report = build_report(secrets=[], nodes=[node], edges=[], start_time=START, end_time=END)
        rendered = render_report(report, MINIMAL_TEMPLATE)
        assert "</script><script>alert(1)</script>" not in rendered


class TestGenerateReport:
    """Success and failure scenarios for generate_report."""

    def test_writes_output_file_from_results_and_template(self, tmp_path):
        results_path = tmp_path / "results.json"
        template_path = tmp_path / "template.html"
        output_path = tmp_path / "output.html"

        report = build_report(
            secrets=[_secret()], nodes=[], edges=[], start_time=START, end_time=END
        )
        write_json_atomic(report.to_json_dict(), path=results_path)
        template_path.write_text(MINIMAL_TEMPLATE, encoding="utf-8")

        result = generate_report(
            results_path=results_path, template_path=template_path, output_path=output_path
        )

        assert result is True
        assert output_path.exists()
        assert "VISUALPING{0123456789abcdef}" in output_path.read_text(encoding="utf-8")

    def test_still_generates_report_when_results_file_is_missing(self, tmp_path):
        template_path = tmp_path / "template.html"
        output_path = tmp_path / "output.html"
        template_path.write_text(MINIMAL_TEMPLATE, encoding="utf-8")

        result = generate_report(
            results_path=tmp_path / "does_not_exist.json",
            template_path=template_path,
            output_path=output_path,
        )

        assert result is True
        assert "No secrets discovered." in output_path.read_text(encoding="utf-8")

    def test_returns_false_when_template_is_missing(self, tmp_path):
        output_path = tmp_path / "output.html"
        result = generate_report(
            results_path=tmp_path / "results.json",
            template_path=tmp_path / "does_not_exist.html",
            output_path=output_path,
        )

        assert result is False
        assert output_path.exists() is False
