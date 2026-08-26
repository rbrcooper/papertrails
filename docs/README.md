# Papertrails — Documentation

**Product:** [PRODUCT.md](PRODUCT.md) (alert feed). Package: `papertrails/`.

Library: scrape ESMA prospectus PDFs and extract bond metadata + underwriting banks. Bulk GOGEL walk via `processes.main` is **legacy**.

## Current status (Aug 2026)

| Area | Status | Notes |
|------|--------|-------|
| Alert feed product | 🚧 | `papertrails/` watchlist + auto-publish |
| Bounded validation L0–L4 | ✅ Passing | 3 benchmark ISINs — `py -3 scripts/run_validation_suite.py` |
| GOGEL + LEI/ISIN | ✅ | Default GOGEL 2025 CSV with identifiers |
| ESMA scraper (audit path) | ✅ 3/3 | Solr `downloadFile` + session cookies |
| ESMA yield (random GOGEL) | ⚠️ | Aug pilot: intake OK, often `no_tier1` |
| Bulk `data/downloads/` | ❌ legacy junk | ~5/277 usable; do not glob |
| Website | ✅ deals page | `website/app.py` ← `website/data/deals.json` |

## Quick start

```bash
pip install -r docs/requirements.txt
ollama pull llama3.1:8b

py -3 -m papertrails.build_watchlist --top 5
py -3 -m papertrails.run_alerts --phase0
py -3 -m papertrails.run_alerts
```

Environment: `HEADLESS=true` by default in alert runner; use `--headed` if needed.

## Validation & quality checks

```bash
# Full bounded suite (recommended)
py -3 scripts/run_validation_suite.py
py -3 scripts/run_validation_suite.py --skip-l2   # reuse existing L2 audit CSV

# L2 ESMA audit only
py -3 processes/tests/debug/audit_benchmark_isins.py

# PDF triage on existing downloads
py -3 scripts/triage_downloaded_pdfs.py --n 10 --seed 1
py -3 scripts/triage_downloaded_pdfs.py --all
```

Legacy extraction diagnose:


```bash
python scripts/diagnose_extraction.py
```

## Integration smoke tests

```bash
python processes/tests/debug/test_csv_ingestion.py
pytest processes/tests/core/test_doc_selection.py -q
```

## Project layout

```
papertrails/         Alert feed product (watchlist, run_alerts, schema)
processes/           Library (main.py legacy, scraper, extractors, DB)
website/             Reverse-chron deals page + data/deals.json
scripts/             Validation suite, triage, diagnostics
tests/               ground_truth.json
processes/tests/     Unit tests (core/) and debug tools (debug/)
data/                GOGEL CSV, downloads/, alerts/, processed/ (local)
logs/                workflow.log, audit/, validation outputs
docs/                This folder — start with PRODUCT.md
```

## Documentation index

| Doc | Purpose |
|-----|---------|
| [PRODUCT.md](PRODUCT.md) | **Product scope, repo reality, STE ranking, kill bar** |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Components, data flow, GOGEL/ISIN matching, AI chunking |
| [VALIDATION_AND_QUALITY.md](VALIDATION_AND_QUALITY.md) | **L0–L4 layers**, download triage, current issues, next steps |
| [OPERATIONAL_NOTES.md](OPERATIONAL_NOTES.md) | Scraper tuning, paths, Windows/PowerShell notes |
| [BENCHMARKS.md](BENCHMARKS.md) | Ground-truth extraction results and known failure modes |
| [ROADMAP.md](ROADMAP.md) | Alert-feed milestones (defers to PRODUCT.md) |
| [examples/company_profiles.example.json](examples/company_profiles.example.json) | Optional scraper profile overrides |

## External data

ESMA’s published datasets (MiFID, FIRDS, etc.) do **not** contain prospectus PDFs or bookrunner lists. This project relies on **GOGEL identifiers + ESMA portal scraping + PDF extraction**. FIRDS-style data may later help validate ISINs/LEIs only.
