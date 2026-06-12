# System architecture

## Pipeline orchestration

`processes/main.py` coordinates:

1. **Load companies** — `CompanyListHandler` reads the Urgewald GOGEL 2025 CSV (default path in `--companies-file`), applies `--region-filter` (`all`, `eu`, or comma-separated countries), tracks processed companies.
2. **Scrape** (optional) — `ESMAScraper` per company unless `--skip-scraping`.
3. **Extract** — `PDFExtractor` on each PDF under `data/downloads/<Company>/` (production still globs all PDFs; validation uses explicit paths only).
4. **Validate** — `ExtractionValidator` adds confidence and checks.
5. **Store** — `DatabaseHandler` → SQLite.
6. **Report** — `DataAggregator` / `OutputGenerator` → `data/processed/master_detailed_report.xlsx`.

CLI flags: `--limit-companies`, `--skip-scraping`, `--max-workers`, `--region-filter`, `--output-dir`.

## Company identification (GOGEL + ESMA scoring)

Primary company data comes from **GOGEL 2025 CSV** (LEI, equity ISIN, bond ISINs, subsidiaries). `ESMAScraper._build_company_profile()` merges optional `data/company_profiles.json` aliases on top.

Row scoring (`_compute_multi_signal_score`) uses:

- **ISIN exact match** — dominant signal (≈0.95 weight when hit).
- **LEI match** — same tier as ISIN when present in row metadata.
- Fuzzy issuer name, document type, recency, penalties for noise.

Fuzzy name matching alone is insufficient; GOGEL identifiers are the main precision lever for scraper selection.

## Extraction engine

### Metadata (regex)

`DateExtractor`, `CurrencyExtractor`, `CouponExtractor` — reliable on benchmark final-terms PDFs (see [BENCHMARKS.md](BENCHMARKS.md)).

### Banks (AI + fallback)

- **`AIBankExtractor`** — Ollama `llama3.1:8b` (configurable), primary path.
- **`BankExtractor`** — regex fallback if AI unavailable.

### Smart chunking (and limitations)

1. Scan text for role keywords (manager, arranger, bookrunner, syndicate, agent, …).
2. Send ~1500-char windows around hits to the LLM.
3. Union and dedupe results across chunks.

**Caveats (observed in production debugging):**

- Very large PDFs (e.g. 165k+ chars) often never hit the syndicate table; chunks pick fiscal/clearing boilerplate.
- Unioning all chunks lets **agent/manager** sections add false banks (e.g. Natixis, Citibank) even when the **syndicate** chunk is correct.
- LLM sometimes returns **role labels** as bank names.

Planned improvements: syndicate-first weighting, post-filters, section truncation — [ROADMAP.md](ROADMAP.md).

## Core modules

| Module | Role |
|--------|------|
| `processes/main.py` | Orchestrator |
| `processes/esma_scraper.py` | ESMA portal Selenium scraper |
| `processes/pdf_extractor.py` | Extraction coordinator |
| `processes/pdf_extraction/` | Extractors + text core |
| `processes/database_handler.py` | SQLite + bank normalization |
| `processes/company_list_handler.py` | GOGEL load + progress tracking |
| `processes/pipeline_components/` | Validation, aggregation, Excel output |

## Quality assurance

### Bounded validation (L0–L4)

| Layer | Script | What it proves |
|-------|--------|----------------|
| L0 | `pytest processes/tests/core/test_doc_selection.py` | Doc tier classification |
| L1 | `scripts/run_validation_l1.py` | Extraction vs `tests/ground_truth.json` |
| L2 | `processes/tests/debug/audit_benchmark_isins.py` | ESMA select + download for 3 ISINs |
| L3 | `scripts/run_validation_l3_benchmarks.py` | DB + `allocated_amount` on tier1 PDFs |
| L4 | `scripts/run_validation_l4_benchmarks.py` | `process_company_pdfs` + completeness gates |

Orchestrator: `scripts/run_validation_suite.py`. Details: [VALIDATION_AND_QUALITY.md](VALIDATION_AND_QUALITY.md).

### Download quality triage

`scripts/triage_downloaded_pdfs.py` scores existing PDFs (no Ollama): dealer-table banks, XS ISIN, first-page checks. Full-pool scan (May 2026): **5/277** `good_tier1_candidate`. Production should add a post-download gate before extraction.

### Other QA

- **Ground truth:** `tests/ground_truth.json`
- **Legacy diagnose:** `scripts/diagnose_extraction.py`
- **Smoke test:** `processes/tests/debug/test_csv_ingestion.py`

## Data flow

```
GOGEL CSV → CompanyListHandler → main.py → ESMAScraper → data/downloads/*.pdf
                                                      ↓
                                            PDFExtractor → validators
                                                      ↓
                                            DatabaseHandler → SQLite
                                                      ↓
                                            OutputGenerator → Excel
```

## Out of scope

ESMA regulatory datasets (MiFID, FIRDS bulk feeds, etc.) do not provide prospectus PDFs or bookrunner relationships. This pipeline does not use `esma_data_py` for core extraction.
