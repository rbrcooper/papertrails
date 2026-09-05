# `papertrails/` — operator commands

Product of record: [docs/PRODUCT.md](../docs/PRODUCT.md). This file is how to run the feed, not what it is.

## Coverage refresh

New GOGEL CSV → STE yaml → `--verify-solr` yaml → incremental poll. Until the CSV has the SPV LEI, Enagas-style finance subs stay invisible. Do not walk 756 PDFs.

```powershell
py -3 -m papertrails.build_watchlist --top 50 --out papertrails/watchlist.yaml
py -3 -m papertrails.build_watchlist --top 50 --verify-solr --out papertrails/watchlist_top50.yaml
py -3 -m papertrails.run_alerts --watchlist papertrails/watchlist_top50.yaml --isin-limit 1 --headed
```

Live poll set is the 23 FTWS-live parents in `watchlist_top50.yaml` until the next `--verify-solr` rebuild. `watchlist_all_lei.yaml` is the 756 LEI-eligible list (no Solr filter).

## Poll / extract / site

`py -3 -m website.app` is local Flask preview. Public UI is Google AI Studio off `website/data/deals.json` or `/api/deals`. Publish path is dealer-table regex only (no Ollama). Cron stays off.

```powershell
py -3 -m papertrails.run_alerts --watchlist papertrails/watchlist_top50.yaml --isin-limit 1 --headed
py -3 -m papertrails.run_alerts --only-issuer "Eni SpA" --headed
py -3 -m papertrails.run_alerts --skip-scraping
py -3 -m website.app
```

Same-ISIN retry: delete that `ISIN|filename` entry in `data/alerts/seen.json` (no folder glob, no PDF delete). `--force` with `--only-issuer` ignores the newer-than cutoff; `skip_isins` still applies.

## Modules

- `build_watchlist.py` — STE-ranked watchlist YAML (`--verify-solr` = downloadable FTWS)
- `schema.py` — Deal model + auto-publish gates
- `run_alerts.py` — Solr-first LEI poll → regex extract → publish or quarantine
