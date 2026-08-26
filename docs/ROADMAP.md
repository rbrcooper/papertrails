# Roadmap

Product scope and kill bar: **[PRODUCT.md](PRODUCT.md)**. Do not resurrect bulk GOGEL-as-goal without updating PRODUCT.md.

## Now (phase 0–1 alert feed)

1. STE-ranked watchlist (`papertrails.build_watchlist`) — top 5 → 50 → 100.
2. ISIN-only poll via existing scraper (Solr + session download) into `data/alerts/pdfs/`.
3. Auto-publish gates → `website/data/deals.json` (no per-PDF approve).
4. Reverse-chron site.
5. Prove ≥1 live non-benchmark download + publish before scaling.

## Next (only after live publish)

- Cron / scheduled `run_alerts`.
- Watchlist top 50 / 100.
- GCEL expansion-ranked slice (same pattern).
- Bank name canonicalization for display.

## Later / not product blockers

- Entity graph, 13F, GEM overlays.
- Flesh out API beyond deals list.
- Scraper selector hardening when ESMA UI breaks.

## Legacy (frozen as product path)

- Unattended full-GOGEL `processes.main` walk.
- Folder-glob extraction of contaminated `data/downloads/`.
- Completeness gates G1–G4 as *product* ship criteria (keep for extractor QA).

## Extractor QA (keep green)

- L0–L4 bounded suite on OMV / AKER / Total.
- Syndicate-first bank extraction improvements — see [BENCHMARKS.md](BENCHMARKS.md).
