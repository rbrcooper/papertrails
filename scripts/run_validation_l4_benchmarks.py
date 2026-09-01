#!/usr/bin/env python3
"""
L4 validation: main.py pipeline slice on 3 tier1 PDFs (--skip-scraping).

Stages one PDF per benchmark company under data/downloads/_l4_benchmark/
so process_company_pdfs does not walk programme/base prospectus files.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from validation_common import apply_validation_env, load_tier1_paths
from processes.main import process_company_pdfs
from processes.pdf_extractor import PDFExtractor
from processes.pipeline_components.validators import (
    ExtractionValidator,
    compute_completeness_gates,
    filter_underwriter_banks,
)
from processes.database_handler import DatabaseHandler

OUT = ROOT / "logs" / "validation_l4_results.json"
GATES_OUT = ROOT / "logs" / "completeness_gates_l4.json"

# Folder names must match main.py sanitized download dirs for these labels.
BENCHMARK_FOLDERS = {
    "AKER": "AKER BP ASA - 549300NFTY73920OYK69",
    "OMV": "OMV",
    "TotalEnergies": "TotalEnergies SE",
}


def stage_tier1_pdf(label: str, src: Path, staging_root: Path):
    folder = BENCHMARK_FOLDERS[label]
    dest_dir = staging_root / folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    for old in dest_dir.glob("*.pdf"):
        old.unlink()
    dest = dest_dir / src.name
    shutil.copy2(src, dest)
    return dest_dir, dest


def main():
    apply_validation_env()
    tier1_paths = load_tier1_paths()
    staging_root = ROOT / "data" / "downloads" / "_l4_benchmark"
    staging_root.mkdir(parents=True, exist_ok=True)

    pdf_extractor = PDFExtractor(debug_mode=False, use_ai_extraction=True)
    validator = ExtractionValidator()
    db = DatabaseHandler(db_path=str(ROOT / "data" / "validation_l4.db"))

    l1_exact = 0
    l1_path = ROOT / "logs" / "validation_l1_results.json"
    if l1_path.exists():
        with open(l1_path, encoding="utf-8") as f:
            l1_exact = json.load(f).get("summary", {}).get("tier1_exact_count", 0)

    run_metrics = {
        "total_companies": 0,
        "companies_succeeded": 0,
        "companies_failed": 0,
        "total_pdfs_processed": 0,
        "pdfs_stored_successfully": 0,
        "isins_in_scope": len(BENCHMARK_FOLDERS),
        "isins_with_tier1": 0,
        "tier1_downloaded": 0,
        "tier1_valid_underwriter_set": 0,
        "eligible_for_allocation": 0,
        "allocated_rows": 0,
        "benchmark_exact_matches": l1_exact,
        "benchmark_role_hallucinations": False,
    }
    results = []

    for label, folder_name in BENCHMARK_FOLDERS.items():
        rel = tier1_paths.get(label)
        if not rel:
            results.append({"benchmark": label, "error": "no_tier1_path", "allocated_ok": False})
            continue
        src = ROOT / rel
        if not src.exists():
            results.append({"benchmark": label, "error": "FILE_MISSING", "pdf_path": rel, "allocated_ok": False})
            continue

        pdf_dir, staged = stage_tier1_pdf(label, src, staging_root)
        run_metrics["total_companies"] += 1
        run_metrics["isins_with_tier1"] += 1
        run_metrics["tier1_downloaded"] += 1
        packages = process_company_pdfs(
            folder_name,
            pdf_dir,
            pdf_extractor,
            validator,
            expected_isins=[],
            max_pdf_chars=80_000,
            pdf_paths=[staged],
            glob_pdfs=False,
        )
        run_metrics["total_pdfs_processed"] += len(packages)

        row = {
            "benchmark": label,
            "company_folder": folder_name,
            "pdf_path": rel,
            "exists": True,
            "allocated_ok": False,
            "completeness_status": "underwriter_set_incomplete",
        }

        for pkg in packages:
            ext = pkg.get("extraction_result") or {}
            banks = filter_underwriter_banks(ext.get("extracted_banks", []))
            issue_size = (ext.get("metadata") or {}).get("issue_size")
            if "ftws_section_not_found" in ext.get("validation_flags", []):
                status = "underwriter_set_incomplete"
            elif not banks:
                status = "underwriter_set_incomplete"
            elif not issue_size:
                status = "amount_not_emitted"
            else:
                status = "allocated_ok"
                row["allocated_ok"] = True
                run_metrics["eligible_for_allocation"] += 1
                run_metrics["allocated_rows"] += len(banks)
            if banks:
                run_metrics["tier1_valid_underwriter_set"] += 1
            row["completeness_status"] = status
            row["validation_is_valid"] = (pkg.get("validation_result") or {}).get("is_valid")

            db.store_extraction_result(folder_name, {
                "filename": Path(pkg["pdf_path"]).name,
                "file_path": pkg["pdf_path"],
                "document_type": ext.get("document_type", "unknown"),
                "extraction_status": "complete",
                "metadata": ext.get("metadata", {}),
                "extracted_banks": ext.get("extracted_banks", []),
                "completeness_status": status,
            })
            run_metrics["pdfs_stored_successfully"] += 1

        if row.get("allocated_ok"):
            run_metrics["companies_succeeded"] += 1
        else:
            run_metrics["companies_failed"] += 1
        results.append(row)

    gate_report = compute_completeness_gates(run_metrics)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"results": results, "run_metrics": run_metrics}, f, indent=2)
    with open(GATES_OUT, "w", encoding="utf-8") as f:
        json.dump(gate_report, f, indent=2)

    ok = sum(1 for r in results if r.get("allocated_ok"))
    present = [r for r in results if r.get("exists")]
    print(f"L4 results written to {OUT}")
    print(f"L4 gates written to {GATES_OUT} (ship={gate_report.get('ship')})")
    print(f"allocated_ok: {ok}/{len(present)} tier1 companies")
    for r in results:
        print(f"  {r.get('benchmark')}: {r.get('completeness_status', r.get('error'))}")
    sys.exit(0 if ok >= 2 and len(present) >= 2 else 1)


if __name__ == "__main__":
    main()
