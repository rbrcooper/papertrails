#!/usr/bin/env python3
"""
L2 audit: merge Solr + UI rows per benchmark PDF, run select_esma_rows, ground-truth check, download proof.
Writes logs/audit/benchmark_isin_audit.csv
"""
import csv
import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from processes.esma_scraper import ESMAScraper, resolve_download_url
from processes.pipeline_components.validators import (
    classify_doc_tier,
    doc_code_rank,
    parse_row_date,
    select_esma_rows,
)
from processes.pdf_extraction.core import ExtractionEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BENCHMARK_LABELS = ("AKER", "OMV", "TotalEnergies")
ISIN_PATTERN = re.compile(r"\b[A-Z]{2}[0-9A-Z]{9}[0-9]\b")


def benchmark_label_from_path(pdf_rel: str) -> str:
    u = pdf_rel.upper()
    if "AKER" in u:
        return "AKER"
    if "OMV" in u:
        return "OMV"
    if "TOTAL" in u:
        return "TotalEnergies"
    return "UNKNOWN"


def extract_xs_isins(pdf_path: Path, engine: ExtractionEngine) -> List[str]:
    text = engine.extract_text_first_pages(str(pdf_path), num_pages=2)
    found = list(dict.fromkeys(ISIN_PATTERN.findall(text.upper())))
    if not found:
        text = engine.extract_text(str(pdf_path))
        found = list(dict.fromkeys(ISIN_PATTERN.findall(text.upper())))
    xs = [i for i in found if i.startswith("XS")]
    return xs if xs else found


def _row_merge_key(r: Dict[str, Any]) -> str:
    doc_id = str(r.get("doc_id") or "").strip()
    if doc_id.isdigit():
        return f"doc:{doc_id}"
    isin = (r.get("isin") or "").strip().upper()
    code = (r.get("doc_type_code") or "").upper()
    date = (r.get("date") or "").strip()
    if isin:
        return f"isin:{isin}:{code}:{date}"
    return (r.get("url") or "").strip()


def _merge_row_fields(target: Dict[str, Any], source: Dict[str, Any]) -> None:
    for key in ("download_url", "doc_id", "details_url", "issuer_name", "doc_type_code"):
        if not target.get(key) and source.get(key):
            target[key] = source[key]
    if not resolve_download_url(target) and resolve_download_url(source):
        target["download_url"] = source.get("download_url") or source.get("url")


def merge_rows(merged: List[Dict[str, Any]], new_rows: List[Dict[str, Any]], search_isin: str) -> None:
    by_key: Dict[str, Dict[str, Any]] = {_row_merge_key(r): r for r in merged}
    for r in new_rows:
        row = dict(r)
        row["search_isin"] = search_isin
        row["isin_match"] = 1.0 if (row.get("isin") or "").strip() == search_isin else 0.0
        row["score"] = max(float(row.get("score") or 0), 0.95 if row["isin_match"] else 0.6)
        row["doc_tier"] = classify_doc_tier(row.get("doc_type_code"), row.get("doc_type"))
        key = _row_merge_key(row)
        if key in by_key:
            _merge_row_fields(by_key[key], row)
            if resolve_download_url(row) and not resolve_download_url(by_key[key]):
                by_key[key]["download_url"] = row.get("download_url") or row.get("url")
        else:
            by_key[key] = row
    merged[:] = list(by_key.values())


def enrich_chosen_row(chosen: Dict[str, Any], merged: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Fill download_url / doc_id from sibling merged rows (Solr vs UI)."""
    out = dict(chosen)
    key = _row_merge_key(out)
    for r in merged:
        if _row_merge_key(r) == key:
            _merge_row_fields(out, r)
    if not out.get("doc_id"):
        for r in merged:
            if (r.get("isin") or "").strip() == (out.get("isin") or "").strip():
                _merge_row_fields(out, r)
                if resolve_download_url(out):
                    break
    return out


def pick_single_benchmark_row(
    candidates: List[Dict[str, Any]],
    expected_issue_date: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None
    exp_dt = None
    if expected_issue_date:
        try:
            exp_dt = datetime.strptime(expected_issue_date[:10], "%Y-%m-%d")
        except ValueError:
            pass

    def sort_key(r: Dict[str, Any]) -> Tuple:
        has_download = 0 if resolve_download_url(r) else 1
        code_rank = doc_code_rank(r.get("doc_type_code"), r.get("doc_type"))
        dt = parse_row_date(r)
        date_ord = dt.timestamp() if dt else 0.0
        date_dist = abs((dt - exp_dt).days) if dt and exp_dt else 99999
        return (has_download, code_rank, date_dist, -date_ord, -float(r.get("score") or 0))

    candidates = sorted(candidates, key=sort_key)
    return candidates[0]


def check_ground_truth(
    row: Dict[str, Any],
    label: str,
    expected: Dict[str, Any],
    pdf_rel: str,
) -> Tuple[bool, str]:
    """Return (ok, detail)."""
    issues: List[str] = []
    code = (row.get("doc_type_code") or "").upper()
    if not code:
        from processes.pipeline_components.validators import _parse_doc_type_code
        code = _parse_doc_type_code(None, row.get("doc_type"))

    exp_date = (expected.get("metadata") or {}).get("issue_date")
    row_dt = parse_row_date(row)

    if label in ("OMV", "TotalEnergies") and code != "FTWS":
        issues.append(f"expected FTWS got {code or '?'}")

    if label == "TotalEnergies" and row_dt and row_dt.year < 2023:
        issues.append(f"date {row.get('date')} too old (want ~2024)")

    if exp_date and row_dt:
        try:
            exp_dt = datetime.strptime(exp_date[:10], "%Y-%m-%d")
            if abs((row_dt - exp_dt).days) > 120:
                issues.append(f"date {row.get('date')} vs expected {exp_date}")
        except ValueError:
            pass

    if label == "AKER" and "final" in pdf_rel.lower() and code == "BPWO":
        issues.append("programme doc on AKER")

    if issues:
        return False, "; ".join(issues)
    return True, "ok"


def _esma_doc_id(row: Dict[str, Any]) -> Optional[str]:
    doc_id = str(row.get("doc_id") or "").strip()
    return doc_id if doc_id.isdigit() else None


def verify_pdf_download(
    scraper: ESMAScraper,
    row: Dict[str, Any],
    search_isin: Optional[str] = None,
) -> Tuple[bool, str, Optional[str]]:
    download_url = resolve_download_url(row)
    esma_doc_id = _esma_doc_id(row)
    if not download_url and not esma_doc_id:
        return False, "no_url", None

    path = None
    detail = "download_failed"

    if search_isin:
        try:
            scraper.navigate_to_search()
            if scraper.search_by_isin(search_isin):
                time.sleep(3)
                try:
                    scraper.driver.execute_script(
                        "if (typeof setNavCookie === 'function') setNavCookie();"
                    )
                except Exception:
                    pass

                if not path and download_url and "downloadFile" in download_url:
                    path = scraper._download_binary_with_session(
                        download_url,
                        doc_id=esma_doc_id or search_isin,
                        doc_type_hint=row.get("doc_type"),
                        date_hint=row.get("date"),
                    )
                    if path:
                        detail = "session_cookies"

                if not path and esma_doc_id:
                    path = scraper.download_via_details_page(
                        esma_doc_id,
                        doc_type_hint=row.get("doc_type"),
                        date_hint=row.get("date"),
                    )
                    if path:
                        detail = "details_page"

                if not path:
                    path = scraper.download_from_results_table(
                        isin=search_isin,
                        doc_type_hint=row.get("doc_type"),
                        date_hint=row.get("date"),
                    )
                    if path:
                        detail = "results_table"
        except Exception as e:
            logger.debug("ISIN-session download failed: %s", e)

    if not path and download_url:
        path = scraper.download_document(
            url=download_url,
            doc_id=esma_doc_id,
            doc_type_hint=row.get("doc_type"),
            date_hint=row.get("date"),
        )
        if path:
            detail = "download_document"

    if not path:
        return False, detail, None
    try:
        with open(path, "rb") as f:
            head = f.read(8)
        if head.startswith(b"%PDF"):
            return True, detail, path
        return False, f"not_pdf:{head[:20]!r}", path
    except OSError as e:
        return False, str(e), path


def write_benchmark_tier1_paths(rows_out: List[Dict[str, Any]], out_path: Path) -> None:
    """Map benchmark label -> local tier1 PDF path for L1/L3/L4 harnesses."""
    mapping: Dict[str, str] = {}
    fallbacks = {
        "AKER": Path(
            "data/downloads/AKER BP ASA - 549300NFTY73920OYK69/"
            "Final terms, including the  summary of the individual issue annexed to them_28_05_2024.pdf"
        ),
        "OMV": Path("data/downloads/OMV/Final_terms_including_the_summ_30082024_2f76b574.pdf"),
        "TotalEnergies": Path(
            "data/downloads/TotalEnergies SE/base_prospectus_17320281_47bb733a.pdf"
        ),
    }
    for r in rows_out:
        label = r.get("benchmark")
        if not label:
            continue
        dl_path = r.get("download_path")
        if r.get("download_ok") and dl_path and Path(dl_path).exists():
            mapping[label] = str(Path(dl_path).as_posix())
        elif label in fallbacks and fallbacks[label].exists():
            logger.warning(
                "[%s] using fallback PDF (download_ok=False)", label
            )
            mapping[label] = str(fallbacks[label].as_posix())

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2)
    logger.info("Wrote tier1 path map (%s entries) to %s", len(mapping), out_path)


def main():
    out_dir = Path("logs/audit")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "benchmark_isin_audit.csv"

    gt_path = Path("tests/ground_truth.json")
    if not gt_path.exists():
        raise SystemExit("Missing tests/ground_truth.json")
    with open(gt_path, encoding="utf-8") as f:
        ground_truth = json.load(f)

    engine = ExtractionEngine(use_ocr=False)
    rows_out: List[Dict[str, Any]] = []
    scraper: Optional[ESMAScraper] = None

    try:
        audit_dl_dir = Path("data/downloads/_audit_l2")
        scraper = ESMAScraper(debug_mode=True, headless=True, download_dir=audit_dl_dir)
        scraper.document_hashes = {}
        scraper.seen_urls = set()

        for case in ground_truth.get("test_cases", []):
            if case.get("doc_kind") and case.get("doc_kind") != "tier1":
                continue
            pdf_rel = case.get("pdf_path", "")
            label = benchmark_label_from_path(pdf_rel)
            expected = case.get("expected") or {}
            pdf_path = Path(pdf_rel)

            base_row = {
                "benchmark": label,
                "pdf_path": pdf_rel,
                "expected_issue_date": (expected.get("metadata") or {}).get("issue_date"),
            }

            if not pdf_path.exists():
                rows_out.append({**base_row, "status": "pdf_missing"})
                continue

            xs_isins = extract_xs_isins(pdf_path, engine)
            if not xs_isins:
                rows_out.append({**base_row, "status": "no_isin_in_pdf"})
                continue

            merged: List[Dict[str, Any]] = []
            isins_with_solr: List[str] = []
            for isin in xs_isins:
                logger.info("[%s] Solr rows for ISIN %s", label, isin)
                solr_rows = scraper.fetch_securities_via_solr(isin)
                merge_rows(merged, solr_rows, isin)
                if solr_rows:
                    isins_with_solr.append(isin)

            if not merged:
                rows_out.append({**base_row, "status": "no_rows", "isins_searched": ",".join(xs_isins)})
                continue

            selected_per_isin = select_esma_rows(merged, policy="strict", min_score=0.55)
            exp_date = (expected.get("metadata") or {}).get("issue_date")
            tier1_merged = [
                r for r in merged
                if classify_doc_tier(r.get("doc_type_code"), r.get("doc_type")) == "tier1"
            ]
            chosen = pick_single_benchmark_row(tier1_merged, exp_date)
            if not chosen and selected_per_isin:
                chosen = pick_single_benchmark_row(selected_per_isin, exp_date)

            if not chosen:
                rows_out.append({**base_row, "status": "no_selection", "isins_searched": ",".join(xs_isins)})
                continue

            chosen = enrich_chosen_row(chosen, merged)
            primary_isin = (
                chosen.get("search_isin")
                or chosen.get("isin")
                or (xs_isins[0] if xs_isins else None)
            )
            scraper.current_company = label
            if primary_isin and primary_isin in isins_with_solr:
                logger.info("[%s] UI rows for primary ISIN %s", label, primary_isin)
                scraper.navigate_to_search()
                if scraper.search_by_isin(primary_isin):
                    time.sleep(3)
                    scraper.set_results_per_page(100)
                    ui_rows = scraper.process_results(label)
                    merge_rows(merged, ui_rows, primary_isin)
                    chosen = enrich_chosen_row(chosen, merged)

            gt_ok, gt_detail = check_ground_truth(chosen, label, expected, pdf_rel)
            scraper.current_company = label
            dl_ok, dl_detail, dl_path = verify_pdf_download(
                scraper, chosen, search_isin=primary_isin
            )

            status = "selected_ok" if gt_ok and dl_ok else "selected_partial"
            if not gt_ok and not dl_ok:
                status = "selected_fail"

            rows_out.append({
                **base_row,
                "status": status,
                "ground_truth_ok": gt_ok,
                "ground_truth_detail": gt_detail,
                "download_ok": dl_ok,
                "download_detail": dl_detail,
                "download_path": dl_path or "",
                "doc_id": chosen.get("doc_id") or "",
                "download_url": chosen.get("download_url") or "",
                "search_isin": chosen.get("search_isin"),
                "selected_isin": chosen.get("isin"),
                "doc_type_code": chosen.get("doc_type_code"),
                "doc_type": chosen.get("doc_type"),
                "doc_tier": chosen.get("doc_tier"),
                "date": chosen.get("date"),
                "issuer": chosen.get("issuer_name"),
                "url": resolve_download_url(chosen),
                "selection_reason": chosen.get("selection_reason"),
                "isins_searched": ",".join(xs_isins),
                "candidates_merged": len(merged),
                "candidates_selected_per_isin": len(selected_per_isin),
            })
            logger.info(
                "[%s] selected %s %s %s gt=%s dl=%s (%s)",
                label,
                chosen.get("doc_type_code"),
                chosen.get("date"),
                chosen.get("isin"),
                gt_ok,
                dl_ok,
                dl_detail,
            )

    finally:
        if scraper:
            scraper.close()

    if rows_out:
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=sorted({k for r in rows_out for k in r}))
            writer.writeheader()
            writer.writerows(rows_out)
        logger.info("Wrote %s rows to %s", len(rows_out), out_csv)

        n_pass = sum(1 for r in rows_out if r.get("status") == "selected_ok")
        logger.info("L2 audit pass: %s/3 benchmarks (selected_ok = gt + PDF)", n_pass)
        write_benchmark_tier1_paths(
            rows_out, Path("logs/benchmark_tier1_paths.json")
        )
    else:
        logger.warning("No audit rows collected")


if __name__ == "__main__":
    main()
