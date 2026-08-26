# `papertrails/` — alert feed product layer

See **[docs/PRODUCT.md](../docs/PRODUCT.md)** for repo reality, product scope, STE ranking, and kill bar.

## Reuse (do not rebuild)

| Need | Library entrypoint |
|------|--------------------|
| ISIN search + Solr `downloadFile` + session download | `processes.esma_scraper.ESMAScraper` |
| Doc tier / row select / underwriter filter | `processes.pipeline_components.validators` |
| PDF extract | `processes.pdf_extractor.PDFExtractor` |
| GOGEL load (related) | `processes.company_list_handler.CompanyListHandler` |

## Do not rebuild

- New post-download quality scorer (triage closed)
- Name/LEI ESMA search as default
- Folder glob of `data/downloads/`
- Per-PDF approve CLI
- Parallel bulk GOGEL walk as the product

## Modules

- `build_watchlist.py` — STE-ranked watchlist YAML
- `schema.py` — Deal model + auto-publish gates
- `run_alerts.py` — poll → extract → publish or quarantine

## Commands

```powershell
py -3 -m papertrails.build_watchlist --top 5 --verify-solr
py -3 -m papertrails.run_alerts --phase0 --skip-benchmarks
py -3 -m papertrails.run_alerts --skip-scraping --no-ai
py -3 -m website.app
```

Reuse: `processes.esma_scraper`, `validators` (tier/select/filter), extractors. Do not rebuild scorers, name search, folder globs, or approve CLIs.
