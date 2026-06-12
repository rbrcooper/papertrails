#!/usr/bin/env python3
"""L3 validation: tier1 benchmark PDFs only (from ground_truth + tier1 path overrides)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from validation_common import apply_validation_env, company_label, load_benchmark_cases
from processes.pdf_extractor import PDFExtractor
from processes.pipeline_components.validators import (
    ExtractionValidator,
    compute_allocated_amount,
    filter_underwriter_banks,
)
from processes.database_handler import DatabaseHandler

OUT = ROOT / "logs" / "validation_l3_results.json"


def main():
    apply_validation_env()
    cases = [c for c in load_benchmark_cases() if c.get("doc_kind") == "tier1"]
    extractor = PDFExtractor(debug_mode=False, use_ai_extraction=True)
    validator = ExtractionValidator()
    db = DatabaseHandler(db_path=str(ROOT / "data" / "validation_l3.db"))
    results = []

    for case in cases:
        pdf_path = case["pdf_path"]
        label = company_label(case["company"])
        row = {
            "company": label,
            "benchmark": case.get("benchmark"),
            "pdf_path": str(pdf_path.relative_to(ROOT)) if pdf_path.is_relative_to(ROOT) else str(pdf_path),
            "exists": pdf_path.exists(),
            "allocated_ok": False,
            "completeness_status": "missing_pdf",
        }
        if not pdf_path.exists():
            results.append(row)
            continue

        text_probe = extractor.extract_text(str(pdf_path))
        large = True  # tier1 only: syndicate/dealer-table path
        quick = validator.quick_first_page_checks(
            str(pdf_path), label, expected_isins=[], max_pdf_chars=80_000
        )
        ext = extractor.process_single_pdf(
            str(pdf_path), section_only=large or quick.get("section_only", False)
        )
        banks = filter_underwriter_banks(ext.get("extracted_banks", []))
        issue_size = (ext.get("metadata") or {}).get("issue_size")
        per_bank, n = compute_allocated_amount(issue_size, ext.get("extracted_banks", []))
        status = "underwriter_set_incomplete"
        if banks and per_bank:
            status = "allocated_ok"
            row["allocated_ok"] = True

        row["completeness_status"] = status
        row["n_underwriters"] = n
        row["per_bank_amount"] = per_bank
        row["issue_size"] = issue_size
        row["extraction_method"] = (ext.get("ai_extraction_metadata") or {}).get("extraction_method")

        db.store_extraction_result(label, {
            "filename": pdf_path.name,
            "file_path": str(pdf_path),
            "document_type": ext.get("document_type", "unknown"),
            "extraction_status": "complete",
            "metadata": ext.get("metadata", {}),
            "extracted_banks": ext.get("extracted_banks", []),
            "completeness_status": status,
        })
        results.append(row)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    ok = sum(1 for r in results if r.get("allocated_ok"))
    present = [r for r in results if r.get("exists")]
    print(f"L3 results written to {OUT}")
    print(f"allocated_ok: {ok}/{len(present)} tier1 benchmark PDFs")
    for r in results:
        print(f"  {r.get('benchmark')}: {r.get('completeness_status')} n={r.get('n_underwriters', 0)}")


if __name__ == "__main__":
    main()
