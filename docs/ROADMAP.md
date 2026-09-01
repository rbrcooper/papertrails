# Roadmap

Product scope and kill bar: **[PRODUCT.md](PRODUCT.md)**. Do not resurrect bulk GOGEL-as-goal without updating PRODUCT.md.

## Done (phase 0–1 alert feed)

1. STE-ranked watchlist (`papertrails.build_watchlist`).
2. ESMA poll into `data/alerts/pdfs/` (now company-LEI Solr-first).
3. Auto-publish gates → `website/data/deals.json` (no per-PDF approve).
4. Reverse-chron site (`website/app.py`).
5. Kill bar met (2026-08-26): live non-benchmark **ESB** `XS2697983869` auto-published.

## Done (phase 2 — deterministic quality)

1. Publish path: dealer-table regex only; quarantine `no_dealer_table`; never Ollama.
2. Solr-first download; UI `search_and_process` only as fallback. Name search off on the alert poll.
3. Deal fields: `extraction_method`, `n_underwriters`, `doc_type_code`.

## Done (phase 3 — Solr-live yield pass)

1. Yield report after each run → `logs/alerts_yield_report.json`.
2. Full poll of 15 XS-live parents (2026-08-26): 5 published, 11 `no_dealer_table`. That 15 was a bond-ISIN artefact.

## Done (phase 3b — dealer-table regex, 2026-08-27)

Fallback `If syndicated` + Managers/Dealers (preferred FTWS anchors first). Skip-scraping: 10/15 of the old PDF set published; A2A / EnBW / Siemens / Iren / MVM still quarantined for layout reasons, not download.

## Done (phase 3c — company LEI discovery, 2026-08-27)

Watchlist eligibility is ≥1 LEI under `name_parent`. Poll queries prospectus rows by LEI (`sec_issuerNameList`), not GOGEL XS. Eni STE rank 10; live FTWS `XS3388188586` published. Enagas finance-sub LEI is the live grain, not the parent LEI.

## Done (phase 3d — LEI-ladder yield slice, 2026-08-27)

STE-top 20 of `watchlist_top50.yaml` live-polled (`--isin-limit 1 --headed`). Slice `not_polled` = 0; `download_failed` = 0; 9 downloads / 1 published (OMV `DE000BU27014`) / 8 `no_dealer_table` / 6 `no_tier1`. No new issuers published. Remaining 30 of the 50 unpolled.

## Done (phase 3e — RWE slash-spacing, 2026-08-28)

Preferred-anchor `/` allows optional whitespace. RWE `XS2743711298` published (`n_underwriters=1`). Cron still no-go.

## Done (phase 3f — FTWS-only document selection, 2026-09-01)

Poll path is FTWS-only (`papertrails/run_alerts.py`). Solr leftover STDA/SUPP no longer fills `--isin-limit`. Solr rows without downloadable FTWS → `no_tier1`, no UI fill. Live re-poll of Eesti / Meren / DNO: 0 FTWS selected, 2 STDA/SUPP dropped, 0 UI calls, 3 honest `no_tier1`. Cron still no-go.

## Done (phase 3g — FTWS-live watchlist verify, 2026-09-01)

`--verify-solr` / `build_watchlist_topn` keep a parent only for downloadable FTWS, not prospectus `numFound>0`. Cron still no-go.

## Done (phase 3h — incremental FTWS poll, 2026-09-01)

Poll Solr-queries every issuer. Skip published `deals.json` ISINs and already-downloaded FTWS; only a strictly newer FTWS downloads unless `--force`. Yield `new_ftws` / `skipped_published` / `na_skipped`. Cron still no-go.

## Done (phase 3i — 23-parent FTWS-live yield poll, 2026-09-01)

All 23 downloadable-FTWS parents in `watchlist_top50.yaml` live-polled (`--isin-limit 1 --headed`, no `--max-issuers`). Yield in PRODUCT 3i. Cron still no-go.

## Next

1. **Cron: no-go.** Unattended production cron stays disabled. This increment does not enable it.
2. On-disk standalones/supplements (Eesti, IPC, Meren, …) are no longer poll slots; they remain extract samples only if someone chooses to regex them. Do not reopen A2A OCR or cover-page JLMs.
3. More of the 756 only after extract yield on **this 23** is honest. Coverage refresh is a **yaml rebuild**, not a 756 PDF walk: new GOGEL CSV → `build_watchlist` → `--verify-solr` → `watchlist_top50.yaml` → incremental `run_alerts`. GCEL stays Later.

## Later

- GCEL expansion-ranked slice.
- Bank name canonicalization for display.
- Entity graph, 13F, GEM overlays.

## Legacy (frozen as product path)

- Unattended full-GOGEL `processes.main` walk.
- Folder-glob extraction of contaminated `data/downloads/`.
- Completeness gates G1–G4 as *product* ship criteria (keep for extractor QA).

## Extractor QA (keep green)

- L0–L4 bounded suite on OMV / AKER / Total.
- Syndicate-first bank extraction improvements — see [BENCHMARKS.md](BENCHMARKS.md).
