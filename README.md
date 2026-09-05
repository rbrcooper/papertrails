# PaperTrails

Open alert feed for **EU fossil-fuel bond underwriting** from public ESMA final terms (FTWS), ranked by GOGEL short-term expansion (STE).

**Ships now:** ESMA FTWS alert feed on **23 FTWS-live** parents (universe **756** LEI-eligible) — about **61** deals in `website/data/deals.json`. Cron is off. UK is parked on `cursor/uk-nsm-intake`.

**Start here:** [docs/PRODUCT.md](docs/PRODUCT.md) (source of truth). History: [docs/ROADMAP.md](docs/ROADMAP.md).

## Map

| Path | Role |
|------|------|
| `papertrails/` | Product — watchlist, poll, auto-publish |
| `website/` | Product — tracked feed `website/data/deals.json`; Flask preview |
| `frontend/` | Product — Vite/React UI of **this feed** (not all GOGEL) |
| `processes/` | Library — ESMA scraper, extractors, DB. **Do not move.** |
| `processes.main` | Frozen — bulk GOGEL walk; not the product |
| Ollama on publish | Frozen — dealer-table regex only |
| `data/downloads/` | Frozen — contaminated legacy scrape; do not glob |

Operator commands: [papertrails/README.md](papertrails/README.md). Studio merge rules: [frontend/README.md](frontend/README.md).

## Commands

```powershell
pip install -r docs/requirements.txt

py -3 -m papertrails.run_alerts --watchlist papertrails/watchlist_top50.yaml --isin-limit 1 --headed
py -3 -m papertrails.run_alerts --skip-scraping
py -3 -m website.app
```

`--headed` if ESMA throttles headless Chrome. Unattended cron is not enabled.
