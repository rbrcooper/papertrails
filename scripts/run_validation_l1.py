#!/usr/bin/env python3
"""L1 validation: benchmark extraction with tier1 vs programme gates."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from validation_common import apply_validation_env, load_tier1_paths, resolve_pdf_path
from processes.pdf_extractor import PDFExtractor
from processes.pipeline_components.validators import (
    compute_allocated_amount,
    filter_underwriter_banks,
)

GROUND_TRUTH = ROOT / "tests" / "ground_truth.json"
OUT = ROOT / "logs" / "validation_l1_results.json"


def normalize_bank(name: str) -> str:
    return (name or "").lower().strip()


def score_banks(expected: list, actual: list) -> dict:
    exp = {normalize_bank(b) for b in expected}
    act = set()
    for b in actual:
        if isinstance(b, dict):
            act.add(normalize_bank(b.get("raw_name", "")))
    missing = exp - act
    extra = act - exp
    exact = exp.issubset(act) and not extra
    return {
        "expected_count": len(exp),
        "actual_count": len(act),
        "missing": sorted(missing),
        "extra": sorted(extra),
        "exact_match": exact,
        "recall": len(exp & act) / len(exp) if exp else 0,
    }


def main():
    apply_validation_env()
    tier1_paths = load_tier1_paths()
    with open(GROUND_TRUTH, encoding="utf-8") as f:
        gt = json.load(f)

    extractor = PDFExtractor(debug_mode=False, use_ai_extraction=True)
    results = []

    for case in gt["test_cases"]:
        doc_kind = case.get("doc_kind", "tier1")
        pdf_path = resolve_pdf_path(case, tier1_paths)
        expected = case["expected"]
        use_ai = doc_kind == "tier1"
        row = {
            "pdf_path": str(case["pdf_path"]),
            "resolved_pdf_path": str(pdf_path.relative_to(ROOT)) if pdf_path.is_relative_to(ROOT) else str(pdf_path),
            "doc_kind": doc_kind,
            "benchmark": case.get("benchmark"),
            "exists": pdf_path.exists(),
            "metadata": {},
            "banks": {},
            "allocation": {},
        }

        if not pdf_path.exists():
            row["error"] = "FILE_MISSING"
            results.append(row)
            continue

        text_probe = extractor.extract_text(str(pdf_path))
        # Tier1 bond docs: always prefer dealer-table / syndicate-section path.
        large = doc_kind == "tier1" or (
            len(text_probe) > 80_000 or pdf_path.stat().st_size > 1_000_000
        )
        if doc_kind == "programme":
            extractor_prog = PDFExtractor(debug_mode=False, use_ai_extraction=False)
            actual = extractor_prog.process_single_pdf(str(pdf_path), section_only=False)
        else:
            actual = extractor.process_single_pdf(str(pdf_path), section_only=large)

        for field in ["issue_date", "maturity_date", "currency", "coupon_rate"]:
            exp = expected["metadata"].get(field)
            act = actual.get("metadata", {}).get(field)
            row["metadata"][field] = {
                "expected": exp,
                "actual": act,
                "match": str(exp).lower() == str(act).lower() if exp is not None else act is None,
            }

        banks_raw = actual.get("extracted_banks", [])
        row["banks"] = score_banks(expected.get("banks", []), banks_raw)
        row["banks"]["role_labels"] = [
            b.get("raw_name") for b in banks_raw
            if isinstance(b, dict) and any(
                x in (b.get("raw_name") or "").lower()
                for x in ("fiscal agent", "clearing system", "any leading bank")
            )
        ]
        row["section_only_used"] = large if doc_kind == "tier1" else False
        row["extraction_method"] = (actual.get("ai_extraction_metadata") or {}).get(
            "extraction_method"
        )
        row["ftws_section_not_found"] = "ftws_section_not_found" in actual.get(
            "validation_flags", []
        )

        issue_size = actual.get("metadata", {}).get("issue_size")
        per_bank, n = compute_allocated_amount(issue_size, banks_raw)
        row["allocation"] = {
            "issue_size": issue_size,
            "n_underwriters": n,
            "per_bank_amount": per_bank,
        }
        results.append(row)

    tier1 = [r for r in results if r.get("doc_kind") == "tier1" and r.get("exists")]
    tier1_exact = sum(1 for r in tier1 if r.get("banks", {}).get("exact_match"))
    programme = [r for r in results if r.get("doc_kind") == "programme"]

    summary = {
        "tier1_exact": f"{tier1_exact}/{len(tier1)}",
        "tier1_exact_count": tier1_exact,
        "tier1_present": len(tier1),
        "programme_cases": len(programme),
        "ship_gate_tier1_exact_ge_2": tier1_exact >= 2 and len(tier1) >= 3,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2)

    print(f"L1 results written to {OUT}")
    print(f"Tier1 exact: {summary['tier1_exact']} (ship gate: {summary['ship_gate_tier1_exact_ge_2']})")
    for r in results:
        name = Path(r.get("resolved_pdf_path", r["pdf_path"])).name
        if not r.get("exists"):
            print(f"  SKIP [{r.get('doc_kind')}] {name}: missing")
            continue
        b = r["banks"]
        print(
            f"  [{r.get('doc_kind')}] {name}: exact={b.get('exact_match')} "
            f"recall={b.get('recall', 0):.0%} method={r.get('extraction_method')}"
        )


if __name__ == "__main__":
    main()
