# Roadmap

Ordered by impact. See [BENCHMARKS.md](BENCHMARKS.md) for why bank extraction is the main gap.

## 1. Bank extraction (critical)

- Prefer **syndicate / bookrunner** chunks; down-weight or skip agent, fiscal agent, dealer, manager chunks in aggregation.
- Post-filter LLM output: reject known non-banks (`Fiscal Agent`, `Clearing System`, `any leading bank`, etc.).
- Enforce strict JSON schema in `processes/pdf_extraction/extractors/ai_bank_extractor.py`.
- For large PDFs (>50k chars): limit to final-terms / syndicate sections before chunking, not full document.
- Per-chunk cache (already partially present) under `data/test_cache/`.
- Normalize Unicode before bank name comparison.

## 2. Scraper hardening + download quality

- User-Agent rotation and optional proxies (`HTTP_PROXY` / `HTTPS_PROXY`) in `esma_scraper.py`.
- Pass Selenium cookies + referer to `requests` downloads.
- Optional `data/company_profiles.json` for aliases (see `docs/examples/company_profiles.example.json`); GOGEL LEI/ISINs remain primary signals.
- **Post-download quality gate** (dealer table + XS ISIN + readable text) — see [VALIDATION_AND_QUALITY.md](VALIDATION_AND_QUALITY.md); triage found **5/277** existing PDFs usable.
- **Explicit tier1 path manifest** per company; stop globbing all PDFs in `data/downloads/<company>/`.
- Fix issuer/folder clustering (88 Energy, 89 Energy, 1920 Energy junk piles).

## 3. Early validation

- First-page issuer / guarantor / ISIN checks before full LLM extraction (`validators.py` has partial support).
- Discard wrong documents early to save runtime.

## 4. Entity canonicalization

- Expand `banks_canonical.json` / `DatabaseHandler` mapping; wire `processes/utils/bank_standardizer.py`.

## 5. Pipeline ops

- Resume/checkpoints per company; bounded `--max-workers`; metrics in `logs/run_metrics.json`.
- Richer Excel reports with validation flags.

## 6. API and deployment

- Flesh out `website/app.py`; runbooks and env-specific config.

## Success criteria (production)

- Process 100+ companies unattended with graceful retries.
- Metadata extraction stable on final terms.
- Bank extraction: majority exact match on ground-truth set; no role-label false positives.
- Full EU GOGEL pass feasible within acceptable wall-clock (caching + parallelism).
