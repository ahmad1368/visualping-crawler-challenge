"""Base HTML report template loader.

Exposes the static `ui/templates/template.html` file — a Tailwind CSS
(Visualping-themed) report shell with named `{{ TOKEN }}` placeholders —
along with the exact set of placeholder tokens it defines, so the
dynamic data injector (`ui.reporter`) has a single source of truth for
what it is expected to fill in.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "template.html"

# Every `{{ TOKEN }}` placeholder the template defines for dynamic data
# injection. Kept here as the single source of truth so ui.reporter and
# this module's tests never drift out of sync with the template file
# itself.
REQUIRED_PLACEHOLDERS: tuple[str, ...] = (
    "{{ GENERATED_AT }}",
    "{{ START_TIME }}",
    "{{ END_TIME }}",
    "{{ TOTAL_PAGES_SCANNED }}",
    "{{ TOTAL_SECRETS_FOUND }}",
    "{{ TOTAL_LINKS_DISCOVERED }}",
    "{{ MAX_CRAWL_DEPTH }}",
    "{{ SECRETS_TABLE_ROWS }}",
    "{{ GRAPH_DATA_JSON }}",
    "{{ API_BASE_URL }}",
)


def load_template(path: Path | str = TEMPLATE_PATH) -> str:
    """Read the base report template's raw HTML text.

    Returns an empty string, and logs a warning, if `path` does not
    exist or cannot be read, rather than raising: a missing template
    should not crash report generation, and the caller can detect the
    empty result and handle the failure itself.
    """
    path = Path(path)

    if not path.exists():
        logger.warning("Template file %s does not exist.", path)
        return ""

    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to read template file %s: %s", path, exc)
        return ""
