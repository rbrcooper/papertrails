"""
Build an expansion-ranked GOGEL watchlist for the alert feed.

Rank metric: parent-level ste_resources_under_development_mmboe (summed).
Tie-break: production_mmboe, then name.
Eligibility: at least one LEI under the parent (parent + finance/operating subs).
--verify-solr: keep only parents with at least one downloadable FTWS under those
LEIs (sec_docType FTWS, ISIN length ≥ 12, downloadFile from sec_docRfssId) —
not prospectus-row numFound>0.
Discovery key is company LEIs, not GOGEL bond ISINs.

Usage:
  py -3 -m papertrails.build_watchlist --top 5
  py -3 -m papertrails.build_watchlist --top 50 --out papertrails/watchlist.yaml
  py -3 -m papertrails.build_watchlist --top 50 --verify-solr --out papertrails/watchlist_top50.yaml
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


def _parse_eu_number(raw: Any) -> float:
    """Parse GOGEL STE/production values, including European decimals (438,11)."""
    if raw is None:
        return 0.0
    try:
        if pd.isna(raw):
            return 0.0
    except (TypeError, ValueError):
        pass
    if isinstance(raw, bool):
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip().replace(" ", "")
    if not s or s in {".", "NA", "nan", "None"}:
        return 0.0
    if re.match(r"^-?\d{1,3}(\.\d{3})+,\d+$", s):
        s = s.replace(".", "").replace(",", ".")
    elif "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _clean_isin(isin: str) -> Optional[str]:
    s = (isin or "").strip().upper()
    if len(s) >= 12 and re.match(r"^[A-Z]{2}[A-Z0-9]+$", s):
        return s
    return None


def _clean_lei(raw: Any) -> Optional[str]:
    s = str(raw or "").strip().upper()
    if len(s) == 20 and re.match(r"^[A-Z0-9]{20}$", s):
        return s
    return None


def _hierarchy_lei_rank(hierarchy: Any) -> int:
    h = str(hierarchy or "").lower()
    if "finance" in h:
        return 1
    if "parent" in h:
        return 0
    return 2


def _load_parent_aggregates(gogel_path: Path) -> List[Dict[str, Any]]:
    df = pd.read_csv(gogel_path, sep=";", encoding="utf-8")
    if METRIC_COLUMN not in df.columns:
        raise SystemExit(f"Missing metric column {METRIC_COLUMN} in {gogel_path}")

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
                "leis": [],
                "_lei_meta": [],
                "isin_equity": "",
                "bond_isins": [],
            },
        )
        bucket["ste_mmboe"] += _parse_eu_number(row.get(METRIC_COLUMN))
        bucket["production_mmboe"] += _parse_eu_number(row.get(PRODUCTION_COLUMN))
        hier = row.get("company_hierarchy")
        lei = _clean_lei(row.get("lei") if pd.notna(row.get("lei")) else "")
        if lei:
            bucket["_lei_meta"].append((_hierarchy_lei_rank(hier), lei))
        eq = _clean_isin(str(row.get("isin_equity") or ""))
        if eq:
            if _hierarchy_lei_rank(hier) == 0:
                bucket["isin_equity"] = eq
            elif not bucket["isin_equity"]:
                bucket["isin_equity"] = eq
        bonds = _parse_multi_value(row.get("isins_bonds")) + _parse_multi_value(
            row.get("isins_bonds_subsidiaries")
        )
        for b in bonds:
            clean = _clean_isin(b)
            if clean and clean not in bucket["bond_isins"]:
                bucket["bond_isins"].append(clean)

    eligible = []
    for v in agg.values():
        ordered: List[str] = []
        for _, lei in sorted(v["_lei_meta"], key=lambda t: t[0]):
            if lei not in ordered:
                ordered.append(lei)
        if not ordered:
            continue
        row = dict(v)
        row.pop("_lei_meta", None)
        row["leis"] = ordered
        row["lei"] = ordered[0]
        eligible.append(row)
    eligible.sort(
        key=lambda x: (-x["ste_mmboe"], -x["production_mmboe"], x["name_parent"].lower())
    )
    return eligible


def _match_benchmark_parent(
    eligible: List[Dict[str, Any]], force: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    needle = force["name_parent"].lower()
    force_isins = set(force.get("bond_isins") or [])
    for row in eligible:
        if needle in row["name_parent"].lower() or row["name_parent"].lower() in needle:
            return row
    if force_isins:
        for row in eligible:
            if force_isins & set(row.get("bond_isins") or []):
                return row
    return None


SOLR_SECURITIES_URL = (
    "https://registers.esma.europa.eu/solr/esma_registers_priii_securities/select"
)
VERIFY_SOLR_QUERY = (
    "sec_issuerNameList:*{lei}* AND sec_docType:FTWS; "
    "ISIN len>=12; downloadFile from sec_docRfssId"
)


def _solr_field(value: Any) -> str:
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value or "").strip()


def _download_url_from_rfss(rfss: Any) -> str:
    """Build downloadFile URL from Solr sec_docRfssId ('fileId,checksum').

    Keep in sync with processes.esma_scraper.download_url_from_rfss.
    Do not import esma_scraper here (Selenium).
    """
    raw = _solr_field(rfss)
    if "," not in raw:
        return ""
    file_id, file_hash = raw.split(",", 1)
    file_id, file_hash = file_id.strip(), file_hash.strip()
    if not file_id.isdigit() or not file_hash:
        return ""
    return (
        "https://registers.esma.europa.eu/publication/downloadFile"
        f"?fileId={file_id}&checksum={file_hash}"
    )


def _is_downloadable_ftws_doc(doc: Dict[str, Any]) -> bool:
    """True only for sec_docType FTWS with ISIN length ≥ 12 and downloadFile."""
    if _solr_field(doc.get("sec_docType")).upper() != "FTWS":
        return False
    if len(_solr_field(doc.get("sec_isin"))) < 12:
        return False
    return "downloadFile" in _download_url_from_rfss(doc.get("sec_docRfssId"))


def solr_lei_has_downloadable_ftws(lei: str, timeout: int = 12) -> bool:
    """HTTP Solr select only. Never GET the PDF / downloadFile URL."""
    lei = (lei or "").strip()
    if not lei:
        return False
    try:
        import requests

        resp = requests.get(
            SOLR_SECURITIES_URL,
            params={
                "q": f"sec_issuerNameList:*{lei}* AND sec_docType:FTWS",
                "rows": 20,
                "wt": "json",
                "fl": "sec_docType,sec_isin,sec_docRfssId",
            },
            headers={"User-Agent": "papertrails-watchlist/1.0"},
            timeout=timeout,
        )
        resp.raise_for_status()
        docs = (resp.json().get("response") or {}).get("docs") or []
    except Exception:
        return False
    return any(_is_downloadable_ftws_doc(d) for d in docs if isinstance(d, dict))


def _issuer_payload(row: Dict[str, Any], rank: Optional[int]) -> Dict[str, Any]:
    leis = list(row.get("leis") or [])
    if row.get("lei") and row["lei"] not in leis:
        leis.insert(0, row["lei"])
    out: Dict[str, Any] = {
        "rank": rank,
        "name_parent": row["name_parent"],
        "lei": leis[0] if leis else (row.get("lei") or ""),
        "leis": leis,
        "isin_equity": row.get("isin_equity") or "",
        "ste_mmboe": round(float(row["ste_mmboe"]), 4),
        "production_mmboe": round(float(row["production_mmboe"]), 4),
    }
    bonds = list(row.get("bond_isins") or [])
    if bonds:
        out["bond_isins"] = bonds[:10]
    return out


def build_watchlist(
    gogel_path: Path,
    top: int,
    include_benchmarks: bool = True,
    verify_solr: bool = False,
    leis_per_parent: int = 8,
) -> Dict[str, Any]:
    eligible = _load_parent_aggregates(gogel_path)
    lei_eligible_total = len(eligible)
    solr_probes = 0
    solr_parents_probed = 0
    live_meta_note = ""

    if verify_solr:
        filtered = []
        for row in eligible:
            solr_parents_probed += 1
            hit = False
            for lei in (row.get("leis") or [])[: max(1, leis_per_parent)]:
                solr_probes += 1
                if solr_lei_has_downloadable_ftws(lei):
                    hit = True
                    break
            if not hit:
                if solr_parents_probed % 10 == 0:
                    print(
                        f"... probed {solr_parents_probed} parents, "
                        f"live={len(filtered)} last_miss={row['name_parent']}",
                        flush=True,
                    )
                continue
            print(
                f"HIT {len(filtered)+1}/{top} {row['name_parent']} "
                f"ste={row['ste_mmboe']} leis={len(row.get('leis') or [])}",
                flush=True,
            )
            filtered.append(dict(row))
            if len(filtered) >= top:
                break
        live_meta_note = (
            f"stopped after {len(filtered)} downloadable-FTWS parents "
            f"(probed {solr_parents_probed} of {lei_eligible_total} LEI-eligible)"
        )
        eligible = filtered

    core = eligible[: max(0, top)]
    core_names = {c["name_parent"] for c in core}

    issuers: List[Dict[str, Any]] = []
    for i, row in enumerate(core, start=1):
        issuers.append(_issuer_payload(row, rank=i))

    if include_benchmarks:
        pool = _load_parent_aggregates(gogel_path) if verify_solr else eligible
        for force in BENCHMARK_FORCE:
            matched = _match_benchmark_parent(pool, force)
            parent_name = matched["name_parent"] if matched else force["name_parent"]
            already = next((r for r in issuers if r["name_parent"] == parent_name), None)
            if already:
                already["benchmark"] = force["benchmark"]
                continue
            payload = _issuer_payload(
                matched
                or {
                    "name_parent": parent_name,
                    "ste_mmboe": 0.0,
                    "production_mmboe": 0.0,
                    "leis": [],
                    "lei": "",
                    "isin_equity": "",
                    "bond_isins": list(force.get("bond_isins") or []),
                },
                rank=None,
            )
            payload["benchmark"] = force["benchmark"]
            payload["force_included"] = matched is None or parent_name not in core_names
            issuers.append(payload)

    return {
        "meta": {
            "gogel_file": str(gogel_path.as_posix()),
            "gogel_version": gogel_path.name,
            "metric_column": METRIC_COLUMN,
            "tiebreak_column": PRODUCTION_COLUMN,
            "aggregation": "sum ste_resources_under_development_mmboe by name_parent",
            "eligibility": (
                "≥1 LEI under name_parent (parent + finance/operating subs)"
                + (
                    "; --verify-solr requires ≥1 downloadable FTWS"
                    if verify_solr
                    else ""
                )
            ),
            "discovery_key": "company LEI on prospectus rows (sec_issuerNameList)",
            "verify_solr": verify_solr,
            "verify_solr_query": VERIFY_SOLR_QUERY if verify_solr else "",
            "top": top,
            "eligible_parents_total": lei_eligible_total,
            "solr_live_parents": len(core) if verify_solr else None,
            "solr_probes": solr_probes if verify_solr else 0,
            "solr_parents_probed": solr_parents_probed if verify_solr else 0,
            "leis_per_parent": leis_per_parent if verify_solr else None,
            "solr_note": live_meta_note,
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
        help=(
            "Keep only parents with ≥1 downloadable FTWS under their LEIs "
            "(sec_docType FTWS, ISIN length ≥ 12, downloadFile; slower). "
            "Not prospectus-row numFound>0."
        ),
    )
    parser.add_argument(
        "--leis-per-parent",
        type=int,
        default=8,
        help="Max LEIs to probe per parent when --verify-solr (parent then finance/operating subs)",
    )
    args = parser.parse_args(argv)

    if not args.gogel.exists():
        raise SystemExit(f"GOGEL file not found: {args.gogel}")

    payload = build_watchlist(
        args.gogel,
        top=args.top,
        include_benchmarks=not args.no_benchmarks,
        verify_solr=bool(args.verify_solr),
        leis_per_parent=int(args.leis_per_parent),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)

    print(
        f"Wrote {len(payload['issuers'])} issuers to {args.out} "
        f"(top={args.top}, lei_eligible={payload['meta']['eligible_parents_total']}, "
        f"solr_live={payload['meta'].get('solr_live_parents')})"
    )
    for row in payload["issuers"]:
        tag = f" [{row['benchmark']}]" if row.get("benchmark") else ""
        n_lei = len(row.get("leis") or [])
        print(
            f"  rank={row.get('rank')} {row['name_parent']}{tag} "
            f"ste={row['ste_mmboe']} leis={n_lei}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
