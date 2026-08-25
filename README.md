# Visualping Crawler Challenge

An async web crawler that walks a target site breadth-first, scans every page (and its
linked JS/CSS assets) for leaked secrets matching `VISUALPING{16_hex_chars}`, and
generates an interactive HTML report of what it found.

## Quick start

```bash
pip install httpx beautifulsoup4 pydantic pytest

python main.py https://example.com
```

This crawls from `https://example.com`, writes incremental results to
`local_data/results.json` as it goes, and generates `output.html` — a Tailwind-styled
report with KPI cards, a secrets table, and an interactive vis-network link graph —
when the crawl finishes.

### CLI options

```bash
python main.py [start_url] [--max-depth N] [--username USER --password PASS]
```

| Flag | Description |
|---|---|
| `start_url` | URL to start crawling from (default: `core.config.ROOT_URL`) |
| `--max-depth N` | Maximum BFS depth to crawl (default: unlimited — see note below) |
| `--username` / `--password` | HTTP Basic Auth credentials, if the target requires them |

**Bound `--max-depth` for real targets.** An unbounded crawl will follow any
crawler trap the target contains — e.g. infinite pagination — forever. Start with a
modest depth (5–10) and increase if the crawl completes quickly without one.

## What it scans

For every page it visits, the crawler checks:

- Visible body text and HTML comments
- HTTP response headers (including `Set-Cookie`) and parsed cookies
- Inline `<script>` tag content
- Every linked JS/CSS asset (`<script src>`, `<link rel=stylesheet>`) — fetched and
  scanned once per crawl, not once per page that references it
- Hidden routes embedded in any of the above as plain text (e.g. a path referenced
  only in a JS string, never present as an `<a href>` in the page's raw HTML — such as
  a client-side-rendered navigation menu)

## Architecture

Code is organized into layers by responsibility:

```
core/       config, data models, in-memory BFS state
network/    async HTTP client, retry/backoff, response wrapper
parsers/    link/route/secret extraction, HTML/asset scanning, link graph
crawl/      BFS traversal loop, page-processing pipeline
storage/    JSON report schema, atomic persistence, data loader
ui/         template loader, vis-network data formatter, HTML report generator
main.py     CLI entry point wiring everything together
```

Results persist atomically (write-to-temp-then-replace) to `local_data/results.json`
throughout the crawl, so findings already on disk survive an interrupted run.

## Testing

```bash
pytest
```

Every module has a matching test file under `tests/`, mirroring the same layer
structure (`tests/core/`, `tests/network/`, etc.).
