#!/usr/bin/env python3
"""List candidate FTWS / base prospectus PDFs under benchmark download dirs (no extraction)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DIRS = {
    "AKER": ROOT / "data/downloads/AKER BP ASA - 549300NFTY73920OYK69",
    "OMV": ROOT / "data/downloads/OMV",
    "TotalEnergies": ROOT / "data/downloads/TotalEnergies SE",
}


def classify(name: str) -> str:
    n = name.lower()
    if "final" in n and "term" in n:
        return "likely_ftws"
    if "base" in n and "prospectus" in n:
        return "likely_programme"
    if "final" in n:
        return "likely_ftws"
    return "unknown"


def main():
    out = {}
    for label, d in DIRS.items():
        entries = []
        if d.is_dir():
            for p in sorted(d.glob("*.pdf")):
                entries.append({
                    "path": str(p.relative_to(ROOT)).replace("\\", "/"),
                    "size_mb": round(p.stat().st_size / 1_048_576, 2),
                    "hint": classify(p.name),
                })
        out[label] = entries
    text = json.dumps(out, indent=2)
    print(text)
    path = ROOT / "logs" / "benchmark_pdf_discovery.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
