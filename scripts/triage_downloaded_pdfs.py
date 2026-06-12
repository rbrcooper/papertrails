#!/usr/bin/env python3
"""
Sample PDFs from data/downloads and score quality (bounded, no folder-wide extraction).

Outputs:
  logs/pdf_quality_report.json
  logs/pdf_quality_allowlist.json
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from validation_common import load_tier1_paths
from processes.pipeline_components.validators import (
    ExtractionValidator,
    classify_doc_tier,
    filter_underwriter_banks,
)
from processes.pdf_extraction.core import ExtractionEngine
from processes.pdf_extraction.extractors.ai_bank_extractor import AIBankExtractor
from processes.pdf_extractor import PDFExtractor

ISIN_RE = re.compile(r"\b[A-Z]{2}[0-9A-Z]{9}[0-9]\b")
SKIP_TOP_DIRS = {
    "_audit_l2",
    "_l4_benchmark",
    "_audit_l2_test",
    "temp_downloads",
    "OfficialESMA_Test",
    "Test_Company",
    "Test Company",
    "Unidentified",
    "UnknownCompany",
}
REPORT_OUT = ROOT / "logs" / "pdf_quality_report.json"
ALLOWLIST_OUT = ROOT / "logs" / "pdf_quality_allowlist.json"


def tier_guess_from_filename(name: str) -> str:
    n = name.lower()
    if "final" in n and "term" in n:
        descr = "Final terms, including the summary"
    elif "supplement" in n:
        descr = "Supplement"
    elif "base" in n and "prospectus" in n:
        descr = "Base prospectus without Final terms"
    elif "prospectus" in n:
        descr = "Base prospectus"
    else:
        descr = name
    return classify_doc_tier(None, descr)


def collect_pdfs(exclude: Set[str]) -> List[Path]:
    downloads = ROOT / "data" / "downloads"
    out: List[Path] = []
    if not downloads.is_dir():
        return out
    for p in downloads.rglob("*.pdf"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel in exclude:
            continue
        parts = p.parts
        try:
            idx = parts.index("downloads")
            top = parts[idx + 1] if idx + 1 < len(parts) else ""
        except ValueError:
            top = ""
        if top in SKIP_TOP_DIRS or top.startswith("_"):
            continue
        out.append(p)
    return out


def company_from_path(pdf: Path) -> str:
    try:
        rel = pdf.relative_to(ROOT / "data" / "downloads")
        return rel.parts[0] if rel.parts else pdf.parent.name
    except ValueError:
        return pdf.parent.name


def label_row(row: Dict[str, Any]) -> str:
    if not row.get("is_pdf") or not row.get("text_readable"):
        return "trash"
    tier = row.get("tier_guess")
    if tier == "reject":
        return "trash"
    if tier == "tier2":
        return "programme_only"
    if tier != "tier1":
        return "trash"

    n_banks = row.get("n_underwriters", 0)
    has_meta = row.get("has_issue_date") or row.get("has_currency")
    has_isin = row.get("n_xs_isins", 0) > 0
    if n_banks >= 3 and has_meta and has_isin:
        return "good_tier1_candidate"
    if n_banks >= 2 and has_isin and row.get("quick_pass"):
        return "good_tier1_candidate"
    if n_banks >= 1 and (has_isin or row.get("quick_pass")):
        return "good_tier1_candidate"
    if n_banks >= 2 and has_meta:
        return "good_tier1_candidate"
    return "trash"


def triage_one(
    pdf: Path,
    validator: ExtractionValidator,
    engine: ExtractionEngine,
    dealer_extractor: AIBankExtractor,
    *,
    fast: bool,
) -> Dict[str, Any]:
    rel = pdf.relative_to(ROOT).as_posix()
    company = company_from_path(pdf)
    row: Dict[str, Any] = {
        "path": rel,
        "company_folder": company,
        "size_bytes": 0,
        "is_pdf": False,
        "tier_guess": "unknown",
        "quick_pass": False,
        "quick_reason": "",
        "text_readable": False,
        "n_xs_isins": 0,
        "has_issue_date": False,
        "has_currency": False,
        "has_coupon": False,
        "has_issue_size": False,
        "n_underwriters": 0,
        "n_dealer_table_banks": 0,
        "extraction_method": None,
    }
    if not pdf.exists():
        row["label"] = "trash"
        return row

    row["size_bytes"] = pdf.stat().st_size
    try:
        head = pdf.read_bytes()[:8]
        row["is_pdf"] = head.startswith(b"%PDF")
    except OSError:
        row["label"] = "trash"
        return row

    if not row["is_pdf"]:
        row["label"] = "trash"
        return row

    row["tier_guess"] = tier_guess_from_filename(pdf.name)

    text_sample = engine.extract_text_first_pages(str(pdf), num_pages=2)
    row["text_readable"] = bool(text_sample and len(text_sample) >= 50)
    if text_sample:
        xs = list(dict.fromkeys(ISIN_RE.findall(text_sample.upper())))
        row["n_xs_isins"] = len([i for i in xs if i.startswith("XS")])

    quick = validator.quick_first_page_checks(str(pdf), company, expected_isins=[])
    row["quick_pass"] = bool(quick.get("pass"))
    row["quick_reason"] = quick.get("reason", "")

    if row["tier_guess"] == "tier1" and row["text_readable"]:
        try:
            pex = PDFExtractor(debug_mode=False, use_ai_extraction=False)
            full_text = pex.extract_text(str(pdf)) or ""
            if full_text:
                xs = list(
                    dict.fromkeys(
                        ISIN_RE.findall(full_text[:250_000].upper())
                    )
                )
                row["n_xs_isins"] = len([i for i in xs if i.startswith("XS")])
                dealer_banks = dealer_extractor.extract_dealer_management_banks(full_text)
                row["n_dealer_table_banks"] = len(dealer_banks)
                row["n_underwriters"] = len(filter_underwriter_banks(dealer_banks))
            if not fast:
                ext = pex.process_single_pdf(str(pdf), section_only=False)
                meta = ext.get("metadata") or {}
                row["has_issue_date"] = bool(meta.get("issue_date"))
                row["has_currency"] = bool(meta.get("currency"))
                row["has_coupon"] = bool(meta.get("coupon_rate"))
                row["has_issue_size"] = bool(meta.get("issue_size"))
                if row["n_underwriters"] == 0:
                    row["n_underwriters"] = len(
                        filter_underwriter_banks(ext.get("extracted_banks", []))
                    )
        except Exception as e:
            row["smoke_error"] = str(e)

    row["label"] = label_row(row)
    return row


def main():
    parser = argparse.ArgumentParser(description="Triage downloaded PDFs")
    parser.add_argument("--n", type=int, default=10, help="Number of PDFs to sample")
    parser.add_argument("--seed", type=int, default=1, help="Random seed")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Score all eligible PDFs (fast scan, no full metadata extract)",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=25,
        help="Print progress every N PDFs when using --all",
    )
    args = parser.parse_args()

    exclude = {str((ROOT / v).as_posix()) for v in load_tier1_paths().values()}
    pool = collect_pdfs(exclude)
    if not pool:
        raise SystemExit("No PDFs found under data/downloads")

    rng = random.Random(args.seed)
    if args.all:
        sample = sorted(pool, key=lambda p: str(p).lower())
    else:
        n = min(args.n, len(pool))
        sample = rng.sample(pool, n)

    validator = ExtractionValidator()
    engine = ExtractionEngine(use_ocr=False)
    dealer_extractor = AIBankExtractor(debug_mode=False)
    fast = bool(args.all)
    results: List[Dict[str, Any]] = []
    for i, p in enumerate(sample, start=1):
        results.append(triage_one(p, validator, engine, dealer_extractor, fast=fast))
        if args.all and args.progress_every > 0 and i % args.progress_every == 0:
            print(f"... {i}/{len(sample)} scanned")

    counts: Dict[str, int] = {}
    for r in results:
        counts[r["label"]] = counts.get(r["label"], 0) + 1

    allowlist = [r["path"] for r in results if r["label"] == "good_tier1_candidate"]

    report = {
        "sample_size": len(results),
        "pool_size": len(pool),
        "seed": args.seed,
        "label_counts": counts,
        "results": results,
        "allowlist_count": len(allowlist),
    }

    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    with open(ALLOWLIST_OUT, "w", encoding="utf-8") as f:
        json.dump({"paths": allowlist}, f, indent=2)

    print(f"Pool: {len(pool)} PDFs (excluded {len(exclude)} benchmark paths)")
    print(f"Sampled: {len(results)}")
    print(f"Labels: {counts}")
    print(f"Wrote {REPORT_OUT}")
    print(f"Wrote {ALLOWLIST_OUT} ({len(allowlist)} good tier1 candidates)")
    for r in sorted(results, key=lambda x: x["label"]):
        print(f"  [{r['label']}] {Path(r['path']).name} tier={r['tier_guess']} banks={r.get('n_underwriters', 0)}")


if __name__ == "__main__":
    main()
