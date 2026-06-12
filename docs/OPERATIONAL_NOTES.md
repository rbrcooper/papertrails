# Operational notes

## Data inputs

- **Company list (required):** `data/raw/Urgewald GOGEL 2025 V1.2 with identifiers.csv`
- **Optional profile overrides:** `data/company_profiles.json` — see `docs/examples/company_profiles.example.json`
- **Downloads:** `data/downloads/<Company>/`
- **Dedup cache:** `data/processed/seen_urls.txt`, `data/document_hashes.json`
- **Scraper audit:** `logs/audit/<Company>/esma_rows.csv`
- **Pipeline log:** `logs/workflow.log`, `logs/run_metrics.json`

## ESMA scraper tuning

- **Bond ISIN searches** use the Securities register `sec_isin` field (up to 10 per company).
- **Document policy:** `--doc-policy strict` (default) downloads tier1 final-terms only; `balanced` allows tier2 fallback.
- **Selection audit columns:** `doc_tier`, `selection_reason`, `register_source` in `logs/audit/<Company>/esma_rows.csv`.
- **Part A benchmark audit:** `py -3 processes/tests/debug/audit_benchmark_isins.py` → `logs/audit/benchmark_isin_audit.csv`
- **ISIN/LEI from GOGEL** are the primary match signals; keep GOGEL CSV up to date.
- **Search tokens:** short tokens (e.g. `OMV` not `OMV AG`) improve recall; profiles add aliases/subsidiaries.
- **Score thresholds:** default around `0.55`; raise toward `0.65` for precision, `0.45` for recall during QA.
- **Headless:** set `HEADLESS=true` for unattended runs; use headed mode when the site throttles or renders poorly.
- **Negative keywords:** tune per sector in company profiles to drop structured-note noise.

## Extraction tuning

- Run ground-truth check after model or prompt changes:
  ```bash
  python scripts/diagnose_extraction.py
  ```
- Expect **minutes per PDF** when AI chunking runs (multiple Ollama calls).
- Ollama must be running (`ollama serve`); model `llama3.1:8b` recommended.

## Windows / PowerShell

Redirecting diagnostic output in PowerShell produces **UTF-16LE** files and may mix stderr with stdout. Prefer:

```powershell
python scripts/diagnose_extraction.py | Out-File -Encoding utf8 diag_out.txt
```

Or run from CMD / Git Bash. Legacy parse scripts live in `processes/tests/debug/` if you need to reprocess old captures.

## Quick tests

```bash
python processes/tests/debug/test_csv_ingestion.py
python processes/tests/debug/test_scraper_run.py
python -m processes.main --limit-companies 1 --skip-scraping
```

## Queue + run ledger (pilot ops)

- **Queue preview (no scrape/extract):**

```powershell
py -3 scripts/pipeline_queue.py --region-filter eu --limit 10
py -3 -m processes.main --dry-run --region-filter eu --limit-companies 5
```

- **Single company / retry failures:**

```powershell
py -3 -m processes.main --skip-scraping --company "OMV AG"
py -3 -m processes.main --retry-failed --limit-companies 5
```

- **Per-company run ledger outputs:**
  - `logs/run_ledger.jsonl` (append-only)
  - `data/processed/company_run_status.json` (latest outcome per company)
  - `logs/run_metrics.json` includes `outcome_counts` and `companies[]`

- **PDF quality triage (existing downloads, no ESMA):**

```powershell
py -3 scripts/triage_downloaded_pdfs.py --n 10 --seed 1
```

Outputs: `logs/pdf_quality_report.json`, `logs/pdf_quality_allowlist.json`

Full-pool scan: `py -3 scripts/triage_downloaded_pdfs.py --all` (fast mode, ~1–2 min). See [VALIDATION_AND_QUALITY.md](VALIDATION_AND_QUALITY.md) for L0–L4 layers and why most downloads are trash.

- **GOGEL pilot:** use ledger outcomes (`complete`, `no_tier1`, `scrape_error`) — not `completeness_gates.ship` on small runs.

## Completeness gates

After each pipeline run, see `logs/completeness_gates.json`:

| Gate | Target |
|------|--------|
| G1 tier1_coverage | ≥ 70% ISINs with tier1 doc |
| G2 bank_set_validity | ≥ 80% tier1 docs with valid underwriter set |
| G3 amount_emit_rate | ≥ 95% eligible bonds emit `allocated_amount` |
| G4 benchmark_quality | ≥ 2/3 exact bank sets on AKER/OMV/Total |

**Allocated amount (BBG-style):** `issue_size / n_underwriters` stored per bank in `bond_banks.allocated_amount`.

**Statuses:** `allocated_ok`, `no_tier1_on_esma`, `underwriter_set_incomplete`, `amount_not_emitted`.

```bash
py -3 -m processes.main --doc-policy strict --max-pdf-chars 80000
```

## Current priority

Validate completeness gates on a GOGEL subset; tune syndicate-section extraction for FTWS (OMV) — see [BENCHMARKS.md](BENCHMARKS.md).
