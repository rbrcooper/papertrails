# Papertrails — Documentation

**Start here:** [PRODUCT.md](PRODUCT.md) (what ships). How to run: [../papertrails/README.md](../papertrails/README.md). Chronology: [ROADMAP.md](ROADMAP.md).

This index is not the product. `processes.main` and Ollama are frozen library/QA paths, not how you run the feed.

## Current status

Shipped: ESMA FTWS dealer-table feed on **23 FTWS-live** parents (universe **756** LEI-eligible) — about **61** deals in `website/data/deals.json`. Cron is off. Publish is regex only.

| Area | Status | Notes |
|------|--------|-------|
| Alert feed product | Shipped | `papertrails/` watchlist + auto-publish |
| Bounded validation L0–L4 | Passing | 3 benchmark ISINs — `py -3 scripts/run_validation_suite.py` |
| GOGEL + LEI/ISIN | In use | Default GOGEL 2025 CSV with identifiers |
| ESMA scraper (audit path) | 3/3 | Solr `downloadFile` + session cookies |
| Product PDFs | `data/alerts/pdfs/` | Live poll / `--skip-scraping` root |
| Bulk `data/downloads/` | Legacy + L1–L4 fixtures | Do not glob; do not relocate wholesale |
| Website | `website/data/deals.json` | Flask `website/app.py` is local preview |

## Quick start

Same as the root README. No Ollama on the publish path.

```powershell
pip install -r docs/requirements.txt

py -3 -m papertrails.run_alerts --watchlist papertrails/watchlist_top50.yaml --isin-limit 1 --headed
py -3 -m papertrails.run_alerts --skip-scraping
py -3 -m website.app
```

`--headed` if ESMA throttles headless Chrome. Unattended cron is not enabled. Operator coverage loop: [../papertrails/README.md](../papertrails/README.md).

## Extractor QA (library)

Not the product run path.

```bash
py -3 scripts/run_validation_suite.py
py -3 scripts/run_validation_suite.py --skip-l2
py -3 processes/tests/debug/audit_benchmark_isins.py
pytest processes/tests/core/test_doc_selection.py -q
```

`scripts/triage_downloaded_pdfs.py` and `scripts/diagnose_extraction.py` score the frozen `data/downloads/` corpus. Do not glob that folder into publish.

## Project layout

```
papertrails/         Product — watchlist, run_alerts, schema
processes/           Library — scraper, extractors, DB. Do not move.
website/             Tracked feed website/data/deals.json + Flask preview
frontend/            Vite UI of this feed
scripts/             L0–L4 validation, triage, frozen-walk diagnostics
tests/               ground_truth.json (L1)
data/alerts/         Live PDFs, seen.json, quarantine (gitignored)
data/downloads/      Legacy scrape + L1–L4 fixtures (gitignored)
docs/                Start with PRODUCT.md
```

## Documentation index

| Doc | Purpose |
|-----|---------|
| [PRODUCT.md](PRODUCT.md) | **Product of record** — scope, now/next, kill bar |
| [ROADMAP.md](ROADMAP.md) | Chronology (done / next / later) |
| [VALIDATION_AND_QUALITY.md](VALIDATION_AND_QUALITY.md) | L0–L4 extractor QA |
| [BENCHMARKS.md](BENCHMARKS.md) | Ground-truth extraction results |
| [ARCHITECTURE.md](ARCHITECTURE.md) | **Library / frozen bulk walk** — not the product |
| [OPERATIONAL_NOTES.md](OPERATIONAL_NOTES.md) | **Library ops** — `processes.main` paths, not `run_alerts` |
| [examples/company_profiles.example.json](examples/company_profiles.example.json) | Optional scraper profile overrides |

## External data

ESMA’s published datasets (MiFID, FIRDS, etc.) do **not** contain prospectus PDFs or bookrunner lists. This project relies on **GOGEL identifiers + ESMA portal scraping + PDF extraction**. FIRDS-style data may later help validate ISINs/LEIs only.
