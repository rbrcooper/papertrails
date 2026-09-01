# `papertrails/` — alert feed product layer

See **[docs/PRODUCT.md](../docs/PRODUCT.md)** for repo reality, product scope, STE ranking, and kill bar.

## Reuse (do not rebuild)

| Need | Library entrypoint |
|------|--------------------|
| LEI prospectus search + Solr `downloadFile` + session download | `processes.esma_scraper.ESMAScraper` |
| Doc tier / row select / underwriter filter | `processes.pipeline_components.validators` |
| PDF text + dealer-table banks | `ExtractionEngine` + `AIBankExtractor.extract_dealer_management_banks` |
| GOGEL load (related) | `processes.company_list_handler.CompanyListHandler` |

## Do not rebuild

- New post-download quality scorer (triage closed)
- Name search as default (LEI is the discovery key; name stays off on the publish poll)
- Folder glob of `data/downloads/`
- Per-PDF approve CLI
- Parallel bulk GOGEL walk as the product
- Ollama / `PDFExtractor.process_single_pdf` on the product publish path

## Modules

- `build_watchlist.py` — STE-ranked watchlist YAML (LEI eligibility; `--verify-solr` = downloadable FTWS)
- `build_watchlist_topn.py` — thin wrapper around the same builder
- `schema.py` — Deal model + auto-publish gates
- `run_alerts.py` — Solr-first LEI poll → deterministic extract → publish or quarantine

## Coverage refresh

New GOGEL CSV → STE yaml → `--verify-solr` yaml → incremental poll. Until the CSV has the SPV LEI, Enagas-style finance subs stay invisible.

```powershell
py -3 -m papertrails.build_watchlist --top 50 --out papertrails/watchlist.yaml
py -3 -m papertrails.build_watchlist --top 50 --verify-solr --out papertrails/watchlist_top50.yaml
py -3 -m papertrails.run_alerts --watchlist papertrails/watchlist_top50.yaml --isin-limit 1 --headed
```

## Commands

`py -3 -m website.app` is local Flask preview only; public UI is Google AI Studio off `website/data/deals.json` or `/api/deals`.

```powershell
py -3 -m papertrails.run_alerts --only-issuer "Eni SpA" --headed
py -3 -m papertrails.run_alerts --skip-scraping
py -3 -m website.app
```

Reuse: `processes.esma_scraper`, `validators` (tier/select/filter), dealer-table regex. Do not rebuild scorers, name search, folder globs, or approve CLIs.
