# PaperTrails

Open alert feed for **EU fossil-fuel bond underwriting** from public ESMA prospectuses, ranked by GOGEL short-term expansion (STE).

**Product definition:** [docs/PRODUCT.md](docs/PRODUCT.md) (start here).

## Status

| Area | Status |
|------|--------|
| Product | Alert feed (`papertrails/`) — auto-publish to `website/data/deals.json` |
| Bounded validation L0–L4 | Ship on 3 benchmarks — extractor regression |
| Bulk GOGEL walk via `processes.main` | **Legacy / not the product** |
| ESMA download | Works on audit path (Solr + session cookies); yield varies by ISIN |

## Quick start (product)

```bash
pip install -r docs/requirements.txt
ollama pull llama3.1:8b   # for bank extraction

py -3 -m papertrails.build_watchlist --top 5
py -3 -m papertrails.run_alerts --phase0          # yield proof (poll only)
py -3 -m papertrails.run_alerts                  # poll + extract + publish
py -3 -m website.app                             # http://127.0.0.1:5000/
```

`HEADLESS=false` or `--headed` if ESMA throttles headless Chrome.

## Legacy pipeline (library / debug)

```bash
python -m processes.main --limit-companies 5 --require-bond-isins
python -m processes.main --company "OMV AG" --pdf-paths path/to.pdf
py -3 scripts/run_validation_suite.py
```

Full docs: [docs/README.md](docs/README.md). Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Roadmap: [docs/ROADMAP.md](docs/ROADMAP.md).

## Layout

- `papertrails/` — watchlist, alert runner, schema (product)
- `processes/` — ESMA scraper, extractors, DB (library)
- `website/` — reverse-chron deals page; `website/data/deals.json` is the tracked site feed
- `scripts/` — validation / triage
- `data/` — GOGEL CSV, downloads, alerts (local)
- `docs/` — including PRODUCT.md
