"""HTML report generator: injects crawl results into the base template.

Loads the persisted crawl results (`storage.data_loader.load_results`)
and the base report template (`ui.template.load_template`), injects
summary KPIs and a row per discovered secret into the template's
`{{ TOKEN }}` placeholders, and atomically writes the finished page to
`index.html`.

Also exposes `build_report_payload`, which turns a `CrawlReport` into
the same JSON-ready shape used both for template rendering and for the
`/api/secrets` endpoint served by `ui.server`, so the live server and
the static template stay in sync with a single source of truth.
"""

from __future__ import annotations

import html
import json
import logging
from pathlib import Path

from core import config
from storage.data_loader import load_results
from storage.exporter import CrawlReport
from storage.persistence import write_text_atomic
from ui.graph_formatter import format_graph_data
from ui.template import load_template

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_PATH = Path("index.html")

# Row shown in the secrets table when a report contains no findings.
_NO_SECRETS_ROW = (
    '<tr><td colspan="4" class="px-4 py-3 text-slate-500">No secrets discovered.</td></tr>'
)


def render_report(report: CrawlReport, template_html: str) -> str:
    """Inject `report`'s data into `template_html` and return the finished HTML.

    Fills every `{{ TOKEN }}` placeholder defined in `template.py`:
    summary KPIs (pages scanned, secrets found, links discovered, and the
    maximum BFS depth reached, derived from `report.nodes`), a `<tr>`
    row per discovered secret (value, location, URL, snippet), and the
    vis-network graph data (via `graph_formatter.format_graph_data`).
    Each secret field is HTML-escaped, since it originates from crawled,
    untrusted page content and is otherwise inserted verbatim into the
    output page.

    `{{ API_BASE_URL }}` is filled in with the live server's own origin
    (`http://localhost:<core.config.APP_PORT>`) rather than left as a
    relative path, since the rendered page is a static file: it can be
    (and during development often is) served by something else, such as
    an editor's static preview server on a different port, in which
    case relative `fetch("/api/...")` calls would silently hit that
    other server instead of `ui.server`.
    """
    max_depth = _max_crawl_depth(report)

    replacements = {
        "{{ GENERATED_AT }}": report.summary.end_time.isoformat(),
        "{{ START_TIME }}": report.summary.start_time.isoformat(),
        "{{ END_TIME }}": report.summary.end_time.isoformat(),
        "{{ TOTAL_PAGES_SCANNED }}": str(report.summary.total_pages_scanned),
        "{{ TOTAL_SECRETS_FOUND }}": str(report.summary.total_secrets_found),
        "{{ TOTAL_LINKS_DISCOVERED }}": str(len(report.edges)),
        "{{ MAX_CRAWL_DEPTH }}": str(max_depth),
        "{{ SECRETS_TABLE_ROWS }}": _render_secrets_rows(report),
        "{{ GRAPH_DATA_JSON }}": _render_graph_data(report),
        "{{ API_BASE_URL }}": f"http://localhost:{config.APP_PORT}",
    }

    rendered = template_html
    for token, value in replacements.items():
        rendered = rendered.replace(token, value)

    return rendered


def _max_crawl_depth(report: CrawlReport) -> int:
    """Return the deepest BFS depth reached across `report.nodes`, or 0 if none."""
    return max((node.depth for node in report.nodes), default=0)


def build_report_payload(report: CrawlReport) -> dict:
    """Build the JSON-ready payload shared by the `/api/secrets` endpoint.

    Mirrors the same KPI fields and secret rows `render_report` injects
    into the static template, plus the vis-network graph data, so a
    browser polling this payload can refresh the page's DOM (KPI cards,
    secrets table, link graph) without a full server-rendered reload.
    Secret fields are left un-escaped here (unlike `render_report`'s HTML
    output): this is JSON, not HTML, so the consuming JavaScript is
    responsible for inserting each value via a text-only DOM API (e.g.
    `textContent`), never via `innerHTML`, since the values still
    originate from crawled, untrusted page content.
    """
    return {
        "generated_at": report.summary.end_time.isoformat(),
        "start_time": report.summary.start_time.isoformat(),
        "end_time": report.summary.end_time.isoformat(),
        "total_pages_scanned": report.summary.total_pages_scanned,
        "total_secrets_found": report.summary.total_secrets_found,
        "total_links_discovered": len(report.edges),
        "max_crawl_depth": _max_crawl_depth(report),
        "secrets": [
            {
                "value": secret.value,
                "location": secret.location.value,
                "url": secret.url,
                "snippet": secret.snippet,
            }
            for secret in report.secrets
        ],
        "graph": format_graph_data(report),
    }


def _render_secrets_rows(report: CrawlReport) -> str:
    """Render one `<tr>` per discovered secret, or a placeholder row if none."""
    if not report.secrets:
        return _NO_SECRETS_ROW

    rows = []
    for secret in report.secrets:
        rows.append(
            "<tr>"
            f'<td class="px-4 py-3 font-mono text-rose-300">{html.escape(secret.value)}</td>'
            f'<td class="px-4 py-3">{html.escape(secret.location.value)}</td>'
            f'<td class="px-4 py-3 break-all">{html.escape(secret.url)}</td>'
            f'<td class="px-4 py-3 text-slate-400">{html.escape(secret.snippet)}</td>'
            "</tr>"
        )
    return "\n".join(rows)


def _render_graph_data(report: CrawlReport) -> str:
    """Serialize the report's vis-network graph data for embedding in a <script> tag.

    Escapes every `</` in the JSON output to `<\\/`, which stays valid
    JSON (`JSON.parse` reads `\\/` back as `/`) but prevents a crawled
    URL or tooltip title containing a literal `"</script>"` from
    prematurely closing the surrounding script tag.
    """
    return json.dumps(format_graph_data(report)).replace("</", "<\\/")


def generate_report(
    *,
    results_path: Path | str | None = None,
    template_path: Path | str | None = None,
    output_path: Path | str = DEFAULT_OUTPUT_PATH,
) -> bool:
    """Load results and the template, render the report, and write index.html.

    `results_path`/`template_path` default to `data_loader.load_results`
    and `template.load_template`'s own defaults when omitted (`None`).
    Returns True if `output_path` was written successfully. Returns
    False, and logs a warning, without writing anything if the template
    failed to load, since an empty template would produce a broken page.
    """
    report = load_results() if results_path is None else load_results(path=results_path)
    template_html = (
        load_template() if template_path is None else load_template(path=template_path)
    )

    if not template_html:
        logger.warning("Cannot generate report: template failed to load.")
        return False

    rendered = render_report(report, template_html)
    return write_text_atomic(rendered, path=output_path)
