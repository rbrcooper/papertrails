# Papertrails — Documentation

Pipeline to scrape ESMA prospectus PDFs for GOGEL-listed companies and extract bond metadata (dates, currency, coupon) and underwriting banks.

## Current status (May 2026)

| Area | Status | Notes |
|------|--------|-------|
| Bounded validation L0–L4 | ✅ Passing | 3 benchmark ISINs (OMV, AKER, Total) — `py -3 scripts/run_validation_suite.py` |
| GOGEL company load + LEI/ISIN scoring | ✅ Working | Default: `data/raw/Urgewald GOGEL 2025 V1.2 with identifiers.csv` |
| ESMA scraper (audit path) | ✅ 3/3 | Live scrape + session download for benchmarks |
| ESMA scraper (bulk downloads) | ⚠️ Poor yield | Triage: **5/277** PDFs good tier1 candidates in existing folder |
| Metadata extraction (regex) | ✅ Strong | Matches ground truth on benchmark FTWS PDFs |
| Bank extraction (AI + chunking) | ⚠️ Mixed | Dealer-table regex + AI; layout-dependent — see [BENCHMARKS.md](BENCHMARKS.md) |
| Validation / DB / Excel output | ✅ Baseline | `ExtractionValidator`, SQLite, `master_detailed_report.xlsx` |
| API / frontend | 🔲 Skeleton | `website/app.py` |

**End-to-end production readiness:** benchmark path ~75%; bulk download → extract path ~40%. See [VALIDATION_AND_QUALITY.md](VALIDATION_AND_QUALITY.md).

## Quick start

```bash
pip install -r docs/requirements.txt
ollama pull llama3.1:8b
ollama serve   # separate terminal

python -m processes.main --limit-companies 3
python -m processes.main --region-filter eu
python -m processes.main --skip-scraping
```

Environment: `HEADLESS=true` for headless Chrome (default is headed).

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
processes/           Core pipeline (main.py, scraper, extractors, DB)
scripts/             Validation suite, triage, diagnostics
tests/               ground_truth.json
processes/tests/     Unit tests (core/) and debug tools (debug/)
data/                GOGEL CSV, downloads/, processed/ (local, gitignored)
logs/                workflow.log, audit/, validation outputs (gitignored)
docs/                This folder
```

## Documentation index

| Doc | Purpose |
|-----|---------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Components, data flow, GOGEL/ISIN matching, AI chunking |
| [VALIDATION_AND_QUALITY.md](VALIDATION_AND_QUALITY.md) | **L0–L4 layers**, download triage, current issues, next steps |
| [OPERATIONAL_NOTES.md](OPERATIONAL_NOTES.md) | Scraper tuning, paths, Windows/PowerShell notes |
| [BENCHMARKS.md](BENCHMARKS.md) | Ground-truth extraction results and known failure modes |
| [ROADMAP.md](ROADMAP.md) | Remaining work to reach production |
| [examples/company_profiles.example.json](examples/company_profiles.example.json) | Optional scraper profile overrides |

## External data

ESMA’s published datasets (MiFID, FIRDS, etc.) do **not** contain prospectus PDFs or bookrunner lists. This project relies on **GOGEL identifiers + ESMA portal scraping + PDF extraction**. FIRDS-style data may later help validate ISINs/LEIs only.
