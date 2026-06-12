# Extraction benchmarks

**2026-05-26 validation (current):** L1 **3/3 tier1 exact**, L2 **3/3 selected_ok** (ESMA FTWS download), L3/L4 **3/3 allocated_ok**. Tier1 PDFs from L2 audit — see `logs/benchmark_tier1_paths.json`.

Historical note (March 2026 diagnose_extraction run):

| PDF | Metadata | Banks | Alloc $ |
|-----|----------|-------|---------|
| AKER (base prospectus) | all match | 6/6 recall, +1 Natixis | 3bn / 7 banks |
| OMV (FTWS) | all match | 0/6 (wrong entities) | issue_size 0 |
| Total (base prospectus) | maturity mismatch | 5/6 recall | 40bn / 6 banks |

G4 gate: **0/3 exact** — L1 not passed. See `logs/validation_l1_results.json`.

## Summary

| PDF | Size (approx.) | Metadata | Banks |
|-----|----------------|----------|-------|
| AKER BP — Final terms | ~14k chars | All fields match | 6/6 expected; **+1 false positive** (Natixis from “manager” chunk) |
| OMV — Final terms | ~165k chars | All fields match | **0/6** — model returned role labels (“Fiscal Agent”, “Clearing System”, “any leading bank”) and unrelated entities |
| TotalEnergies — Base prospectus | ~21k chars | Issue/currency/coupon match; maturity differs from ground truth (multi-tranche programme doc) | **~5–6/6** — syndicate chunk works; Citibank false positives from agent/dealer chunks; SMBC missed once due to typo (“smb bank eu ag”) |

**Takeaway:** Regex metadata is reliable on these samples. Bank extraction is **not** uniformly high-accuracy; it depends heavily on PDF size and section structure.

## Known failure modes

1. **Large PDFs** — Whole-document text (~100k+ chars) sends chunking to boilerplate (fiscal agent, clearing) instead of syndicate tables.
2. **Chunk union without role weighting** — Agent/manager/dealer chunks add false banks (Natixis, Citibank) while syndicate chunks are correct.
3. **Role labels as bank names** — LLM returns “Fiscal Agent”, “Clearing System”, “any leading bank”.
4. **Concatenated header lines** — One “bank” string containing an entire syndicate sentence (seen in earlier runs).
5. **Unicode in comparisons** — Accent corruption in diff output (`sociΘtΘ gΘnΘrale`) may hide real matches; normalize before compare.

## Performance

With AI chunking enabled, expect **several minutes per PDF** (multiple Ollama calls, ~2 min each). Not suitable for bulk runs without caching or parallelism tuning.

## Regression harness

- **Ground truth:** `tests/ground_truth.json` (5 cases: 3 tier1 + 2 programme)
- **Primary runner:** `py -3 scripts/run_validation_suite.py` (L0–L4)
- **L1 only:** `py -3 scripts/run_validation_l1.py`
- **Legacy:** `scripts/diagnose_extraction.py`
- **Tier1 PDF paths:** `logs/benchmark_tier1_paths.json` (from L2 audit; gitignored locally)

Add new PDFs to `ground_truth.json` after manual verification (e.g. via `scripts/dump_pdf_text.py`). Use explicit paths — do not glob `data/downloads/<company>/*.pdf` in validation.
