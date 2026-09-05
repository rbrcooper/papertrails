# PaperTrails backend next steps

Stale vs phase 4 (61-deal feed, coupon/maturity/roles UI): see [PRODUCT.md](PRODUCT.md) and [ROADMAP.md](ROADMAP.md) Next. Plan below is historical backend packages. Cron stays off.

Plan only. Cron stays off. Public UI is Google AI Studio (out of this plan). Flask is local preview. Do not resurrect `processes.main` as product.

Coverage grain: GOGEL is the master entity list. A new SPV LEI not in the CSV is accepted as invisible. No GLEIF. No EU HQ filter. A2A OCR out. STDA out of the poll.

## Checked (do not redo)

| Item | Status |
|------|--------|
| `Deal.to_dict` / `save_deals` / `append_deal` omit `pdf_path` | Done (`papertrails/schema.py`). Covered in `test_content_gates_publish` + `test_append_deal_public_payload_omits_pdf_path`. Live `website/data/deals.json` has no `pdf_path`. |
| Flask `/api/deals` strips `pdf_path` | Done (`website/app.py` `_public_deals`). **No test.** |
| Flask debug | Done: `debug` only if `FLASK_DEBUG` in `{1,true,yes}`. Default off. **No test.** |
| Flask bind | Implicit Flask default `127.0.0.1` (`app.run(debug=…, port=…)` does not pass `host`). Not locked. **No test.** |
| Incremental poll | Done (phase 3h/3i). Solr every issuer; skip published + seen FTWS; newer FTWS still downloads. |
| FTWS-only selection | Done (phase 3f). STDA/SUPP leftover unused. |
| Coverage loop docs | Done in `papertrails/README.md` (Coverage refresh). Code not required unless that loop is broken. |
| Extract leftovers on the 23 | A2A image PDF stays `no_dealer_table`. Bapco / EDF are N/A syndicate (`non_syndicated`). Gasunie / Veolia published. Not a regex hole. |
| Cron | No-go. Package 5 landed `data/chrome_profile` + cookie jar. 2026-09-01: windowless cookieless `downloadFile` returned `%PDF`; cookie-reuse live skipped (no jar). Cron still off. |

## Constraints (every package)

- Cron stays disabled. No Task Scheduler, no GitHub Action poll, no `HEADLESS` cron recipe.
- No AI Studio HTML / frontend work.
- No `python -m processes.main` as a product command, ship path, or “coverage walk”.
- No A2A OCR, no cover-page JLMs, no STDA-as-slot, no GLEIF, no EU HQ filter.
- No Ollama on publish (`dealer_table_regex` only).

## Rank (cause, not busywork)

1. Host-pin `downloadFile` (open GET).
2. Lock Flask preview bind + tests (debug/`pdf_path` already coded).
3. Coverage refresh (ops; yaml rebuild).
4. Extract leftover — **defer** (not broken).
5. Cookie/session persistence spike — **done** (2026-09-01). Cron still off.
6. Cron — **out**.

Packages 1–3 can run in parallel (no file overlap). Package 5 must follow package 1 (`esma_scraper.py`).

---

## Package 1 — Host-pin ESMA `downloadFile`

**Why.** `download_document` / `resolve_download_url` gate on `"downloadFile" in url`. That accepts any host (`https://evil.example/downloadFile`, `https://registers.esma.europa.eu.attacker/…`). Solr/UI rows can carry attacker-controlled hrefs; the next GET is the product download. Substring `registers.esma.europa.eu not in current_url` elsewhere is the same class of bug; this package pins the **download GET**, not every navigation string.

**Do.** Add one helper (urlparse): `https`, hostname **exactly** `registers.esma.europa.eu` (not suffix/contains), path `/publication/downloadFile`. Normalize relative `/publication/downloadFile?…` against that origin before the check. Use it as the only admit gate in `resolve_download_url` and `download_document` (replace `"downloadFile" in url` as sufficient). Keep `download_url_from_rfss` as the constructor (it already emits that origin).

**Files.** `processes/esma_scraper.py`. New `processes/tests/core/test_esma_download_host.py` only.

**Done when.** Helper rejects `http://`, wrong host, suffix-host, `downloadFile` as query/path on another host, details URLs. Accepts a real `https://registers.esma.europa.eu/publication/downloadFile?fileId=&checksum=` URL and a root-relative path after normalize. `download_document` returns None without GET on rejects (mock `requests.get` / driver). Existing `TestSolrDownloadUrlJoin` still passes.

**Don’t.** Touch `papertrails/build_watchlist.py` (Solr select only; never GETs the PDF; `"downloadFile" in` is on a URL it just built). Don’t touch `run_alerts.py` (inherits `resolve_download_url`). Don’t rewrite Selenium click/href loops in this package. Don’t enable cron.

---

## Package 2 — Flask preview: bind lock + tests

**Why.** Public feed is `website/data/deals.json` / `/api/deals`. Debug and `pdf_path` stripping are already implemented; they are untested. Bind is an implicit Flask default, so a copied `host="0.0.0.0"` or `FLASK_HOST` later would publish the preview (and the debugger if someone also sets `FLASK_DEBUG`). Cause is “local preview must stay loopback and path-free,” not new UI.

**Do.** In `website/app.py`: explicit loopback bind (`127.0.0.1`). Refuse non-loopback hosts (including `0.0.0.0`). Keep debug gated on `FLASK_DEBUG`. Extract a tiny bind/debug helper so tests do not `app.run()`. Tests: default debug False; `FLASK_DEBUG=1` True; default host loopback; `0.0.0.0` refused; `/api/deals` omits `pdf_path` even when the file contains it; `_public_deals` / `_load_payload` same.

**Files.** `website/app.py`. New `processes/tests/core/test_website_app.py` only. Do not add these tests to `test_papertrails_alerts.py`.

**Done when.** `pytest processes/tests/core/test_website_app.py` green without starting Chrome or writing the real `deals.json`. Helper (or `__main__` kwargs) never uses `host="0.0.0.0"`.

**Don’t.** AI Studio. Flask as shipped front. New routes, auth, or HTTPS. Changing `schema.py` (already strips on write). Binding to LAN “for convenience.”

---

## Package 3 — Coverage refresh (ops)

**Why.** New issuing LEIs appear only when Urgewald ships a new GOGEL CSV. `--verify-solr` is the FTWS-live ceiling for that file; incremental `run_alerts` then downloads only a strictly newer FTWS. This is the coverage loop. It is already documented in `papertrails/README.md`. Code is not the bottleneck unless that loop is broken.

**Do.** When a new CSV lands (not on a schedule):

```powershell
# point --gogel at the new file if it is not the default path
py -3 -m papertrails.build_watchlist --top 50 --out papertrails/watchlist.yaml
py -3 -m papertrails.build_watchlist --top 50 --verify-solr --out papertrails/watchlist_top50.yaml
py -3 -m papertrails.run_alerts --watchlist papertrails/watchlist_top50.yaml --isin-limit 1 --headed
```

Commit yaml + `website/data/deals.json` if the poll published. Record parent count vs previous 23 in PRODUCT only if the operator is already editing that doc.

**Files.** None for code. Inputs: new GOGEL CSV under `data/raw/`. Outputs: `papertrails/watchlist.yaml`, `papertrails/watchlist_top50.yaml`, `website/data/deals.json`, `logs/alerts_yield_report.json`. Touch `build_watchlist.py` / `run_alerts.py` **only if** the commands fail or the README loop is wrong.

**Done when.** `--verify-solr` yaml is FTWS-downloadable parents only (not prospectus `numFound>0`). Incremental run Solr-queries all of them; `download_failed` is 0 or explained; no STDA fill; no UI fallback when Solr had rows. New SPV LEI absent from CSV is still missing (accepted).

**Don’t.** Walk 756 PDFs. EU HQ filter. GLEIF. Cron. `--force` on the full list. `processes.main`. Rebuild yaml from the old CSV “to be sure.”

---

## Package 4 — Extract leftover — DEFER

**Why.** After the 23-parent poll + leftover re-extract: published dealer-table hits are the product. Remaining misses are A2A (image PDF — OCR stays out) and Bapco/EDF (N/A syndicate — already `non_syndicated`, not `no_dealer_table`). On-disk STDA/standalones (Eesti, IPC, Meren, …) are not poll slots. There is no remaining syndicated-FTWS regex miss on that set (Gasunie/Veolia/RWE slash-spacing already shipped).

**Do.** Nothing unless a **syndicated** FTWS with a selectable dealer table fails `extract_dealer_management_banks`. Optional ops-only: `py -3 -m papertrails.run_alerts --skip-scraping --watchlist papertrails/watchlist_top50.yaml` and read `quarantine_by_reason`. If that surfaces a text-layer syndicated miss, open a **new** package then (`ai_bank_extractor.py` + `test_doc_selection.py` dealer tests).

**Files.** None now.

**Done when.** N/A (deferred). Honest leftover remains A2A image + N/A syndicate.

**Don’t.** A2A OCR. Iren/MVM cover JLMs. Vier Gas all-caps. STDA regex. Harvesting `If non-syndicated, name of Dealer` as underwriters. Expanding `_FTWS_DEALER_LEGAL_NAMES` “just in case.”

---

## Package 5 — Cookie/session persistence spike — DONE (2026-09-01)

**Why.** Unattended cron is blocked by ESMA PDF bytes, not by watchlist math. HTTP `downloadFile` often works; when it returns HTML, the GET needs cookies from a live Chrome session on `registers.esma.europa.eu`. Headless is not the same as cookieless-unattended.

**What landed.** `setup_chrome_options` sets `--user-data-dir` to gitignored `data/chrome_profile/` (uc keeps that profile on quit). JSON jar `data/chrome_profile/esma_cookies.json` is dumped from Selenium cookies (ESMA host only) on close / download GET, and reused on the next `downloadFile` HTTP GET when the live driver has none. Host-pin unchanged: `admitted_esma_download_url` is still the only admit gate. Env: `ESMA_CHROME_USER_DATA_DIR`, `ESMA_COOKIE_JAR`. Tests: `processes/tests/core/test_esma_session_persist.py`. Probe: `processes/tests/debug/probe_esma_session_persist.py`.

**Result (2026-09-01).** Windowless `downloadFile` PDF magic: **yes** — cookieless HTTP GET of Gasunie FTWS `XS3386682952` (`https://registers.esma.europa.eu/publication/downloadFile?fileId=50639572&checksum=4cd64dd4e69bc1303f0f97c4c1181df9`) returned `%PDF-1.7`; no Chrome window. Cookie-reuse across runs: **not proven** — live skipped, no usable jar / empty profile (no prior attended dump). HTML-fallback session reuse remains untested. **Cron still off** either way.

**Don’t.** Enable cron, Task Scheduler, or CI poll. Commit cookie files. Treat headed `--headed` yield polls as “unattended.” Change poll selection or extract in the spike.

---

## Package 6 — Cron — OUT

**Why.** Same as Package 5. Windowless HTTP can return `%PDF` for some `downloadFile` URLs; reused Chrome session for the HTML-fallback case is unproven. PRODUCT go/no-go is No.

**Do.** Nothing.

**Files.** None.

**Done when.** Cron remains off.

**Don’t.** Add cron docs, enable flags, or “just run headless nightly.”

---

## Schema / feed JSON

**Accept as done.** Public payload has no local paths. `append_deal` upserts by ISIN. Amount is tranche; `allocated_amount` is 1/n of tranche. Live feed has no `pdf_path`. Package 2 tests the Flask strip as regression lock. No schema field work in this plan.

## Watchlist rebuild vs poll

Rebuild (`--verify-solr`) changes **who is eligible**. Incremental poll changes **which new FTWS downloads**. Do not conflate. `--force` is `--only-issuer` retry, not coverage.

## CLI (refresh)

```powershell
py -3 -m papertrails.build_watchlist --top 50 --out papertrails/watchlist.yaml
py -3 -m papertrails.build_watchlist --top 50 --verify-solr --out papertrails/watchlist_top50.yaml
py -3 -m papertrails.run_alerts --watchlist papertrails/watchlist_top50.yaml --isin-limit 1 --headed
py -3 -m papertrails.run_alerts --watchlist papertrails/watchlist.yaml --only-issuer "Eni SpA" --headed
py -3 -m papertrails.run_alerts --watchlist papertrails/watchlist_top50.yaml --only-issuer "Repsol" --force --headed
py -3 -m papertrails.run_alerts --skip-scraping --watchlist papertrails/watchlist.yaml
py -3 -m website.app
```

`run_alerts` also: `--phase0`, `--max-issuers`, `--benchmarks-only`, `--skip-benchmarks`, `--seen`, `--pdf-root`, `--deals`, `--quarantine`. Default watchlist is `papertrails/watchlist.yaml` (STE unverified). Live poll file is `watchlist_top50.yaml`.
