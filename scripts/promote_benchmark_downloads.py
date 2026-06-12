#!/usr/bin/env python3
"""Copy L2 audit FTWS PDFs into canonical data/downloads company folders."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATHS_FILE = ROOT / "logs" / "benchmark_tier1_paths.json"

DEST = {
    "OMV": ROOT / "data/downloads/OMV",
    "AKER": ROOT / "data/downloads/AKER BP ASA - 549300NFTY73920OYK69",
    "TotalEnergies": ROOT / "data/downloads/TotalEnergies SE",
}


def main():
    if not PATHS_FILE.exists():
        raise SystemExit(f"Missing {PATHS_FILE} — run audit_benchmark_isins.py first")
    with open(PATHS_FILE, encoding="utf-8") as f:
        mapping = json.load(f)
    promoted = {}
    for label, rel in mapping.items():
        src = ROOT / rel
        if not src.exists() or not src.suffix.lower() == ".pdf":
            print(f"SKIP {label}: missing {rel}")
            continue
        dest_dir = DEST.get(label)
        if not dest_dir:
            print(f"SKIP {label}: no dest folder")
            continue
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
        promoted[label] = str(dest.relative_to(ROOT)).replace("\\", "/")
        print(f"OK {label} -> {promoted[label]}")
    with open(PATHS_FILE, "w", encoding="utf-8") as f:
        json.dump(promoted, f, indent=2)
    print(f"Updated {PATHS_FILE}")


if __name__ == "__main__":
    main()
