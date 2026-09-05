# PaperTrails product

Single source of truth for what this project ships. Root README and ROADMAP defer here.

**Read this first**

- Universe: **756** LEI-eligible GOGEL parents → **23** FTWS-live (the live poll set until a `--verify-solr` rebuild).
- Publish path: **dealer-table regex only** — no Ollama.
- Frontend aggregates are **this feed** (~61 deals), not all of GOGEL.
- Cron is off. UK is parked on `cursor/uk-nsm-intake`.
- This file is the product of record; [ROADMAP.md](ROADMAP.md) is chronology.

## Repo reality (2026-08-26)

| Area | Status |
|------|--------|
| Bounded L0–L4 | `logs/validation_suite_summary.json` **ship: true**; L1–L4 **3/3** on OMV / AKER / Total |
| ESMA PDF download | **Works** on L2 audit path: Solr `downloadFile` + Selenium session cookies |
| Solr | In `processes/esma_scraper.py` — HTTP join for URLs; cookies still from browser session |
| Intake contract (2026-08-14) | L2/main **ISIN** audit path; PaperTrails **discovery is company LEI** (phase 3c). No folder glob unless `--glob-pdfs` |
| Aug 2026 EU pilot (5 cos) | Intake held; **0 new PDFs**; ledger `no_tier1` — **yield** problem, not total DL failure |
| Old bulk `data/downloads/` | Triage **5/277** good — legacy loose scrape contamination |
| Extraction (product) | **Dealer-table regex only** — no Ollama on publish path |
| Extraction (QA) | L1–L4 still use AI path on OMV / AKER / Total benchmarks |
| GOGEL file | `data/raw/Urgewald GOGEL 2025 V1.2 with identifiers.csv` |
| Product package | `papertrails/` — thin alert layer over `processes/` |

**Hinge:** PDF download works when a company LEI hits ESMA prospectus rows (`sec_issuerNameList`) plus Solr `downloadFile` and session cookies. The old 15-parent ceiling was a GOGEL **bond-ISIN** poll artefact (STE parsed as 0, four XS probes). Name search stays off on the publish poll.

## Product

**Ship:** reverse-chronological list of EU fossil-fuel bond deals for expansion-ranked GOGEL parents — issuer, ISIN, date, size/currency if present, underwriters, prospectus link. The site feed is `website/data/deals.json` (trackable; not the gitignored root `data/`). Public UI is Google AI Studio off that JSON or `/api/deals`; Flask `website/app.py` is local preview only, not the shipped front. Public JSON has no local filesystem paths; Flask debug is off unless `FLASK_DEBUG=1`.

**Ops:** auto-publish with machine gates. No per-PDF human approve. Failures → `data/alerts/quarantine/`. Same PDF → same banks (`extraction_method=dealer_table_regex`). Empty dealer table → quarantine `no_dealer_table`.

**Not in phase 1–2:** full GOGEL/GCEL backfill, cron, 13F, GIS/GEM, lobby, Excel-as-product, second prospectus source, FIRDS-as-replacement (no bookrunners).

## Watchlist ranking

- **Metric:** `ste_resources_under_development_mmboe` summed by `name_parent` (European decimals parsed, so Eni ranks as an expander).
- **Tie-break:** `production_mmboe`, then name
- **Eligibility:** ≥1 **LEI** under the parent (parent + finance/operating subs). `isin_equity` is kept for scoring only — it is not an ESMA `sec_isin` key.
- **Discovery key:** company LEIs on ESMA prospectus rows (`sec_issuerNameList:*LEI*`). Solr field `issuer_lei:` returns issuer-party records, not downloadable FTWS. UI fallback still uses the `issuer_lei` form field. Name search stays off (`allow_fallback_search=False`).
- **Deal ISIN:** ESMA `sec_isin` on the selected document, not a hit on GOGEL `isins_bonds`.
- **Build:** `py -3 -m papertrails.build_watchlist --top 50` (STE rank). `--verify-solr` (and `build_watchlist_topn`) keeps a parent only when a LEI under `name_parent` has at least one downloadable FTWS on Solr (`sec_docType` FTWS, ISIN length ≥ 12, `downloadFile` from `sec_docRfssId`), not `numFound>0` on any prospectus row.

## Coverage grain

Entity is GOGEL `name_parent`. Discovery is the union of valid 20-character `lei` values on rows under that parent, queried as Solr `sec_issuerNameList:*LEI*`. Not HQ country, not equity ISIN, not GOGEL `isins_bonds`.

This GOGEL file: **1994** legal rows, **1375** parents, **756** LEI-eligible, **23** FTWS-live (`watchlist_top50.yaml` after a full 756 scan — universe ceiling for that snapshot). The live poll set stays those 23 until a `--verify-solr` rebuild. Do **not** add an EU HQ pre-filter: it would drop Aker and Bapco and add nobody.

**Holes (accepted):** a new issuing LEI absent from this CSV is invisible (GOGEL is the master fossil-entity list; no GLEIF crawl); a parent among the 756 that later gets a first downloadable FTWS is missed until `--verify-solr`; no-LEI parents; UK/Nordic/US venues; STDA-only names skipped on purpose.

## Phase 3b (dealer-table regex, 2026-08-27)

Preferred anchors unchanged (`Dealer/Management Group`, `Active Bookrunners`). Fallback only if those miss: `If syndicated` + `names of Managers/Dealers` (page-break gap up to 80 chars); end marker `date of syndication agreement`. Whitelist match is casefold; `known_banks` extras stay exact-case (Vier Gas remains UniCredit only).

`--skip-scraping` re-extract of on-disk PDFs:

**Published (unchanged bank sets):** OMV, TotalEnergies, ESB, Vier Gas (UniCredit only).

**Newly published:** Aker, Enagas, EP Investment, Gasunie, ORLEN, Romgaz.

**Still quarantined (`no_dealer_table`):** A2A (image PDF), EnBW and Siemens (non-syndicated), Iren and MVM (standalone cover, no FTWS dealer table).

## Phase 3c (company-first discovery, 2026-08-27)

GOGEL LEI-eligible parents: **756**. STE rank of **Eni SpA: 10** (`ste_mmboe=5302.86`, 4 LEIs). `papertrails/watchlist.yaml` is this STE list (top 50 + OMV force-include).

**Eni live probe** (`--only-issuer "Eni SpA"`, headed): parent LEI `BUCRF72VH5RBN7X3VL35` → Solr prospectus `numFound=10` (3 FTWS). Finance-sub LEI 2 rows; Vår Energi 4; EniPower 0. Downloaded FTWS **XS3388188586** and **published** (5 underwriters, `dealer_table_regex`). Eni’s four newest GOGEL XS (`XS3225183824` … `XS3223334981`) are Solr `numFound=0` — the XS poll would skip this parent.

**Enagas grain:** parent LEI `numFound=0`; finance-sub `213800H2FQSU5E19V152` `numFound=2`. Parent-LEI-only is the wrong grain.

`--verify-solr` on `watchlist_top50.yaml`: **50** prospectus-live parents (885 LEI probes, 663 of 756 LEI-eligible walked, then stopped). Not a universe ceiling — remaining parents were not scanned.

**Go/no-go cron:** superseded by the STE-top 20 slice below. No Ollama on publish.

## Phase 3d (LEI-ladder yield slice, 2026-08-27)

Live poll of [`papertrails/watchlist_top50.yaml`](../papertrails/watchlist_top50.yaml) (`--max-issuers 20 --isin-limit 1 --headed`). Default [`watchlist.yaml`](../papertrails/watchlist.yaml) is the STE-unverified top 50 and was not used. Report: [`logs/alerts_yield_report.json`](../logs/alerts_yield_report.json) (`skip_scraping: false`).

| Metric | Result |
|--------|--------|
| Cap | STE-top 20 of the 50 LEI-live parents |
| Skips (alert PDF already on disk) | 5 — TotalEnergies, Eni, Aker, ORLEN, Romgaz |
| Attempts | 15 |
| Downloads this run | **9** (all Solr-first HTTP) |
| Published this run | **1** — OMV `DE000BU27014` (issuer already on the feed; 3 underwriters) |
| Quarantine this run | **8** — all `no_dealer_table` |
| `no_tier1` | **6** — ALROSA, DNO, MOL, BlueNord, OKEA, Rex |
| `download_failed` | 0 |
| `not_polled` among the 20 | **0** |
| New issuers published | **0** |
| Feed | **12** deals (was 11). Leftover A2A / EnBW / Iren / MVM / Siemens quarantines unchanged. |

Whole-file overlay in the yield report still shows `not_polled: 21` — that is the unpolled remainder of the 50, not this slice.

New PDFs that missed the dealer-table regex (samples for later extract work, not A2A OCR):

- **Non-syndicated FTWS:** Repsol `XS2343835315` (`If non-syndicated, name of Dealer`).
- **Standalone prospectuses:** Eesti Energia `EE0000001303`, IPC `NO0013671107`, BW Energy `NO0013259663`, Deutsche Rohstoff `DE000A460CG9`, INA `HRINA0RA0007`.
- **Equity supplement:** Meren `CA00829Q1019`.

**RWE `XS2743711298`:** syndicated FTWS; the miss was slash spacing on `Dealer / Management Group` (optional whitespace around `/`), not non-syndicated. `--skip-scraping` (2026-08-28) published it (`n_underwriters=1`, `SMBC Bank EU AG`; whitelist subset). OMV / TotalEnergies / ESB bank sets unchanged.

**Go/no-go cron: No.** Session and download held. New PDFs are mostly `no_dealer_table` (8/9), so extract is the bottleneck. Cron itself stays a later increment. Next extract work is those samples — not A2A OCR, Iren/MVM cover-page JLMs, or Vier Gas all-caps.

## Phase 3f (FTWS-only poll selection, 2026-09-01)

The alert poll fills `--isin-limit` with **downloadable FTWS only**. `classify_doc_tier` / L2 `select_esma_rows` still treat STDA and SUPP as tier1; leftover concatenation after an empty FTWS list is gone. If Solr returned prospectus rows but no downloadable FTWS, the issuer is `no_tier1` and UI `search_and_process` is not called. UI fallback runs only when Solr returned 0 rows, and still keeps FTWS only.

Slot count (`_count_issuer_alert_pdfs`) is downloaded FTWS still on disk (used so UI fallback is not called when an FTWS is already stored). A stored standalone or supplement does not skip the issuer; `skip_isins` still avoids re-downloading that ISIN. Incremental skip (phase 3h) Solr-queries anyway and only downloads a strictly newer FTWS. `--force` (intended with `--only-issuer`) ignores that newer-than cutoff; `skip_isins` still applies. To retry a stored FTWS without `--force`, delete that `ISIN|filename` entry in `data/alerts/seen.json` (no folder glob, no PDF delete).

Several FTWS: newest first. A cheap peek treats a syndicated-managers field of N/A as non-syndicated; try the next FTWS (cap 3). If every peeked FTWS is N/A, keep the newest N/A. Dealer-table regex and cover-page JLMs are unchanged.

**Solr research** (`sec_issuerNameList:*LEI*`) before the live re-poll — downloadable means ISIN length ≥ 12 and `downloadFile`:

| Issuer | numFound | Downloadable FTWS | Downloadable STDA/SUPP |
|--------|----------|-------------------|------------------------|
| Eesti Energia | 1 | 0 | 1 STDA |
| IPC | 3 | 0 | 3 STDA |
| Meren | 2 | 0 | 1 STDA + 1 SUPP (same ISIN) |
| Repsol | 4 | 1 (`XS2343835315`) | 1 STDA |
| BW Energy | 1 | 0 | 1 STDA |
| Deutsche Rohstoff | 3 | 0 | 2 STDA |
| INA | 1 | 0 | 1 STDA |
| ALROSA | 1 | 0 | 0 (STDA row not downloadable) |
| DNO | 4 | 0 | 0 (SECN reject) |

Repsol has no second downloadable FTWS, so `--force` cannot replace the 2021 N/A. Honest keep of that FTWS; do not fall back to STDA.

**Live re-poll** (2026-09-01, headless, `--isin-limit 1`) of Eesti Energia, Meren, and DNO via `poll_watchlist` in `papertrails/run_alerts.py`. Report: [`logs/alerts_yield_report.json`](../logs/alerts_yield_report.json) (`skip_scraping: false`).

| Metric | Result |
|--------|--------|
| Issuers attempted | 3 |
| Solr had rows | 3 |
| Selected FTWS | **0** |
| Dropped STDA/SUPP leftover (unused) | **2** (Eesti STDA; Meren SUPP after one-per-ISIN) |
| UI fallback calls | **0** |
| `no_tier1` (Solr rows, no downloadable FTWS) | **3** |
| New PDFs this run | **0** |

**Go/no-go cron: No.** Unattended production cron is not enabled. Next work is not cron.

## Phase 3h (incremental FTWS poll, 2026-09-01)

Continual-update shape without a cron job. The poll Solr-queries every issuer (no issuer-level slot-full skip). Skip ISINs already in `website/data/deals.json` and already-downloaded seen FTWS. Default does not backfill an older unstored FTWS; `--force` ignores that cutoff but `skip_isins` still holds. A strictly newer FTWS still downloads. Yield report `incremental`: `new_ftws` / `skipped_published` / `na_skipped`. HTTP `downloadFile` stays first. FTWS-only selection is unchanged.

Same-ISIN retry: delete that `ISIN|filename` entry in `data/alerts/seen.json` (no folder glob, no PDF delete).

## Phase 3i (23-parent FTWS-live yield poll, 2026-09-01)

Live poll of all **23** downloadable-FTWS parents in [`papertrails/watchlist_top50.yaml`](../papertrails/watchlist_top50.yaml) (`--isin-limit 1 --headed`, **no** `--max-issuers`). First poll of that file since `--verify-solr` meant downloadable FTWS. Report: [`logs/alerts_yield_report.json`](../logs/alerts_yield_report.json) (`skip_scraping: false`, `generated_at` 2026-09-01T14:46:42Z) with `incremental`.

Incremental skip held: Solr every issuer (`issuers_attempted: 23`, `solr_had_rows: 23`, UI fallback **0**). Published / already-downloaded FTWS idle unless a strictly newer FTWS.

| Metric | Result |
|--------|--------|
| Cap | All 23 FTWS-live parents (no `--max-issuers`) |
| `incremental.new_ftws` | **15** |
| `incremental.skipped_published` | **8** |
| `incremental.na_skipped` | **3** |
| Published this run | **10** — TotalEnergies `XS3305214903`, Aker `XS2341269970`, ORLEN `XS3430816002`, CEZ `XS3373524050`, Enel `XS3358330663`, Engie `FR0014019L14`, EP Investment `XS3281145691`, Iren `XS2906211946`, Snam `XS3406814445`, Vier Gas `XS3343287838` |
| `no_dealer_table` | **5** this run (poll) — Bapco `XS2294167825`, A2A `XS3238204062`, EDF `FR001400ZGF2`, Gasunie `XS3386682952`, Veolia `FR0014017P12`. Overlay then `quarantine_by_reason.no_dealer_table` **25** (includes leftover standalones). Gasunie and Veolia later published at tranche — leftover. |
| `no_tier1` | This-run `selection.no_tier1_solr_no_ftws` **0**. `totals.no_tier1` **10** still includes legacy seen (DNO, BlueNord, …). |
| Feed | Poll **23** deals / **26585** bytes. After leftover: **25** deals / **35967** bytes (`website/data/deals.json`). Unique issuers **18**. |

Leftovers after re-extract of those five: A2A `XS3238204062` is an image PDF (`no_dealer_table`) and stays out. Bapco `XS2294167825` and EDF `FR001400ZGF2` are N/A syndicate fields (`non_syndicated`, dealer not harvested). Gasunie `XS3386682952` and Veolia `FR0014017P12` are published at tranche (not `no_dealer_table`): 650m EUR / programme 7.5bn / 4 underwriters / allocated 162500000, and 500m EUR / programme 22bn / 7 underwriters / allocated 71428571.43.

`totals.not_polled` **0** among the 23. New issuers on the feed: CEZ, Enel, Engie, Iren, Snam, Veolia.

**Go/no-go cron: No.** Unattended cron stays disabled. Session and download held.

**Session persistence spike (2026-09-01):** Chrome `--user-data-dir` and a JSON cookie jar now default to gitignored `data/chrome_profile/` (override `ESMA_CHROME_USER_DATA_DIR` / `ESMA_COOKIE_JAR`); `admitted_esma_download_url` still gates every `downloadFile` GET. Cookie-reuse live was skipped — no jar on disk from a prior attended session. A windowless cookieless HTTP GET of Gasunie FTWS `XS3386682952` (`downloadFile?fileId=50639572`) returned `%PDF-1.7` with no Chrome window. That is a yes for this file without a human window; it does not prove a reused Chrome session for the HTML-fallback case. Unattended cron stays off.

## Phase 0–1 result (2026-08-26)

- Benchmark poll into `data/alerts/pdfs/`: Aker + TotalEnergies downloaded.
- Solr-live STE watchlist poll (`--skip-benchmarks`): **A2A** and **ESB** non-benchmark PDFs downloaded.
- Auto-publish: **ESB (XS2697983869)** published to `website/data/deals.json` (**kill bar met**). A2A quarantined (no dealer-table banks without Ollama).
- Prefer `--verify-solr` (or `build_watchlist_topn.py`): raw STE top parents often have XS ISINs absent from ESMA.
- Top Solr-live ladder file: `papertrails/watchlist_top50.yaml` (2026-08-26: **16** parents with live ESMA ISINs after full eligible scan — not 50; yield ceiling).

## Phase 2 (deterministic quality)

- Publish path never calls Ollama; banks only from `AIBankExtractor.extract_dealer_management_banks`.
- Poll prefers Solr ISIN select + HTTP `downloadFile` before Selenium session/UI search.
- Deal records carry `extraction_method`, `n_underwriters`, `doc_type_code`, `amount` (issued FTWS tranche), `amount_kind` (`tranche` | `programme` | `unknown`), `programme_size` (EMTN/facility ceiling when known), and `allocated_amount` (deal-level and on each `underwriters[]` row). `append_deal` upserts by ISIN (keeps first `published_at`).

Bloomberg DCM league-table credit (public General Guidelines in Bloomberg’s league-table PDFs, e.g. [Global Green Capital Markets Q1 2020](https://data.bloomberglp.com/professional/sites/10/Bloomberg-Global-Green-Capital-Markets-Q1-2020.pdf) and [Global Structured Notes Q1 2020](https://data.bloomberglp.com/professional/sites/10/Bloomberg-Global-Structured-Notes-League-Tables-Q1-2020.pdf)): “Credit is based on the total amount of the offering sold to the public. Full credit is awarded to the sole bookrunning manager or split equally among joint bookrunning managers; unless full, explicit breakdown of bookrunning is provided by an involved party.” Credit is the issued offering (principal; taps/increases as issued amounts), not an EMTN programme ceiling or unsold/undrawn capacity, and is bookrunners only — not full credit to each name. The feed has no bookrunner-vs-dealer split, so `allocated_amount` is that equal split of the **tranche** among the dealer-table underwriters already stored (`compute_allocated_amount`); it is never 1/n of `programme_size`.
- Scale / cron remain later.

### Phase 2 proof (2026-08-26)

- Offline `--skip-scraping`: Total / ESB / OMV upserted with `extraction_method=dealer_table_regex`; A2A + Aker quarantined `no_dealer_table`.
- Live `--only-issuer "Enagas SA" --isin-limit 1`: Solr-first **HTTP downloadFile** succeeded for `XS2751598322` → `data/alerts/pdfs/Enagas SA/…`; extract quarantined `no_dealer_table` (no UI fallback needed for the download).

## Phase 3 (Solr-live yield pass, 2026-08-26)

Full poll of [`papertrails/watchlist_top50.yaml`](papertrails/watchlist_top50.yaml) (`--isin-limit 1 --headed`) + re-extract. Report: [`logs/alerts_yield_report.json`](logs/alerts_yield_report.json).

| Metric | Result |
|--------|--------|
| Solr-live parents | 15 (+ TotalEnergies force-included) |
| PDFs downloaded (seen) | 17 |
| **Published** | **5** — ESB, Vier Gas (new non-benchmark), OMV, TotalEnergies (+ benchmarks) |
| **Quarantine** (`no_dealer_table`) | **11** — A2A, Aker, Enagas, EnBW, EP Investment, Iren, MVM, Gasunie, ORLEN, Siemens, Romgaz |
| **no_tier1** | Bulgarian Energy (+ legacy STE-top noise in seen.json) |
| New poll downloads | 9/9 via Solr-first HTTP; 1/9 published (Vier Gas), 8/9 quarantined |

**Feed-ready:** ESB, Vier Gas, OMV, TotalEnergies (dealer-table regex hits).

**Blocked on regex:** 11 issuers with FTWS/standalone PDFs but no dealer-table match — not ESMA download.

**Go/no-go (2026-08-26, superseded):** extract yield was too low for cron. See phase 3b/3c above.

## Commands

```powershell
py -3 -m papertrails.build_watchlist --top 50 --out papertrails/watchlist.yaml
py -3 -m papertrails.build_watchlist --top 50 --verify-solr --out papertrails/watchlist_top50.yaml
py -3 -m papertrails.run_alerts --watchlist papertrails/watchlist_top50.yaml --isin-limit 1 --headed
py -3 -m papertrails.run_alerts --watchlist papertrails/watchlist.yaml --only-issuer "Eni SpA" --headed
py -3 -m papertrails.run_alerts --watchlist papertrails/watchlist_top50.yaml --only-issuer "Repsol" --force --headed
py -3 -m papertrails.run_alerts --skip-scraping --watchlist papertrails/watchlist.yaml
py -3 -m website.app
```

Legacy bulk walk: `python -m processes.main` (library/debug). Prefer alert runner for the product.

## Kill bar

**Met (2026-08-26):** live non-benchmark ESB `XS2697983869` auto-published to `website/data/deals.json`. Benchmarks alone do not count.

**Phase 3c:** live non-benchmark **Eni** `XS3388188586` auto-published via company LEI (parent the XS poll skipped).
