#!/usr/bin/env python3
"""
Bounded validation suite: L0 → L1 → L2 → L3 → L4.

Tier1 ship gate: L1 tier1_exact >= 2/3; L3 allocated_ok on tier1 PDFs present.
L2: ESMA selection + PDF download audit (selection 3/3 required; download may use fallbacks).
"""
import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from validation_common import apply_validation_env, load_benchmark_cases

SUMMARY_OUT = ROOT / "logs" / "validation_suite_summary.json"
L2_CSV = ROOT / "logs" / "audit" / "benchmark_isin_audit.csv"


def run_py(args: list[str]) -> int:
    cmd = [sys.executable] + args
    print(f"\n>>> {' '.join(cmd)}\n")
    return subprocess.call(cmd, cwd=str(ROOT))


def _parse_l2_csv() -> dict:
    if not L2_CSV.exists():
        return {"pass": False, "selected_ok": "0/3", "selection_ok": "0/3", "download_ok": "0/3"}
    with open(L2_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    n = len(rows)
    sel_ok = sum(1 for r in rows if str(r.get("ground_truth_ok", "")).lower() == "true")
    dl_ok = sum(1 for r in rows if str(r.get("download_ok", "")).lower() == "true")
    selected_ok = sum(1 for r in rows if r.get("status") == "selected_ok")
    return {
        "selected_ok": f"{selected_ok}/{n}",
        "selection_ok": f"{sel_ok}/{n}",
        "download_ok": f"{dl_ok}/{n}",
        "pass": sel_ok >= 3 and selected_ok >= 3 and dl_ok >= 3,
    }


def main():
    parser = argparse.ArgumentParser(description="Bounded validation suite")
    parser.add_argument(
        "--skip-l2",
        action="store_true",
        help="Skip ESMA audit (use existing benchmark_isin_audit.csv)",
    )
    args = parser.parse_args()
    apply_validation_env()
    tier1_cases = [c for c in load_benchmark_cases() if c.get("doc_kind") == "tier1"]
    missing = [c["pdf_rel"] for c in tier1_cases if not c["pdf_path"].exists()]
    if missing:
        print("Missing tier1 benchmark PDFs:")
        for m in missing:
            print(f"  - {m}")

    summary = {"stages": {}, "ship": False}

    rc = run_py(["-m", "pytest", "processes/tests/core/test_doc_selection.py", "-q", "--tb=no"])
    summary["stages"]["L0"] = {"pass": rc == 0, "exit_code": rc}
    if rc != 0:
        _write(summary)
        sys.exit(rc)

    rc = run_py(["scripts/run_validation_l1.py"])
    summary["stages"]["L1"] = {"pass": False, "exit_code": rc}
    l1_path = ROOT / "logs" / "validation_l1_results.json"
    if l1_path.exists():
        with open(l1_path, encoding="utf-8") as f:
            l1 = json.load(f)
        s = l1.get("summary", {})
        summary["stages"]["L1"]["tier1_exact"] = s.get("tier1_exact", "?")
        summary["stages"]["L1"]["pass"] = s.get("ship_gate_tier1_exact_ge_2", False)

    if args.skip_l2:
        l2 = _parse_l2_csv()
        l2["skipped"] = True
        summary["stages"]["L2"] = l2
    else:
        rc = run_py(["processes/tests/debug/audit_benchmark_isins.py"])
        l2 = _parse_l2_csv()
        l2["exit_code"] = rc
        summary["stages"]["L2"] = l2

    rc = run_py(["scripts/run_validation_l3_benchmarks.py"])
    summary["stages"]["L3"] = {"pass": False, "exit_code": rc}
    l3_path = ROOT / "logs" / "validation_l3_results.json"
    if l3_path.exists():
        with open(l3_path, encoding="utf-8") as f:
            l3 = json.load(f)
        present = [r for r in l3 if r.get("exists")]
        ok = sum(1 for r in present if r.get("allocated_ok"))
        summary["stages"]["L3"]["allocated_ok"] = f"{ok}/{len(present)}"
        summary["stages"]["L3"]["pass"] = ok >= 2 and len(present) >= 2

    rc = run_py(["scripts/run_validation_l4_benchmarks.py"])
    summary["stages"]["L4"] = {"pass": False, "exit_code": rc}
    l4_path = ROOT / "logs" / "validation_l4_results.json"
    gates_path = ROOT / "logs" / "completeness_gates_l4.json"
    if l4_path.exists():
        with open(l4_path, encoding="utf-8") as f:
            l4 = json.load(f)
        ok = sum(1 for r in l4.get("results", []) if r.get("allocated_ok"))
        summary["stages"]["L4"]["allocated_ok"] = f"{ok}/3"
    if gates_path.exists():
        with open(gates_path, encoding="utf-8") as f:
            gates = json.load(f)
        summary["stages"]["L4"]["completeness_ship"] = gates.get("ship", False)
        summary["stages"]["L4"]["pass"] = summary["stages"]["L4"].get("allocated_ok", "").startswith(
            "3/"
        ) or gates.get("ship", False)

    summary["ship"] = all(
        summary["stages"].get(s, {}).get("pass")
        for s in ("L0", "L1", "L3")
    )
    _write(summary)

    print("\n=== Validation suite summary ===")
    print(json.dumps(summary, indent=2))
    print(f"\nShip (L0+L1+L3): {'YES' if summary['ship'] else 'NO'}")
    sys.exit(0 if summary["ship"] else 1)


def _write(summary: dict) -> None:
    SUMMARY_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_OUT, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
