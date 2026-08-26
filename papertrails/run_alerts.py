"""
PaperTrails alert runner.

Hinge: tier1 yield on watchlist ISINs + ESMA UI/session stability.
PDF download is proven on L2 benchmarks (Solr downloadFile + session cookies).
This module does not invent a second pipeline — it wraps processes.esma_scraper
and existing extractors, then auto-publishes through schema content gates.

Usage:
  py -3 -m papertrails.run_alerts --watchlist papertrails/watchlist.yaml
  py -3 -m papertrails.run_alerts --skip-scraping --pdf-map logs/alerts_pdf_map.json
  py -3 -m papertrails.run_alerts --phase0   # poll only, no extract/publish
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from papertrails.schema import (  # noqa: E402
    append_deal,
    content_gates,
    write_quarantine,
)
from processes.esma_scraper import ESMAScraper  # noqa: E402
from processes.pdf_extractor import PDFExtractor  # noqa: E402

logger = logging.getLogger("papertrails.run_alerts")

DEFAULT_WATCHLIST = Path(__file__).resolve().parent / "watchlist.yaml"
DEFAULT_SEEN = ROOT / "data" / "alerts" / "seen.json"
DEFAULT_PDF_ROOT = ROOT / "data" / "alerts" / "pdfs"
DEFAULT_QUARANTINE = ROOT / "data" / "alerts" / "quarantine"
DEFAULT_DEALS = ROOT / "website" / "data" / "deals.json"


def _load_watchlist(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_seen(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"entries": {}}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _save_seen(path: Path, seen: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(seen, f, indent=2)


def _seen_key(isin: str, doc_hint: str = "") -> str:
    return f"{isin.upper()}|{doc_hint}".strip("|")


def poll_watchlist(
    watchlist: Dict[str, Any],
    *,
    seen_path: Path,
    pdf_root: Path,
    headless: bool,
    max_issuers: Optional[int] = None,
    isin_limit_per_issuer: int = 3,
    benchmarks_only: bool = False,
    skip_benchmarks: bool = False,
) -> List[Dict[str, Any]]:
    """ISIN-only ESMA poll + session download. Returns download records."""
    seen = _load_seen(seen_path)
    entries: Dict[str, Any] = seen.setdefault("entries", {})
    issuers = list(watchlist.get("issuers") or [])
    if benchmarks_only:
        issuers = [i for i in issuers if i.get("benchmark")]
    elif skip_benchmarks:
        issuers = [i for i in issuers if not i.get("benchmark")]
    if max_issuers is not None:
        issuers = issuers[:max_issuers]

    pdf_root.mkdir(parents=True, exist_ok=True)
    scraper = ESMAScraper(download_dir=str(pdf_root), debug_mode=True, headless=headless)
    downloads_out: List[Dict[str, Any]] = []

    try:
        for issuer in issuers:
            name = issuer["name_parent"]
            isins = list(issuer.get("bond_isins") or [])[:isin_limit_per_issuer]
            pending = []
            for i in isins:
                matched = [
                    entries[k]
                    for k in entries
                    if k.startswith(i.upper() + "|")
                ]
                has_alert_pdf = False
                for m in matched:
                    fp = m.get("file_path")
                    if not fp or m.get("status") != "downloaded":
                        continue
                    p = Path(fp)
                    try:
                        p.resolve().relative_to(pdf_root.resolve())
                        if p.exists():
                            has_alert_pdf = True
                            break
                    except ValueError:
                        # Outside alerts/pdfs (e.g. smoke seed from _audit_l2) — do not skip poll
                        continue
                if not has_alert_pdf:
                    pending.append(i)
            if not pending:
                logger.info("Skip %s — all ISINs already downloaded", name)
                continue

            if benchmarks_only and not issuer.get("benchmark"):
                continue
            if skip_benchmarks and issuer.get("benchmark"):
                continue

            company_data = {
                "name": name,
                "lei": issuer.get("lei") or "",
                "isins_bonds": pending,
                "isins_bonds_subsidiaries": [],
            }
            logger.info(
                "Polling %s (rank=%s benchmark=%s) ISINs=%s",
                name,
                issuer.get("rank"),
                issuer.get("benchmark"),
                company_data["isins_bonds"],
            )
            try:
                downloads = scraper.search_and_process(
                    name,
                    company_data=company_data,
                    doc_policy="strict",
                    allow_fallback_search=False,
                )
            except Exception as e:
                logger.exception("Scrape error for %s: %s", name, e)
                for isin in company_data["isins_bonds"]:
                    entries[_seen_key(isin, "error")] = {
                        "issuer": name,
                        "error": str(e),
                        "benchmark": issuer.get("benchmark"),
                    }
                continue

            if not downloads:
                for isin in company_data["isins_bonds"]:
                    key = _seen_key(isin, "no_tier1")
                    entries[key] = {
                        "issuer": name,
                        "status": "no_tier1",
                        "benchmark": issuer.get("benchmark"),
                        "ste_mmboe": issuer.get("ste_mmboe"),
                        "rank": issuer.get("rank"),
                    }
                logger.warning("no_tier1 for %s", name)
                continue

            for d in downloads:
                isin = (d.get("isin") or "").upper()
                fp = d.get("file_path")
                key = _seen_key(isin, Path(fp).name if fp else "doc")
                rec = {
                    "issuer": name,
                    "isin": isin,
                    "file_path": fp,
                    "doc_tier": d.get("doc_tier"),
                    "status": "downloaded",
                    "benchmark": issuer.get("benchmark"),
                    "ste_mmboe": issuer.get("ste_mmboe"),
                    "rank": issuer.get("rank"),
                    "source_url": None,
                }
                entries[key] = rec
                downloads_out.append(rec)
                logger.info("Downloaded %s → %s", isin, fp)
    finally:
        try:
            scraper.close()
        except Exception:
            pass
        _save_seen(seen_path, seen)

    return downloads_out


def extract_and_publish(
    records: List[Dict[str, Any]],
    *,
    deals_path: Path,
    quarantine_dir: Path,
    max_pdf_chars: int = 80000,
    use_ai: bool = True,
) -> Dict[str, int]:
    stats = {"published": 0, "quarantine": 0, "skipped": 0}
    if not records:
        return stats

    extractor = PDFExtractor(
        pdf_dir=str(DEFAULT_PDF_ROOT),
        use_ocr=False,
        max_workers=1,
        debug_mode=False,
        use_ai_extraction=use_ai,
    )
    from processes.pdf_extraction.extractors.ai_bank_extractor import AIBankExtractor

    dealer_helper = AIBankExtractor(debug_mode=False)

    for rec in records:
        pdf_path = Path(rec["file_path"]) if rec.get("file_path") else None
        if not pdf_path or not pdf_path.exists():
            stats["skipped"] += 1
            continue

        section_only = False
        try:
            from processes.pdf_extraction.core import ExtractionEngine

            engine = ExtractionEngine(use_ocr=False)
            text = engine.extract_text(str(pdf_path)) or ""
            section_only = len(text) > max_pdf_chars
        except Exception:
            text = ""

        try:
            extraction = extractor.process_single_pdf(
                str(pdf_path), section_only=section_only
            )
        except Exception as e:
            write_quarantine(
                quarantine_dir,
                {
                    "isin": rec.get("isin"),
                    "issuer": rec.get("issuer"),
                    "pdf_path": str(pdf_path),
                    "reject_reason": f"extract_error: {e}",
                },
            )
            stats["quarantine"] += 1
            continue

        if extraction.get("error"):
            write_quarantine(
                quarantine_dir,
                {
                    "isin": rec.get("isin"),
                    "issuer": rec.get("issuer"),
                    "pdf_path": str(pdf_path),
                    "reject_reason": extraction.get("error"),
                },
            )
            stats["quarantine"] += 1
            continue

        # Dealer-table regex does not need Ollama (same path AIBankExtractor uses first).
        if not extraction.get("extracted_banks") and text:
            dealer_banks = dealer_helper.extract_dealer_management_banks(text)
            if dealer_banks:
                extraction["extracted_banks"] = dealer_banks
                extraction["bank_sections"] = {"dealer_table": "regex"}
            elif not use_ai:
                bank_info = dealer_helper.extract(text, section_only=section_only)
                if bank_info.get("extracted_banks"):
                    extraction["extracted_banks"] = bank_info["extracted_banks"]

        deal, reason = content_gates(
            pdf_path=pdf_path,
            isin=rec.get("isin") or "",
            issuer=rec.get("issuer") or "",
            extraction=extraction,
            source_url=rec.get("source_url"),
            text_sample=text[:50000] if text else "",
            ste_mmboe=rec.get("ste_mmboe"),
            watchlist_rank=rec.get("rank"),
        )
        if reason or deal is None:
            write_quarantine(
                quarantine_dir,
                {
                    "isin": rec.get("isin"),
                    "issuer": rec.get("issuer"),
                    "pdf_path": str(pdf_path),
                    "reject_reason": reason or "unknown",
                    "benchmark": rec.get("benchmark"),
                },
            )
            stats["quarantine"] += 1
            logger.warning("Quarantine %s: %s", rec.get("isin"), reason)
            continue

        if append_deal(deals_path, deal):
            stats["published"] += 1
            logger.info("Published deal %s (%s)", deal.id, deal.isin)
        else:
            stats["skipped"] += 1
            logger.info("Deal already published: %s", deal.id)

    return stats


def records_from_seen(seen_path: Path, only_downloaded: bool = True) -> List[Dict[str, Any]]:
    seen = _load_seen(seen_path)
    out = []
    for rec in (seen.get("entries") or {}).values():
        if only_downloaded and rec.get("status") != "downloaded":
            continue
        if rec.get("file_path"):
            out.append(rec)
    return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="PaperTrails alert poll + auto-publish")
    parser.add_argument("--watchlist", type=Path, default=DEFAULT_WATCHLIST)
    parser.add_argument("--seen", type=Path, default=DEFAULT_SEEN)
    parser.add_argument("--pdf-root", type=Path, default=DEFAULT_PDF_ROOT)
    parser.add_argument("--deals", type=Path, default=DEFAULT_DEALS)
    parser.add_argument("--quarantine", type=Path, default=DEFAULT_QUARANTINE)
    parser.add_argument(
        "--phase0",
        action="store_true",
        help="Poll/download only (no extract/publish) — yield proof",
    )
    parser.add_argument(
        "--skip-scraping",
        action="store_true",
        help="Do not poll ESMA; extract from seen.json downloaded paths",
    )
    parser.add_argument("--max-issuers", type=int, default=None)
    parser.add_argument("--isin-limit", type=int, default=3)
    parser.add_argument("--no-ai", action="store_true", help="Regex banks only")
    parser.add_argument("--headed", action="store_true", help="Run Chrome headed")
    parser.add_argument(
        "--benchmarks-only",
        action="store_true",
        help="Poll only force-included L2 benchmark issuers",
    )
    parser.add_argument(
        "--skip-benchmarks",
        action="store_true",
        help="Poll STE-ranked issuers only (exclude OMV/AKER/Total force-includes)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not args.watchlist.exists():
        logger.error("Watchlist missing: %s — run py -3 -m papertrails.build_watchlist", args.watchlist)
        return 1

    watchlist = _load_watchlist(args.watchlist)
    headless = not args.headed and os.environ.get("HEADLESS", "true").lower() != "false"

    downloads: List[Dict[str, Any]] = []
    if not args.skip_scraping:
        downloads = poll_watchlist(
            watchlist,
            seen_path=args.seen,
            pdf_root=args.pdf_root,
            headless=headless,
            max_issuers=args.max_issuers,
            isin_limit_per_issuer=args.isin_limit,
            benchmarks_only=bool(args.benchmarks_only),
            skip_benchmarks=bool(args.skip_benchmarks),
        )
        logger.info("Phase0/poll downloads: %s", len(downloads))
        non_bench = [d for d in downloads if not d.get("benchmark")]
        logger.info("Non-benchmark downloads: %s", len(non_bench))
        if args.phase0:
            report = {
                "downloads": len(downloads),
                "non_benchmark_downloads": len(non_bench),
                "paths": [d.get("file_path") for d in downloads],
            }
            out = ROOT / "logs" / "alerts_phase0_report.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
            print(json.dumps(report, indent=2))
            return 0 if downloads else 2
    else:
        downloads = records_from_seen(args.seen)

    stats = extract_and_publish(
        downloads,
        deals_path=args.deals,
        quarantine_dir=args.quarantine,
        use_ai=not args.no_ai,
    )
    print(json.dumps({"poll_downloads": len(downloads), **stats}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
