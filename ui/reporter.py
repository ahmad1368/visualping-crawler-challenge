"""HTML report generator: injects crawl results into the base template.

Loads the persisted crawl results (`data_loader.load_results`) and the
base report template (`template.load_template`), injects summary KPIs
and a row per discovered secret into the template's `{{ TOKEN }}`
placeholders, and atomically writes the finished page to `output.html`.
"""

from __future__ import annotations

import html
import logging
from pathlib import Path

from data_loader import load_results
from exporter import CrawlReport
from persistence import write_text_atomic
from template import load_template

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_PATH = Path("output.html")

# Row shown in the secrets table when a report contains no findings.
_NO_SECRETS_ROW = (
    '<tr><td colspan="4" class="px-4 py-3 text-slate-500">No secrets discovered.</td></tr>'
)


def render_report(report: CrawlReport, template_html: str) -> str:
    """Inject `report`'s data into `template_html` and return the finished HTML.

    Fills every `{{ TOKEN }}` placeholder defined in `template.py`:
    summary KPIs (pages scanned, secrets found, links discovered, and the
    maximum BFS depth reached, derived from `report.nodes`) and a `<tr>`
    row per discovered secret (value, location, URL, snippet). Each
    secret field is HTML-escaped, since it originates from crawled,
    untrusted page content and is otherwise inserted verbatim into the
    output page.
    """
    max_depth = max((node.depth for node in report.nodes), default=0)

    replacements = {
        "{{ GENERATED_AT }}": report.summary.end_time.isoformat(),
        "{{ START_TIME }}": report.summary.start_time.isoformat(),
        "{{ END_TIME }}": report.summary.end_time.isoformat(),
        "{{ TOTAL_PAGES_SCANNED }}": str(report.summary.total_pages_scanned),
        "{{ TOTAL_SECRETS_FOUND }}": str(report.summary.total_secrets_found),
        "{{ TOTAL_LINKS_DISCOVERED }}": str(len(report.edges)),
        "{{ MAX_CRAWL_DEPTH }}": str(max_depth),
        "{{ SECRETS_TABLE_ROWS }}": _render_secrets_rows(report),
        "{{ GRAPH_DATA_JSON }}": "{}",
    }

    rendered = template_html
    for token, value in replacements.items():
        rendered = rendered.replace(token, value)

    return rendered


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


def generate_report(
    *,
    results_path: Path | str | None = None,
    template_path: Path | str | None = None,
    output_path: Path | str = DEFAULT_OUTPUT_PATH,
) -> bool:
    """Load results and the template, render the report, and write output.html.

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
