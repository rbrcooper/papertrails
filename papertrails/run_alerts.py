"""
PaperTrails alert runner.

Hinge: tier1 yield on watchlist company LEIs + ESMA session stability for PDF bytes.
Discovery prefers Solr issuer_lei; Selenium UI search is fallback only.
Publish path is deterministic: dealer-table regex only — never Ollama.

Usage:
  py -3 -m papertrails.run_alerts --watchlist papertrails/watchlist.yaml
  py -3 -m papertrails.run_alerts --skip-scraping
  py -3 -m papertrails.run_alerts --only-issuer "Eni SpA" --headed
  py -3 -m papertrails.run_alerts --only-issuer "Repsol" --force --headed
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from papertrails.schema import (  # noqa: E402
    EXTRACTION_METHOD_DEALER_TABLE,
    append_deal,
    content_gates,
    load_deals,
    write_quarantine,
)
from processes.esma_scraper import (  # noqa: E402
    ESMAScraper,
    attach_solr_download_urls,
    resolve_download_url,
)
from processes.pipeline_components.validators import (  # noqa: E402
    _parse_doc_type_code,
    classify_doc_tier,
    select_esma_rows,
)
from processes.pdf_extraction.core import ExtractionEngine  # noqa: E402
from processes.pdf_extraction.extractors.ai_bank_extractor import (  # noqa: E402
    AIBankExtractor,
)
from processes.pdf_extraction.extractors.currency_extractor import (  # noqa: E402
    CurrencyExtractor,
)
from processes.pdf_extraction.extractors.date_extractor import DateExtractor  # noqa: E402

logger = logging.getLogger("papertrails.run_alerts")

DEFAULT_WATCHLIST = Path(__file__).resolve().parent / "watchlist.yaml"
DEFAULT_SEEN = ROOT / "data" / "alerts" / "seen.json"
DEFAULT_PDF_ROOT = ROOT / "data" / "alerts" / "pdfs"
DEFAULT_QUARANTINE = ROOT / "data" / "alerts" / "quarantine"
DEFAULT_DEALS = ROOT / "website" / "data" / "deals.json"
DEFAULT_YIELD_REPORT = ROOT / "logs" / "alerts_yield_report.json"

# When several FTWS exist, peek at most this many downloads for non-syndicated N/A.
NA_PEEK_CAP = 3
_NA_TOKEN = r"(?:n\s*/\s*a|n\s*\.\s*a\s*\.?|not\s+applicable)"
_SYNDICATED_NA_RE = re.compile(
    r"if\s+syndicated"
    r"(?:[,:\s]+names?\s+of\s+(?:the\s+)?managers?)?"
    r"[\s:,\-]*"
    r"(?:\([^)]{0,40}\))?"
    r"[\s:,]*"
    r"(?:specify[\s:,]*)?"
    r"(?:\(specify\))?"
    r"[\s:,]*"
    + _NA_TOKEN,
    re.IGNORECASE,
)


@dataclass
class SolrLeiResult:
    """Outcome of Solr-first FTWS download for one issuer."""

    downloads: List[Dict[str, Any]] = field(default_factory=list)
    nonsyndicated: List[Dict[str, Any]] = field(default_factory=list)
    solr_row_count: int = 0
    ftws_candidates: int = 0
    ftws_available: int = 0
    dropped_non_ftws: int = 0
    na_skipped: int = 0
    skipped_published: int = 0


def _empty_selection_stats() -> Dict[str, Any]:
    return {
        "policy": "ftws_only",
        "issuers_attempted": 0,
        "issuers_skipped_slot_full": 0,
        "solr_had_rows": 0,
        "solr_zero_rows": 0,
        "ui_fallback_calls": 0,
        "selected_ftws": 0,
        "new_ftws": 0,
        "dropped_non_ftws": 0,
        "na_skipped": 0,
        "non_syndicated": 0,
        "skipped_published": 0,
        "no_tier1_solr_no_ftws": 0,
        "no_tier1_solr_empty": 0,
        "force": False,
    }


def _published_isin_set(deals_path: Optional[Path]) -> set:
    if not deals_path:
        return set()
    return {
        (d.get("isin") or "").upper()
        for d in load_deals(deals_path)
        if d.get("isin")
    }


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


def _record_from_download(
    *,
    name: str,
    issuer: Dict[str, Any],
    d: Dict[str, Any],
) -> Dict[str, Any]:
    isin = (d.get("isin") or "").upper()
    fp = d.get("file_path")
    return {
        "issuer": name,
        "isin": isin,
        "file_path": fp,
        "doc_tier": d.get("doc_tier"),
        "doc_type_code": d.get("doc_type_code") or _row_doc_type_code(d) or None,
        "status": "downloaded",
        "benchmark": issuer.get("benchmark"),
        "ste_mmboe": issuer.get("ste_mmboe"),
        "rank": issuer.get("rank"),
        "source_url": resolve_download_url(d) or d.get("download_url") or d.get("url"),
        "doc_id": d.get("doc_id"),
    }


def _issuer_leis(issuer: Dict[str, Any]) -> List[str]:
    leis: List[str] = []
    for x in issuer.get("leis") or []:
        s = str(x).strip()
        if s and s not in leis:
            leis.append(s)
    lei = str(issuer.get("lei") or "").strip()
    if lei and lei not in leis:
        leis.insert(0, lei)
    return leis


def _row_doc_type_code(row: Dict[str, Any]) -> str:
    return _parse_doc_type_code(row.get("doc_type_code"), row.get("doc_type"))


def _is_ftws_row(row: Dict[str, Any]) -> bool:
    """True only for Final Terms (FTWS). STDA/SUPP never qualify."""
    code = _row_doc_type_code(row)
    if code == "FTWS":
        return True
    if code in {"STDA", "SUPP"}:
        return False
    descr = (row.get("doc_type") or "").lower()
    if "standalone" in descr:
        return False
    if re.search(r"\bsupplement\b", descr) and "pricing" not in descr:
        return False
    if any(k in descr for k in ("final term", "pricing supplement")):
        return True
    return False


def _is_nonsyndicated_na(text: str) -> bool:
    """True when the FTWS marks the syndicated-managers field as N/A."""
    if not text or not text.strip():
        return False
    return bool(_SYNDICATED_NA_RE.search(text))


def _peek_nonsyndicated_na(pdf_path: str) -> bool:
    """Cheap PDF peek: syndication line is N/A. Missing file → not N/A."""
    path = Path(pdf_path)
    if not path.exists():
        return False
    try:
        import fitz

        chunks: List[str] = []
        with fitz.open(str(path)) as doc:
            for i, page in enumerate(doc):
                if i >= 25:
                    break
                chunks.append(page.get_text() or "")
        return _is_nonsyndicated_na("\n".join(chunks))
    except Exception as e:
        logger.info("N/A peek failed for %s: %s", path, e)
        return False


def _count_issuer_alert_pdfs(
    name: str, entries: Dict[str, Any], pdf_root: Path
) -> int:
    """Count downloaded FTWS still on disk. STDA/SUPP do not fill the slot."""
    n = 0
    root = pdf_root.resolve()
    for rec in entries.values():
        if rec.get("issuer") != name or rec.get("status") != "downloaded":
            continue
        if not _is_ftws_row(rec):
            continue
        fp = rec.get("file_path")
        if not fp:
            continue
        p = Path(fp)
        try:
            p.resolve().relative_to(root)
        except ValueError:
            continue
        if p.exists():
            n += 1
    return n


def _download_record(row: Dict[str, Any], path: str) -> Dict[str, Any]:
    isin = (row.get("isin") or "").upper()
    code = row.get("doc_type_code") or _row_doc_type_code(row) or "FTWS"
    return {
        "file_path": path,
        "isin": isin,
        "doc_tier": row.get("doc_tier") or "tier1",
        "doc_type_code": code,
        "doc_id": row.get("doc_id"),
        "download_url": resolve_download_url(row),
        "url": resolve_download_url(row),
        "doc_type": row.get("doc_type"),
        "date": row.get("date"),
    }


def _download_via_solr_lei(
    scraper: ESMAScraper,
    company_name: str,
    leis: List[str],
    *,
    skip_isins: Optional[set] = None,
    published_isins: Optional[set] = None,
    max_docs: int = 1,
    peek_na: Optional[Callable[[str], bool]] = None,
    force: bool = False,
) -> SolrLeiResult:
    """Solr-first: one slot is downloadable FTWS only. Empty FTWS → no downloads.

    STDA/SUPP leftover is never concatenated. Newest FTWS first; non-syndicated
    N/A peeks try the next FTWS (cap NA_PEEK_CAP). If every peeked FTWS is N/A,
    downloads stay empty and newest N/A is returned in nonsyndicated (PDF kept,
    not extracted). Default incremental: skip known ISINs and do not backfill
    older FTWS unless force.
    """
    skip_isins = {s.upper() for s in (skip_isins or set()) if s}
    published_isins = {s.upper() for s in (published_isins or set()) if s}
    peek = peek_na or _peek_nonsyndicated_na
    scraper.current_company = company_name
    solr_rows: List[Dict[str, Any]] = []
    for lei in leis:
        rows = scraper.fetch_securities_via_solr(lei=lei, rows=50)
        nfound = int(rows[0].get("solr_num_found") or 0) if rows else 0
        if not rows:
            logger.info("Solr LEI %s → 0 prospectus rows for %s", lei, company_name)
        else:
            logger.info(
                "Solr sec_issuerNameList LEI %s numFound=%s rows=%s (%s)",
                lei,
                nfound,
                len(rows),
                company_name,
            )
        for r in rows:
            r["queried_lei"] = lei
            r["lei_match"] = 1.0
            r["score"] = max(float(r.get("score") or 0), 0.95)
            r["doc_tier"] = classify_doc_tier(r.get("doc_type_code"), r.get("doc_type"))
        solr_rows.extend(rows)
    if not solr_rows:
        return SolrLeiResult(solr_row_count=0)

    attach_solr_download_urls(solr_rows, solr_rows)
    selected = select_esma_rows(solr_rows, policy="strict", min_score=0.0)
    selected = [
        s
        for s in selected
        if s.get("doc_tier") == "tier1"
        and float(s.get("lei_match") or 0) > 0
        and resolve_download_url(s)
    ]
    ftws_all = [s for s in selected if _is_ftws_row(s)]
    rest = [s for s in selected if s not in ftws_all]
    dropped = len(rest)
    skipped_published = sum(
        1
        for s in ftws_all
        if (s.get("isin") or "").upper() in published_isins
    )
    known_dates = [
        s.get("date") or ""
        for s in ftws_all
        if (s.get("isin") or "").upper() in skip_isins
    ]
    cutoff = max(known_dates) if known_dates and not force else ""
    ftws = []
    for s in ftws_all:
        isin = (s.get("isin") or "").upper()
        if isin in skip_isins:
            continue
        if cutoff and (s.get("date") or "") <= cutoff:
            continue
        ftws.append(s)
    ftws.sort(key=lambda r: r.get("date") or "", reverse=True)
    logger.info(
        "FTWS-only %s: %s downloadable FTWS, dropped %s non-FTWS (STDA/SUPP leftover unused)",
        company_name,
        len(ftws),
        dropped,
    )
    if not ftws:
        return SolrLeiResult(
            downloads=[],
            solr_row_count=len(solr_rows),
            ftws_candidates=0,
            ftws_available=len(ftws_all),
            dropped_non_ftws=dropped,
            skipped_published=skipped_published,
        )

    max_keep = max(1, int(max_docs or 1))
    out: List[Dict[str, Any]] = []
    peeked: List[Dict[str, Any]] = []
    newest_na: Optional[Dict[str, Any]] = None
    na_skipped = 0
    in_run_skip = set(skip_isins)

    for row in ftws:
        if len(out) >= max_keep:
            break
        isin = (row.get("isin") or "").upper()
        if isin in in_run_skip:
            continue
        if len(peeked) >= NA_PEEK_CAP:
            break
        path = scraper.download_selected_row(row)
        if not path:
            continue
        rec = _download_record(row, path)
        peeked.append(rec)
        logger.info("Solr-first LEI downloaded %s → %s", isin, path)
        is_na = bool(peek(path))
        if is_na:
            in_run_skip.add(isin)
            if newest_na is None:
                newest_na = rec
            remaining = [
                r
                for r in ftws
                if (r.get("isin") or "").upper() not in in_run_skip
            ]
            if remaining and len(peeked) < NA_PEEK_CAP:
                na_skipped += 1
                logger.info(
                    "Non-syndicated N/A FTWS %s — try next (peeked %s/%s)",
                    isin,
                    len(peeked),
                    NA_PEEK_CAP,
                )
                continue
            # Last remaining, or cap reached: nonsyndicated below if nothing better.
            continue
        out.append(rec)

    nonsyndicated: List[Dict[str, Any]] = []
    if not out and newest_na:
        logger.info(
            "All peeked FTWS N/A for %s — newest N/A %s not for extract",
            company_name,
            newest_na.get("isin"),
        )
        nonsyndicated = [newest_na]

    return SolrLeiResult(
        downloads=out,
        nonsyndicated=nonsyndicated,
        solr_row_count=len(solr_rows),
        ftws_candidates=len(ftws),
        ftws_available=len(ftws_all),
        dropped_non_ftws=dropped,
        na_skipped=na_skipped,
        skipped_published=skipped_published,
    )


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
    only_issuer: Optional[str] = None,
    force: bool = False,
    selection_stats: Optional[Dict[str, Any]] = None,
    deals_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """LEI poll: Solr download first by issuer_lei. UI only if Solr returned 0 rows.

    Solr rows but no downloadable FTWS → no_tier1 (do not search_and_process).
    Known FTWS (seen downloaded or deals.json) are skipped; a strictly newer
    FTWS still downloads. --force ignores the newer-than cutoff; skip_isins still
    applies. UI fallback still keeps FTWS only.
    """
    seen = _load_seen(seen_path)
    entries: Dict[str, Any] = seen.setdefault("entries", {})
    published_isins = _published_isin_set(deals_path)
    issuers = list(watchlist.get("issuers") or [])
    stats = selection_stats if selection_stats is not None else _empty_selection_stats()
    stats["force"] = bool(force)
    if only_issuer:
        needle = only_issuer.strip().lower()
        issuers = [
            i
            for i in issuers
            if needle in (i.get("name_parent") or "").lower()
            or needle == (i.get("benchmark") or "").lower()
        ]
    if benchmarks_only:
        issuers = [i for i in issuers if i.get("benchmark")]
    elif skip_benchmarks:
        issuers = [i for i in issuers if not i.get("benchmark")]
    if max_issuers is not None:
        issuers = issuers[:max_issuers]

    pdf_root.mkdir(parents=True, exist_ok=True)
    scraper = ESMAScraper(download_dir=str(pdf_root), debug_mode=True, headless=headless)
    downloads_out: List[Dict[str, Any]] = []
    max_docs = max(1, int(isin_limit_per_issuer or 1))

    try:
        for issuer in issuers:
            name = issuer["name_parent"]
            leis = _issuer_leis(issuer)
            if not leis:
                logger.warning("Skip %s — no LEI on watchlist", name)
                entries[_seen_key("NOLEI", name)] = {
                    "issuer": name,
                    "status": "no_tier1",
                    "error": "no_lei",
                    "benchmark": issuer.get("benchmark"),
                    "ste_mmboe": issuer.get("ste_mmboe"),
                    "rank": issuer.get("rank"),
                }
                continue

            skip_isins = {
                (e.get("isin") or "").upper()
                for e in entries.values()
                if e.get("issuer") == name
                and e.get("status") == "downloaded"
                and e.get("isin")
            }
            skip_isins |= published_isins
            want = max_docs
            stats["issuers_attempted"] = stats.get("issuers_attempted", 0) + 1
            logger.info(
                "Polling %s (rank=%s benchmark=%s) LEIs=%s max_docs=%s force=%s",
                name,
                issuer.get("rank"),
                issuer.get("benchmark"),
                leis,
                want,
                force,
            )

            result = SolrLeiResult()
            try:
                result = _download_via_solr_lei(
                    scraper,
                    name,
                    leis,
                    skip_isins=skip_isins,
                    published_isins=published_isins,
                    max_docs=want,
                    force=force,
                )
            except Exception as e:
                logger.warning("Solr-first LEI failed for %s: %s", name, e)
                result = SolrLeiResult(solr_row_count=0)

            stats["dropped_non_ftws"] = stats.get("dropped_non_ftws", 0) + result.dropped_non_ftws
            stats["na_skipped"] = stats.get("na_skipped", 0) + result.na_skipped
            stats["skipped_published"] = (
                stats.get("skipped_published", 0) + result.skipped_published
            )
            if result.solr_row_count > 0:
                stats["solr_had_rows"] = stats.get("solr_had_rows", 0) + 1
            else:
                stats["solr_zero_rows"] = stats.get("solr_zero_rows", 0) + 1

            got = list(result.downloads)
            for d in got:
                rec = _record_from_download(name=name, issuer=issuer, d=d)
                key = _seen_key(d.get("isin") or "", Path(d["file_path"]).name)
                entries[key] = rec
                downloads_out.append(rec)
            for d in result.nonsyndicated:
                rec = _record_from_download(name=name, issuer=issuer, d=d)
                key = _seen_key(d.get("isin") or "", Path(d["file_path"]).name)
                entries[key] = rec
            if result.nonsyndicated:
                stats["non_syndicated"] = stats.get("non_syndicated", 0) + len(
                    result.nonsyndicated
                )
            if got:
                stats["selected_ftws"] = stats.get("selected_ftws", 0) + len(got)
                stats["new_ftws"] = stats.get("new_ftws", 0) + len(got)
                continue
            if result.nonsyndicated:
                logger.info(
                    "Skip %s — all peeked FTWS N/A (non_syndicated, not extract)",
                    name,
                )
                continue

            # Known FTWS already skipped — incremental idle, not no_tier1.
            if result.ftws_available > 0:
                logger.info(
                    "Skip %s — %s known FTWS, no newer unstored FTWS",
                    name,
                    result.ftws_available,
                )
                continue

            # Solr had prospectus rows but no downloadable FTWS: honest no_tier1.
            if result.solr_row_count > 0:
                entries[_seen_key("no_tier1", name)] = {
                    "issuer": name,
                    "status": "no_tier1",
                    "error": "solr_no_downloadable_ftws",
                    "benchmark": issuer.get("benchmark"),
                    "ste_mmboe": issuer.get("ste_mmboe"),
                    "rank": issuer.get("rank"),
                }
                stats["no_tier1_solr_no_ftws"] = stats.get("no_tier1_solr_no_ftws", 0) + 1
                logger.warning("no_tier1 for %s (Solr rows but no downloadable FTWS)", name)
                continue

            if _count_issuer_alert_pdfs(name, entries, pdf_root) > 0:
                logger.info("Skip UI fallback for %s — already have FTWS on disk", name)
                continue

            company_data = {
                "name": name,
                "lei": leis[0],
                "leis": leis,
                "isin_equity": issuer.get("isin_equity") or "",
            }
            stats["ui_fallback_calls"] = stats.get("ui_fallback_calls", 0) + 1
            try:
                downloads = scraper.search_and_process(
                    name,
                    company_data=company_data,
                    doc_policy="strict",
                    allow_fallback_search=False,
                )
            except Exception as e:
                logger.exception("UI scrape error for %s: %s", name, e)
                entries[_seen_key("error", name)] = {
                    "issuer": name,
                    "error": str(e),
                    "benchmark": issuer.get("benchmark"),
                }
                downloads = []

            ftws_ui = [
                d
                for d in downloads
                if _is_ftws_row(d)
                and (d.get("isin") or "").upper() not in skip_isins
            ]
            dropped_ui = len(downloads) - len(ftws_ui)
            if dropped_ui:
                stats["dropped_non_ftws"] = stats.get("dropped_non_ftws", 0) + dropped_ui
                logger.info(
                    "UI fallback %s: kept %s FTWS, dropped %s non-FTWS",
                    name,
                    len(ftws_ui),
                    dropped_ui,
                )
            if not ftws_ui:
                entries[_seen_key("no_tier1", name)] = {
                    "issuer": name,
                    "status": "no_tier1",
                    "error": "solr_empty_no_ftws",
                    "benchmark": issuer.get("benchmark"),
                    "ste_mmboe": issuer.get("ste_mmboe"),
                    "rank": issuer.get("rank"),
                }
                stats["no_tier1_solr_empty"] = stats.get("no_tier1_solr_empty", 0) + 1
                logger.warning("no_tier1 for %s (Solr 0 rows, UI had no FTWS)", name)
            for d in ftws_ui[:want]:
                isin = (d.get("isin") or "").upper()
                fp = d.get("file_path")
                key = _seen_key(isin, Path(fp).name if fp else "doc")
                rec = _record_from_download(name=name, issuer=issuer, d=d)
                entries[key] = rec
                downloads_out.append(rec)
                stats["selected_ftws"] = stats.get("selected_ftws", 0) + 1
                stats["new_ftws"] = stats.get("new_ftws", 0) + 1
                logger.info("UI-fallback downloaded FTWS %s → %s", isin, fp)
    finally:
        try:
            scraper.close()
        except Exception:
            pass
        _save_seen(seen_path, seen)

    return downloads_out


def _regex_metadata(text: str) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    try:
        dates = DateExtractor(debug_mode=False).extract(text)
        meta["issue_date"] = dates.get("issue_date")
        meta["maturity_date"] = dates.get("maturity_date")
    except Exception:
        pass
    try:
        cur = CurrencyExtractor(debug_mode=False).extract(text)
        meta["currency"] = cur.get("currency")
        meta["issue_size"] = cur.get("issue_size") or cur.get("amount")
        meta["programme_size"] = cur.get("programme_size")
    except Exception:
        pass
    return meta


def extract_and_publish(
    records: List[Dict[str, Any]],
    *,
    deals_path: Path,
    quarantine_dir: Path,
    max_pdf_chars: int = 80000,
) -> Dict[str, int]:
    """Deterministic extract: dealer-table regex only. Never calls Ollama."""
    stats = {
        "published": 0,
        "quarantine": 0,
        "skipped": 0,
        "non_syndicated": 0,
        "no_dealer_table": 0,
    }
    if not records:
        return stats

    engine = ExtractionEngine(use_ocr=False)
    dealer_helper = AIBankExtractor(debug_mode=False)

    for rec in records:
        pdf_path = Path(rec["file_path"]) if rec.get("file_path") else None
        if not pdf_path or not pdf_path.exists():
            stats["skipped"] += 1
            continue

        if _peek_nonsyndicated_na(str(pdf_path)):
            write_quarantine(
                quarantine_dir,
                {
                    "isin": rec.get("isin"),
                    "issuer": rec.get("issuer"),
                    "pdf_path": str(pdf_path),
                    "reject_reason": "non_syndicated",
                    "benchmark": rec.get("benchmark"),
                },
            )
            stats["quarantine"] += 1
            stats["non_syndicated"] += 1
            logger.warning("Quarantine %s: non_syndicated", rec.get("isin"))
            continue

        try:
            text = engine.extract_text(str(pdf_path)) or ""
        except Exception as e:
            write_quarantine(
                quarantine_dir,
                {
                    "isin": rec.get("isin"),
                    "issuer": rec.get("issuer"),
                    "pdf_path": str(pdf_path),
                    "reject_reason": f"text_extract_error: {e}",
                },
            )
            stats["quarantine"] += 1
            continue

        if len(text) > max_pdf_chars:
            # Still scan full text for dealer table; no LLM truncation path.
            pass

        dealer_banks = dealer_helper.extract_dealer_management_banks(text)
        if not dealer_banks:
            write_quarantine(
                quarantine_dir,
                {
                    "isin": rec.get("isin"),
                    "issuer": rec.get("issuer"),
                    "pdf_path": str(pdf_path),
                    "reject_reason": "no_dealer_table",
                    "benchmark": rec.get("benchmark"),
                },
            )
            stats["quarantine"] += 1
            stats["no_dealer_table"] += 1
            logger.warning("Quarantine %s: no_dealer_table", rec.get("isin"))
            continue

        extraction = {
            "metadata": _regex_metadata(text),
            "extracted_banks": dealer_banks,
            "extraction_method": EXTRACTION_METHOD_DEALER_TABLE,
            "doc_type_code": rec.get("doc_type_code"),
        }

        deal, reason = content_gates(
            pdf_path=pdf_path,
            isin=rec.get("isin") or "",
            issuer=rec.get("issuer") or "",
            extraction=extraction,
            source_url=rec.get("source_url"),
            doc_id=rec.get("doc_id"),
            text_sample=text[:50000] if text else "",
            ste_mmboe=rec.get("ste_mmboe"),
            watchlist_rank=rec.get("rank"),
            require_dealer_table=True,
        )
        if reason or deal is None:
            reject = reason or "unknown"
            write_quarantine(
                quarantine_dir,
                {
                    "isin": rec.get("isin"),
                    "issuer": rec.get("issuer"),
                    "pdf_path": str(pdf_path),
                    "reject_reason": reject,
                    "benchmark": rec.get("benchmark"),
                },
            )
            stats["quarantine"] += 1
            if reject == "non_syndicated":
                stats["non_syndicated"] += 1
            elif reject == "no_dealer_table":
                stats["no_dealer_table"] += 1
            logger.warning("Quarantine %s: %s", rec.get("isin"), reason)
            continue

        if append_deal(deals_path, deal):
            stats["published"] += 1
            logger.info(
                "Published/upserted deal %s (%s) n_underwriters=%s method=%s",
                deal.id,
                deal.isin,
                deal.n_underwriters,
                deal.extraction_method,
            )
        else:
            stats["skipped"] += 1
            logger.info("Deal not written: %s", deal.id)

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


def _quarantine_breakdown(quarantine_dir: Path) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    if not quarantine_dir.exists():
        return counts
    for path in quarantine_dir.glob("*.json"):
        try:
            with path.open(encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        reason = str(payload.get("reject_reason") or "unknown")
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def _issuer_rows_from_seen(
    seen_path: Path,
    *,
    deals_path: Path,
    quarantine_dir: Path,
    pdf_root: Path,
    watchlist: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """One row per watchlist issuer (or seen issuer) with best-known outcome."""
    seen = _load_seen(seen_path)
    entries = list((seen.get("entries") or {}).values())
    published_by_isin = {
        (d.get("isin") or "").upper(): d for d in load_deals(deals_path)
    }
    quarantine_by_isin: Dict[str, str] = {}
    if quarantine_dir.exists():
        for path in quarantine_dir.glob("*.json"):
            try:
                with path.open(encoding="utf-8") as f:
                    payload = json.load(f)
                isin = (payload.get("isin") or "").upper()
                if isin:
                    quarantine_by_isin[isin] = str(
                        payload.get("reject_reason") or "unknown"
                    )
            except (OSError, json.JSONDecodeError):
                continue

    # Build issuer specs: display name + how to match seen entries
    specs: List[Dict[str, Any]] = []
    seen_names = sorted({e.get("issuer") for e in entries if e.get("issuer")})
    if watchlist:
        for i in watchlist.get("issuers") or []:
            name = i.get("name_parent") or ""
            if not name:
                continue
            specs.append(
                {
                    "display": name,
                    "match_names": {name},
                    "match_benchmarks": {i.get("benchmark")} if i.get("benchmark") else set(),
                }
            )
    for name in seen_names:
        if not any(name in s["match_names"] for s in specs):
            specs.append({"display": name, "match_names": {name}, "match_benchmarks": set()})

    rows: List[Dict[str, Any]] = []
    for spec in specs:
        name = spec["display"]
        matched = [
            e
            for e in entries
            if e.get("issuer") in spec["match_names"]
            or (e.get("benchmark") and e.get("benchmark") in spec["match_benchmarks"])
        ]
        outcome = "unknown"
        isin = None
        pdf_path = None
        reject_reason = None

        # Prefer published ISINs linked to this issuer via deal record
        for deal in published_by_isin.values():
            deal_issuer = deal.get("issuer") or ""
            if deal_issuer in spec["match_names"] or (
                deal.get("isin") or ""
            ).upper() in {
                (e.get("isin") or "").upper()
                for e in matched
                if e.get("isin")
            }:
                if deal_issuer in spec["match_names"] or any(
                    (e.get("isin") or "").upper() == (deal.get("isin") or "").upper()
                    for e in matched
                ):
                    outcome = "published"
                    isin = (deal.get("isin") or "").upper()
                    pdf_path = deal.get("pdf_path")
                    break

        if outcome != "published":
            for e in matched:
                if e.get("status") == "downloaded" and e.get("isin"):
                    cand = (e.get("isin") or "").upper()
                    pdf_path = e.get("file_path")
                    isin = cand
                    if cand in published_by_isin:
                        outcome = "published"
                        break
                    if cand in quarantine_by_isin:
                        outcome = "quarantine"
                        reject_reason = quarantine_by_isin[cand]
                        break
                    fp = Path(pdf_path) if pdf_path else None
                    if fp and fp.exists():
                        outcome = "downloaded"
                        break

        if outcome not in ("published", "quarantine", "downloaded"):
            if any(e.get("status") == "no_tier1" for e in matched):
                outcome = "no_tier1"
                no_t = next(e for e in matched if e.get("status") == "no_tier1")
                isin = (no_t.get("isin") or isin or "").upper() or None
            elif any(e.get("error") for e in matched):
                outcome = "download_failed"
                err = next(e for e in matched if e.get("error"))
                isin = (err.get("isin") or isin or "").upper() or None
                reject_reason = err.get("error")
            elif not matched:
                outcome = "not_polled"

        rows.append(
            {
                "issuer": name,
                "isin": isin,
                "outcome": outcome,
                "reject_reason": reject_reason,
                "pdf_path": pdf_path,
                "benchmark": next(
                    (e.get("benchmark") for e in matched if e.get("benchmark")),
                    None,
                ),
                "rank": next(
                    (e.get("rank") for e in matched if e.get("rank") is not None),
                    None,
                ),
            }
        )
    return rows


def _count_seen_statuses(seen_path: Path) -> Dict[str, int]:
    counts: Dict[str, int] = {
        "downloaded": 0,
        "no_tier1": 0,
        "download_failed": 0,
    }
    for rec in (_load_seen(seen_path).get("entries") or {}).values():
        status = rec.get("status")
        if status == "downloaded":
            counts["downloaded"] += 1
        elif status == "no_tier1":
            counts["no_tier1"] += 1
        elif rec.get("error"):
            counts["download_failed"] += 1
    return counts


def write_yield_report(
    *,
    out_path: Path,
    seen_path: Path,
    deals_path: Path,
    quarantine_dir: Path,
    pdf_root: Path,
    extract_stats: Dict[str, int],
    poll_downloads: int,
    watchlist: Optional[Dict[str, Any]] = None,
    skip_scraping: bool = False,
    selection_stats: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    seen_counts = _count_seen_statuses(seen_path)
    quarantine_by_reason = _quarantine_breakdown(quarantine_dir)
    issuer_rows = _issuer_rows_from_seen(
        seen_path,
        deals_path=deals_path,
        quarantine_dir=quarantine_dir,
        pdf_root=pdf_root,
        watchlist=watchlist,
    )
    outcome_counts: Dict[str, int] = {}
    for row in issuer_rows:
        o = row.get("outcome") or "unknown"
        outcome_counts[o] = outcome_counts.get(o, 0) + 1
    non_syndicated_issuers = sum(
        1 for row in issuer_rows if row.get("reject_reason") == "non_syndicated"
    )
    no_dealer_table_issuers = sum(
        1 for row in issuer_rows if row.get("reject_reason") == "no_dealer_table"
    )

    report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "skip_scraping": skip_scraping,
        "poll_downloads_this_run": poll_downloads,
        "extract_this_run": dict(extract_stats),
        "incremental": {
            "new_ftws": (selection_stats or {}).get("new_ftws", 0),
            "skipped_published": (selection_stats or {}).get("skipped_published", 0),
            "na_skipped": (selection_stats or {}).get("na_skipped", 0),
            "non_syndicated": (selection_stats or {}).get("non_syndicated", 0),
        },
        "totals": {
            "published": outcome_counts.get("published", 0),
            "quarantine": outcome_counts.get("quarantine", 0),
            "non_syndicated": non_syndicated_issuers,
            "no_dealer_table": no_dealer_table_issuers,
            "downloaded_unpublished": outcome_counts.get("downloaded", 0),
            "no_tier1": outcome_counts.get("no_tier1", 0),
            "download_failed": outcome_counts.get("download_failed", 0),
            "not_polled": outcome_counts.get("not_polled", 0),
            "seen_downloaded": seen_counts["downloaded"],
            "seen_no_tier1": seen_counts["no_tier1"],
            "seen_download_failed": seen_counts["download_failed"],
        },
        "quarantine_by_reason": quarantine_by_reason,
        "selection": selection_stats or _empty_selection_stats(),
        "issuers": issuer_rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return report


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
        help="Poll/download only (no extract/publish)",
    )
    parser.add_argument(
        "--skip-scraping",
        action="store_true",
        help="Do not poll ESMA; extract from seen.json downloaded paths",
    )
    parser.add_argument("--max-issuers", type=int, default=None)
    parser.add_argument(
        "--isin-limit",
        type=int,
        default=1,
        help="Max documents to download per issuer (LEI poll; not a GOGEL ISIN query cap)",
    )
    parser.add_argument(
        "--only-issuer",
        type=str,
        default=None,
        help="Poll only issuers whose name_parent/benchmark contains this string",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Ignore the newer-than cutoff so an older unstored FTWS can fill "
            "(intended with --only-issuer). skip_isins still applies "
            "(seen downloaded + deals.json published); does not delete PDFs or "
            "seen.json keys. To retry a stored FTWS without --force, delete that "
            "ISIN|filename entry in data/alerts/seen.json."
        ),
    )
    parser.add_argument("--headed", action="store_true", help="Run Chrome headed")
    parser.add_argument("--benchmarks-only", action="store_true")
    parser.add_argument("--skip-benchmarks", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not args.watchlist.exists():
        logger.error(
            "Watchlist missing: %s — run py -3 -m papertrails.build_watchlist",
            args.watchlist,
        )
        return 1

    watchlist = _load_watchlist(args.watchlist)
    headless = not args.headed and os.environ.get("HEADLESS", "true").lower() != "false"

    downloads: List[Dict[str, Any]] = []
    selection_stats = _empty_selection_stats()
    selection_stats["force"] = bool(args.force)
    if args.force and not args.only_issuer:
        logger.warning(
            "--force without --only-issuer will ignore the newer-than cutoff for every issuer"
        )
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
            only_issuer=args.only_issuer,
            force=bool(args.force),
            selection_stats=selection_stats,
            deals_path=args.deals,
        )
        logger.info("Poll downloads: %s", len(downloads))
        logger.info(
            "Incremental: new_ftws=%s skipped_published=%s na_skipped=%s non_syndicated=%s",
            selection_stats.get("new_ftws"),
            selection_stats.get("skipped_published"),
            selection_stats.get("na_skipped"),
            selection_stats.get("non_syndicated"),
        )
        logger.info(
            "Selection FTWS-only: selected=%s dropped_non_ftws=%s ui_fallback=%s no_tier1_solr_no_ftws=%s",
            selection_stats.get("selected_ftws"),
            selection_stats.get("dropped_non_ftws"),
            selection_stats.get("ui_fallback_calls"),
            selection_stats.get("no_tier1_solr_no_ftws"),
        )
        non_bench = [d for d in downloads if not d.get("benchmark")]
        logger.info("Non-benchmark downloads: %s", len(non_bench))
        if args.phase0:
            report = {
                "downloads": len(downloads),
                "non_benchmark_downloads": len(non_bench),
                "selection": selection_stats,
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
    )
    report = write_yield_report(
        out_path=DEFAULT_YIELD_REPORT,
        seen_path=args.seen,
        deals_path=args.deals,
        quarantine_dir=args.quarantine,
        pdf_root=args.pdf_root,
        extract_stats=stats,
        poll_downloads=len(downloads),
        watchlist=watchlist,
        skip_scraping=bool(args.skip_scraping),
        selection_stats=selection_stats,
    )
    print(json.dumps({"poll_downloads": len(downloads), **stats, "yield_report": str(DEFAULT_YIELD_REPORT)}, indent=2))
    logger.info(
        "Yield report: published=%s quarantine=%s non_syndicated=%s no_dealer_table=%s no_tier1=%s → %s",
        report["totals"].get("published"),
        report["totals"].get("quarantine"),
        report["totals"].get("non_syndicated"),
        report["totals"].get("no_dealer_table"),
        report["totals"].get("no_tier1"),
        DEFAULT_YIELD_REPORT,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
