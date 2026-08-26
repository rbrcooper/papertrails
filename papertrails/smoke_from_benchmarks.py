"""
Seed data/alerts/seen.json from L2/ground-truth benchmark PDFs, then publish.

Used for smoke when live ESMA poll is slow or yield is zero.
Does not replace phase0 live yield proof.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from papertrails.run_alerts import extract_and_publish  # noqa: E402

SEEN = ROOT / "data" / "alerts" / "seen.json"
DEALS = ROOT / "website" / "data" / "deals.json"
QUAR = ROOT / "data" / "alerts" / "quarantine"

SEEDS = [
    {
        "issuer": "OMV AG",
        "isin": "XS2886118079",
        "file_path": str(
            ROOT
            / "data/downloads/_audit_l2/OMV/Final_terms_including_the_summ_20240905_2f76b574.pdf"
        ),
        "benchmark": "OMV",
        "status": "downloaded",
        "rank": None,
        "ste_mmboe": 0,
    },
    {
        "issuer": "Aker BP ASA",
        "isin": "XS2830454554",
        "file_path": str(
            ROOT
            / "data/downloads/_audit_l2/AKER/Final_terms_including_the_summ_20240529_ee2fb289.pdf"
        ),
        "benchmark": "AKER",
        "status": "downloaded",
        "rank": None,
        "ste_mmboe": 0,
    },
    {
        "issuer": "TotalEnergies SE",
        "isin": "XS2937308737",
        "file_path": str(
            ROOT
            / "data/downloads/_audit_l2/TotalEnergies/Final_terms_including_the_summ_20241120_47bb733a.pdf"
        ),
        "benchmark": "TotalEnergies",
        "status": "downloaded",
        "rank": None,
        "ste_mmboe": 0,
    },
]


def main() -> int:
    records = []
    entries = {}
    for s in SEEDS:
        p = Path(s["file_path"])
        if not p.exists():
            # fall back to ground_truth paths
            alt = {
                "OMV": ROOT
                / "data/downloads/OMV/Final_terms_including_the_summ_20240905_2f76b574.pdf",
                "AKER": ROOT
                / "data/downloads/AKER BP ASA - 549300NFTY73920OYK69/Final_terms_including_the_summ_20240529_ee2fb289.pdf",
                "TotalEnergies": ROOT
                / "data/downloads/TotalEnergies SE/Final_terms_including_the_summ_20241120_46702e01.pdf",
            }.get(s["benchmark"])
            if alt and alt.exists():
                s = dict(s)
                s["file_path"] = str(alt)
                p = alt
            else:
                print(f"Missing PDF for {s['benchmark']}: {p}")
                continue
        key = f"{s['isin']}|{p.name}"
        entries[key] = s
        records.append(s)

    SEEN.parent.mkdir(parents=True, exist_ok=True)
    with SEEN.open("w", encoding="utf-8") as f:
        json.dump({"entries": entries}, f, indent=2)

    stats = extract_and_publish(
        records, deals_path=DEALS, quarantine_dir=QUAR, use_ai=False
    )
    print(json.dumps(stats, indent=2))
    return 0 if stats.get("published", 0) or stats.get("skipped", 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
