"""
Build an expansion-ranked GOGEL watchlist for the alert feed.

Rank metric: parent-level ste_resources_under_development_mmboe (summed).
Tie-break: production_mmboe, then name.
Eligibility: at least one bond ISIN in isins_bonds or isins_bonds_subsidiaries.

Usage:
  py -3 -m papertrails.build_watchlist --top 5
  py -3 -m papertrails.build_watchlist --top 50 --out papertrails/watchlist.yaml
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOGEL = ROOT / "data" / "raw" / "Urgewald GOGEL 2025 V1.2 with identifiers.csv"
DEFAULT_OUT = Path(__file__).resolve().parent / "watchlist.yaml"

METRIC_COLUMN = "ste_resources_under_development_mmboe"
PRODUCTION_COLUMN = "production_mmboe"
# ESMA prospectus register is dominated by international (XS) issues.
# Domestic CO/IN/JP/… ISINs are not useful for this alert product.
ESMA_ISIN_PREFIXES = ("XS",)

BENCHMARK_FORCE = [
    {"name_parent": "OMV", "bond_isins": ["XS2886118079"], "benchmark": "OMV"},
    {"name_parent": "Aker BP", "bond_isins": ["XS2830454554"], "benchmark": "AKER"},
    {
        "name_parent": "TotalEnergies",
        "bond_isins": ["XS2937308737"],
        "benchmark": "TotalEnergies",
    },
]


def _parse_multi_value(raw: Any) -> List[str]:
    if not isinstance(raw, str) or raw.strip() in ("", ".", "NA", "nan"):
        return []
    raw = raw.strip().strip('"')
    return [v.strip() for v in raw.split(";") if v.strip() and v.strip() != "."]


def _clean_isin(isin: str) -> Optional[str]:
    s = (isin or "").strip().upper()
    if len(s) >= 12 and re.match(r"^[A-Z]{2}[A-Z0-9]+$", s):
        return s
    return None


def _load_parent_aggregates(gogel_path: Path) -> List[Dict[str, Any]]:
    df = pd.read_csv(gogel_path, sep=";", encoding="utf-8")
    if METRIC_COLUMN not in df.columns:
        raise SystemExit(f"Missing metric column {METRIC_COLUMN} in {gogel_path}")

    df["_ste"] = pd.to_numeric(df[METRIC_COLUMN], errors="coerce").fillna(0.0)
    df["_prod"] = pd.to_numeric(df.get(PRODUCTION_COLUMN), errors="coerce").fillna(0.0)
    df["_parent"] = df["name_parent"].fillna(df["name_company"]).astype(str).str.strip()

    agg: Dict[str, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        parent = row["_parent"]
        if not parent or parent.lower() in ("nan", "."):
            continue
        bucket = agg.setdefault(
            parent,
            {
                "name_parent": parent,
                "ste_mmboe": 0.0,
                "production_mmboe": 0.0,
                "lei": "",
                "bond_isins": [],
            },
        )
        bucket["ste_mmboe"] += float(row["_ste"])
        bucket["production_mmboe"] += float(row["_prod"])
        lei = str(row.get("lei", "")).strip() if pd.notna(row.get("lei")) else ""
        if lei and len(lei) >= 20 and not bucket["lei"]:
            bucket["lei"] = lei
        bonds = _parse_multi_value(row.get("isins_bonds")) + _parse_multi_value(
            row.get("isins_bonds_subsidiaries")
        )
        for b in bonds:
            clean = _clean_isin(b)
            if clean and clean not in bucket["bond_isins"]:
                bucket["bond_isins"].append(clean)

    def _esma_isins(isins: List[str]) -> List[str]:
        return [i for i in isins if i.startswith(ESMA_ISIN_PREFIXES)]

    eligible = []
    for v in agg.values():
        xs = _esma_isins(v["bond_isins"])
        if not xs:
            continue
        row = dict(v)
        # Prefer XS for polling; keep other ISINs after for reference
        row["bond_isins"] = xs + [i for i in v["bond_isins"] if i not in xs]
        row["esma_bond_isins"] = xs
        eligible.append(row)
    eligible.sort(
        key=lambda x: (-x["ste_mmboe"], -x["production_mmboe"], x["name_parent"].lower())
    )
    return eligible


def _match_benchmark_parent(
    eligible: List[Dict[str, Any]], force: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    needle = force["name_parent"].lower()
    force_isins = set(force["bond_isins"])
    for row in eligible:
        if needle in row["name_parent"].lower() or row["name_parent"].lower() in needle:
            return row
    for row in eligible:
        if force_isins & set(row["bond_isins"]):
            return row
    return None


def _solr_num_found(isin: str, timeout: int = 15) -> int:
    try:
        import requests

        resp = requests.get(
            "https://registers.esma.europa.eu/solr/esma_registers_priii_securities/select",
            params={"q": f"sec_isin:{isin}", "rows": 0, "wt": "json"},
            timeout=timeout,
        )
        resp.raise_for_status()
        return int(resp.json().get("response", {}).get("numFound") or 0)
    except Exception:
        return -1


def _prefer_solr_live_isins(isins: List[str], verify: bool) -> List[str]:
    """Return Solr-live ISINs only when verify=True; cap probes per parent."""
    if not verify or not isins:
        return isins
    live: List[str] = []
    ordered = sorted(set(isins), reverse=True)
    max_probes = min(8, len(ordered))
    for i in ordered[:max_probes]:
        n = _solr_num_found(i)
        if n > 0:
            live.append(i)
            if len(live) >= 2:
                break
    return live


def build_watchlist(
    gogel_path: Path,
    top: int,
    include_benchmarks: bool = True,
    verify_solr: bool = False,
) -> Dict[str, Any]:
    eligible = _load_parent_aggregates(gogel_path)
    if verify_solr:
        filtered = []
        for row in eligible:
            xs = [
                i for i in (row.get("esma_bond_isins") or row["bond_isins"])
                if i.startswith(ESMA_ISIN_PREFIXES)
            ]
            live = _prefer_solr_live_isins(xs, verify=True)
            if not live:
                continue
            row = dict(row)
            row["bond_isins"] = live
            row["esma_bond_isins"] = live
            filtered.append(row)
            if len(filtered) >= top:
                break
        eligible = filtered

    core = eligible[: max(0, top)]
    core_names = {c["name_parent"] for c in core}

    issuers: List[Dict[str, Any]] = []
    for i, row in enumerate(core, start=1):
        bonds = row.get("esma_bond_isins") or row["bond_isins"]
        issuers.append(
            {
                "rank": i,
                "name_parent": row["name_parent"],
                "lei": row.get("lei") or "",
                "bond_isins": bonds[:10],
                "ste_mmboe": round(float(row["ste_mmboe"]), 4),
                "production_mmboe": round(float(row["production_mmboe"]), 4),
            }
        )

    if include_benchmarks:
        existing_isins = {i for row in issuers for i in row["bond_isins"]}
        for force in BENCHMARK_FORCE:
            matched = _match_benchmark_parent(
                _load_parent_aggregates(gogel_path) if verify_solr else eligible,
                force,
            )
            parent_name = matched["name_parent"] if matched else force["name_parent"]
            already = next((r for r in issuers if r["name_parent"] == parent_name), None)
            if already:
                already["benchmark"] = force["benchmark"]
                for bi in reversed(force["bond_isins"]):
                    if bi in already["bond_isins"]:
                        already["bond_isins"].remove(bi)
                    already["bond_isins"].insert(0, bi)
                continue
            if any(bi in existing_isins for bi in force["bond_isins"]):
                continue
            issuers.append(
                {
                    "rank": None,
                    "name_parent": parent_name,
                    "lei": (matched or {}).get("lei", ""),
                    "bond_isins": list(force["bond_isins"]),
                    "ste_mmboe": round(float((matched or {}).get("ste_mmboe", 0.0)), 4),
                    "production_mmboe": round(
                        float((matched or {}).get("production_mmboe", 0.0)), 4
                    ),
                    "benchmark": force["benchmark"],
                    "force_included": matched is None or parent_name not in core_names,
                }
            )
            existing_isins.update(force["bond_isins"])

    return {
        "meta": {
            "gogel_file": str(gogel_path.as_posix()),
            "gogel_version": gogel_path.name,
            "metric_column": METRIC_COLUMN,
            "tiebreak_column": PRODUCTION_COLUMN,
            "aggregation": "sum ste_resources_under_development_mmboe by name_parent",
            "eligibility": "≥1 XS bond ISIN (isins_bonds or subsidiaries); ESMA-relevant",
            "esma_isin_prefixes": list(ESMA_ISIN_PREFIXES),
            "verify_solr": verify_solr,
            "top": top,
            "eligible_parents_total": len(eligible),
        },
        "issuers": issuers,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build STE-ranked GOGEL watchlist")
    parser.add_argument("--gogel", type=Path, default=DEFAULT_GOGEL)
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--no-benchmarks", action="store_true")
    parser.add_argument(
        "--verify-solr",
        action="store_true",
        help="Keep only parents/ISINs with numFound>0 on ESMA Solr (slower)",
    )
    args = parser.parse_args(argv)

    if not args.gogel.exists():
        raise SystemExit(f"GOGEL file not found: {args.gogel}")

    payload = build_watchlist(
        args.gogel,
        top=args.top,
        include_benchmarks=not args.no_benchmarks,
        verify_solr=bool(args.verify_solr),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)

    print(
        f"Wrote {len(payload['issuers'])} issuers to {args.out} "
        f"(top={args.top}, eligible={payload['meta']['eligible_parents_total']})"
    )
    for row in payload["issuers"]:
        tag = f" [{row['benchmark']}]" if row.get("benchmark") else ""
        print(
            f"  rank={row.get('rank')} {row['name_parent']}{tag} "
            f"ste={row['ste_mmboe']} isins={len(row['bond_isins'])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
