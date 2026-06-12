# Papertrails Data Pipeline

Extract bond underwriting data from ESMA prospectus PDFs for companies in the **Urgewald GOGEL 2025** dataset. Hybrid extraction: local LLM (Ollama) for banks, regex for dates/currency/coupon.

## Status (May 2026)

| Area | Status |
|------|--------|
| Bounded validation (L0–L4 on 3 benchmark ISINs) | ✅ `ship: true` — see [docs/VALIDATION_AND_QUALITY.md](docs/VALIDATION_AND_QUALITY.md) |
| Metadata extraction (regex) | ✅ Strong on FTWS final terms |
| Bank extraction (AI) | ⚠️ Good on benchmark FTWS; layout-dependent |
| ESMA scraper (benchmark audit) | ✅ 3/3 select + download |
| Bulk `data/downloads/` quality | ❌ ~5/277 usable without triage gate |
| Full GOGEL production pass | 🔲 Not ready |

**Reality check:** extraction on known-good PDFs works; **finding and keeping the right PDF at scale** is the main gap.

Full documentation: **[docs/README.md](docs/README.md)**

## Prerequisites

1. [Ollama](https://ollama.ai/) with `llama3.1:8b`
2. Python 3.8+
3. Chrome (for scraping)

```bash
pip install -r docs/requirements.txt
ollama pull llama3.1:8b
```

Place the GOGEL CSV at:

`data/raw/Urgewald GOGEL 2025 V1.2 with identifiers.csv`

## Run

```bash
python -m processes.main --limit-companies 5
python -m processes.main --region-filter eu
python -m processes.main --skip-scraping
```

`HEADLESS=true` enables headless Chrome.

## Validation & QA

```bash
# Bounded benchmark suite (L0 → L1 → L2 → L3 → L4)
py -3 scripts/run_validation_suite.py

# Legacy single-shot extraction diagnose
python scripts/diagnose_extraction.py

# Triage existing downloads (no ESMA, no Ollama)
py -3 scripts/triage_downloaded_pdfs.py --n 10 --seed 1
```

Ground truth: `tests/ground_truth.json`. See [docs/BENCHMARKS.md](docs/BENCHMARKS.md) and [docs/VALIDATION_AND_QUALITY.md](docs/VALIDATION_AND_QUALITY.md).

## Layout

- `processes/` — `main.py`, scraper, extractors, database, pipeline components
- `scripts/` — validation suite, triage, diagnostics
- `tests/` — ground truth
- `processes/tests/` — unit tests (`core/`) and debug tools (`debug/`)
- `data/` — GOGEL CSV, downloads, processed output (local, gitignored)
- `docs/` — architecture, validation, benchmarks, roadmap, operations
