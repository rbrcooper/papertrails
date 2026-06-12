# Validation layers and download quality

**Last updated:** 2026-05-26

This doc explains the **L0–L4 validation harness**, what is passing today, why `data/downloads/` is mostly unusable, and what we are doing about it.

---

## What L0, L1, L2, L3, L4 mean

These are **bounded checks** — each layer tests one slice of the pipeline. They are **not** the same as completeness gates G1–G4 (those measure production batch quality).

| Layer | What it tests | Main script | Pass criteria (benchmarks) |
|-------|----------------|-------------|----------------------------|
| **L0** | Document **selection rules** in code (tier1 vs programme vs reject) | `pytest processes/tests/core/test_doc_selection.py` | All unit tests green |
| **L1** | **Extraction accuracy** on fixed PDFs in `tests/ground_truth.json` | `scripts/run_validation_l1.py` | Tier1 cases: exact metadata + exact bank set (programme cases: metadata only, no Ollama) |
| **L2** | **ESMA search + row pick + PDF download** for 3 benchmark ISINs (OMV, AKER, Total) | `processes/tests/debug/audit_benchmark_isins.py` | 3/3 `selected_ok`, `ground_truth_ok`, `download_ok` in `logs/audit/benchmark_isin_audit.csv` |
| **L3** | **Allocation path** on tier1 benchmark PDFs only (DB write, `allocated_amount`) | `scripts/run_validation_l3_benchmarks.py` | 3/3 `allocated_ok` |
| **L4** | **`process_company_pdfs` slice** + completeness gates on staged tier1 PDFs (no live scrape) | `scripts/run_validation_l4_benchmarks.py` | 3/3 allocated; `logs/completeness_gates_l4.json` ship |

**Full suite:** `py -3 scripts/run_validation_suite.py` (use `--skip-l2` to reuse an existing L2 CSV).

**Important distinction:** L1–L4 use **explicit benchmark paths** (`logs/benchmark_tier1_paths.json`, `tests/ground_truth.json`). They do **not** glob `data/downloads/<company>/*.pdf`. That glob behaviour in production is what caused multi-hour runs and garbage-in extraction.

---

## Current status (2026-05-26)

### Bounded benchmarks — passing

Latest `logs/validation_suite_summary.json`:

- **L0:** pass  
- **L1:** 3/3 tier1 exact  
- **L2:** 3/3 selected, selection, download  
- **L3:** 3/3 allocated  
- **L4:** 3/3 allocated, completeness ship  
- **Overall `ship`:** true  

So: on **three hand-audited FTWS PDFs** (after L2 audit fixes), search → download → extract → allocate works.

### Bulk existing downloads — mostly bad

We ran **PDF quality triage** on everything already under `data/downloads/` (excluding audit/benchmark staging folders):

```powershell
py -3 scripts/triage_downloaded_pdfs.py --all
```

Results (`logs/pdf_quality_report.json`):

| Label | Count | Meaning |
|-------|------:|---------|
| `good_tier1_candidate` | 5 | Readable FTWS-style doc with dealer-table banks + XS ISIN signals |
| `programme_only` | 3 | Tier2 / programme docs (base prospectus, standalone prospectus) |
| `trash` | 269 | Wrong type, unreadable, or tier1 filename with no substance |

**Allowlist:** `logs/pdf_quality_allowlist.json` — only **5 paths**, essentially OMV duplicates + one TotalEnergies FTWS. AKER’s known-good benchmark PDF does **not** pass the cheap dealer-table heuristic (different layout); L1 still passes AKER with full AI extraction.

**Takeaway:** Benchmark harness green ≠ production download folder clean. ~**97%** of files already on disk are not safe inputs for extraction.

---

## Why there is so much junk in `data/downloads/`

### 1. Production scraper pulls more than tier1 FTWS

`main.py` / `esma_scraper.py` can download **many ESMA rows per company** when not in strict audit mode. Rows include supplements, securities notes, base prospectuses, registration documents, and duplicate final-terms filings. Filename often says `Final_terms_…` even when the underlying ESMA row or file content is not the syndicate-bearing issue doc we need.

### 2. Wrong issuer / company folder

Trash clusters in a few folders (from full-pool triage):

- **88 Energy Ltd** — ~100 trash PDFs  
- **89 Energy III LLC** — ~61  
- **1920 Energy LLC** — ~28  

That pattern usually means **issuer matching or search tokens** pulled documents for the wrong legal entity or repeated near-duplicate searches, not that those companies have 100 valid bond issues.

### 3. No post-download quality gate in the main pipeline

L2 audit proves we *can* pick and download the right PDF for 3 ISINs. The **production loop** does not yet run the same verification (or triage) before treating a file as tier1 input. Files land in `data/downloads/` and stay there.

### 4. Dedupe is partial

`data/document_hashes.json` and `seen_urls.txt` reduce exact duplicates but do not stop **different URLs / names for the same useless doc type**, or **many distinct bad rows** per company.

### 5. Folder glob extraction amplifies the problem

If extraction walks every PDF in a company folder, one bad scrape batch triggers hundreds of extractions (and Ollama calls). Validation explicitly avoids this; production should too.

---

## What “only correct data” means operationally

A PDF should only enter extraction if **all** of the following hold:

1. **ESMA selection:** tier1 doc type (FTWS / final terms), correct ISIN/issuer match, `downloadFile` URL, session download OK.  
2. **File sanity:** starts with `%PDF`, readable text, not empty/scanned garbage.  
3. **Content sanity (cheap, no Ollama):** XS ISIN in text, dealer/management-group table with ≥1 bank (see `scripts/triage_downloaded_pdfs.py`).  
4. **Explicit path list:** pipeline consumes a JSON allowlist or per-company **one chosen path**, not `*.pdf` globs.

Benchmark L1 adds a fifth bar for QA: **exact bank set vs ground truth** on reference PDFs.

---

## Progress log

| Date | Work | Outcome |
|------|------|---------|
| 2026-05-26 | L2 audit fixes (`resolve_download_url`, session cookies, row merge by `doc_id`) | 3/3 benchmark download OK |
| 2026-05-26 | Tier1 paths promoted from `_audit_l2` | `logs/benchmark_tier1_paths.json` |
| 2026-05-26 | L1 bank extractor fixes (dealer anchor, substring dedupe) | 3/3 tier1 exact on FTWS PDFs |
| 2026-05-26 | Bounded suite L0–L4 wired | `ship: true` in `logs/validation_suite_summary.json` |
| 2026-05-26 | PDF triage script + full-pool scan | 5/277 good; report + allowlist in `logs/` |

---

## Next steps (planned)

1. **Post-download gate in scraper** — after save, run the same cheap checks as triage; mark row `rejected_quality` and do not enqueue for extraction.  
2. **Stricter `--doc-policy strict`** — default for production; log `selection_reason` and reject tier2/programme unless explicitly overridden.  
3. **Explicit paths manifest** — e.g. `logs/eligible_tier1_paths.json` per company run; L1/L3-style runners and GOGEL pilot read only that file.  
4. **Issuer matching audit** — review why 88 Energy / 89 Energy / 1920 Energy folders accumulate; tighten GOGEL→ESMA company resolution.  
5. **Content-hash dedupe** — one file per SHA256 per company; skip re-download and re-extract.  
6. **Optional:** bounded validation runner over `pdf_quality_allowlist.json` only (no folder glob).

---

## Commands reference

```powershell
# Full bounded validation (benchmarks)
py -3 scripts/run_validation_suite.py
py -3 scripts/run_validation_suite.py --skip-l2

# L2 ESMA audit only
py -3 processes/tests/debug/audit_benchmark_isins.py

# Triage existing downloads (no ESMA, no Ollama)
py -3 scripts/triage_downloaded_pdfs.py --n 10 --seed 1
py -3 scripts/triage_downloaded_pdfs.py --all

# Promote audit PDFs to canonical download paths
py -3 scripts/promote_benchmark_downloads.py
```

**Outputs:** `logs/validation_*`, `logs/pdf_quality_*`, `logs/audit/benchmark_isin_audit.csv`, `logs/benchmark_tier1_paths.json`.

See also [BENCHMARKS.md](BENCHMARKS.md) (extraction failure modes), [OPERATIONAL_NOTES.md](OPERATIONAL_NOTES.md) (scraper tuning), [ROADMAP.md](ROADMAP.md) (remaining production work).
