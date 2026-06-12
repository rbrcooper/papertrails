#!/usr/bin/env python3
"""
Queue inspection helper for GOGEL pilots.

Prints the next N companies given current processed set and last run outcomes.
Does not scrape or extract.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_status() -> dict:
    p = ROOT / "data" / "processed" / "company_run_status.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect pipeline company queue")
    parser.add_argument(
        "--companies-file",
        default=str(ROOT / "data" / "raw" / "Urgewald GOGEL 2025 V1.2 with identifiers.csv"),
        help="Path to the GOGEL data file (.csv or .xlsx)",
    )
    parser.add_argument(
        "--region-filter",
        default="all",
        help="Region filter: 'all', 'eu', or comma-separated country names (default: all)",
    )
    parser.add_argument("--limit", type=int, default=10, help="Number of companies to show")
    parser.add_argument(
        "--include-processed",
        action="store_true",
        help="Include processed companies in output",
    )
    parser.add_argument(
        "--format",
        default="table",
        choices=["table", "json"],
        help="Output format",
    )
    args = parser.parse_args()

    # Lazy import after args so it works when run from repo root.
    from processes.company_list_handler import CompanyListHandler

    h = CompanyListHandler(args.companies_file, region_filter=args.region_filter)
    status = load_status()

    companies = h.get_all_companies()
    if not args.include_processed:
        companies = h.get_unprocessed_companies()

    rows = []
    for c in companies[: args.limit]:
        name = c.get("name", "")
        bond_isins = list(
            dict.fromkeys((c.get("isins_bonds") or []) + (c.get("isins_bonds_subsidiaries") or []))
        )
        bond_isin_count = len([i for i in bond_isins if i and len(i) >= 12])
        st = status.get(name, {})
        rows.append(
            {
                "name": name,
                "country": c.get("country", ""),
                "bond_isin_count": bond_isin_count,
                "processed": name in getattr(h, "processed_companies", set()),
                "last_outcome": st.get("outcome", ""),
                "last_run": st.get("run_timestamp", ""),
            }
        )

    if args.format == "json":
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0

    # Table-ish output without extra deps.
    cols = ["name", "country", "bond_isin_count", "processed", "last_outcome", "last_run"]
    print(" | ".join(cols))
    print("-" * 120)
    for r in rows:
        print(" | ".join(str(r.get(c, "")) for c in cols))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

