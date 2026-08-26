# PaperTrails product

Single source of truth for what this project ships. Root README and ROADMAP defer here.

## Repo reality (2026-08-26)

| Area | Status |
|------|--------|
| Bounded L0–L4 | `logs/validation_suite_summary.json` **ship: true**; L1–L4 **3/3** on OMV / AKER / Total |
| ESMA PDF download | **Works** on L2 audit path: Solr `downloadFile` + Selenium session cookies |
| Solr | In `processes/esma_scraper.py` — HTTP join for URLs; cookies still from browser session |
| Intake contract (2026-08-14) | ISIN-only by default; extract this-run paths only; no folder glob unless `--glob-pdfs` |
| Aug 2026 EU pilot (5 cos) | Intake held; **0 new PDFs**; ledger `no_tier1` — **yield** problem, not total DL failure |
| Old bulk `data/downloads/` | Triage **5/277** good — legacy loose scrape contamination |
| Extraction | Regex metadata strong; AI banks **3/3** on FTWS benchmarks |
| GOGEL file | `data/raw/Urgewald GOGEL 2025 V1.2 with identifiers.csv` |
| Product package | `papertrails/` — thin alert layer over `processes/` |

**Hinge:** PDF download works when tier1 row + Solr URL + session cookies line up. Risks: (1) UI/scraper fragility, (2) low tier1 yield for many GOGEL bond ISINs, (3) expanders with no `isins_bonds`. Not “we cannot download PDFs.”

## Product

**Ship:** reverse-chronological list of EU fossil-fuel bond deals for expansion-ranked GOGEL parents — issuer, ISIN, date, size/currency if present, underwriters, prospectus link.

**Ops:** auto-publish with machine gates. No per-PDF human approve. Failures → `data/alerts/quarantine/`.

**Not in phase 1:** full GOGEL/GCEL backfill, 13F, GIS/GEM, lobby, Excel-as-product, second prospectus source, FIRDS-as-replacement (no bookrunners).

## Watchlist ranking

- **Metric:** `ste_resources_under_development_mmboe` summed by `name_parent`
- **Tie-break:** `production_mmboe`, then name
- **Eligibility:** ≥1 **XS** bond ISIN; optional `--verify-solr` keeps only ISINs with ESMA Solr `numFound>0`
- **Ladder:** top 5 (phase 0) → 50 after one live publish → 100 if stable → GCEL later
- **Build:** `py -3 -m papertrails.build_watchlist --top 5` (add `--verify-solr` before live polls)

## Phase 0 result (2026-08-26)

- Benchmark poll into `data/alerts/pdfs/`: Aker + TotalEnergies downloaded.
- Solr-live STE watchlist poll (`--skip-benchmarks`): **A2A** and **ESB** non-benchmark PDFs downloaded.
- Auto-publish: **ESB (XS2697983869)** published to `website/data/deals.json` (kill bar met). A2A quarantined (no dealer-table banks without Ollama).
- Prefer `--verify-solr` (or equivalent Solr-live ISIN pick): raw STE top parents often have XS ISINs absent from ESMA.

## Commands

```powershell
py -3 -m papertrails.build_watchlist --top 5
py -3 -m papertrails.run_alerts --phase0 --headed
py -3 -m papertrails.run_alerts
py -3 -m website.app
```

Legacy bulk walk: `python -m processes.main` (library/debug). Prefer alert runner for the product.

## Kill bar

One *live* non-benchmark watchlist ISIN auto-publishes to `website/data/deals.json`. Benchmarks alone do not count.
