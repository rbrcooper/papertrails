"""
Deal schema and auto-publish content gates for PaperTrails alerts.

No human approve step: pass gates → published; fail → quarantine.
Phase 2: banks must come from dealer_table_regex only (deterministic).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from processes.pipeline_components.validators import (
    compute_allocated_amount,
    filter_underwriter_banks,
)

logger = logging.getLogger("papertrails.schema")

EXTRACTION_METHOD_DEALER_TABLE = "dealer_table_regex"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _atomic_write_json(path: Path, data: Any, indent: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        delete=False,
        suffix=".tmp",
    )
    try:
        json.dump(data, temp_file, indent=indent)
        temp_file.flush()
        os.fsync(temp_file.fileno())
        temp_file.close()
        os.replace(temp_file.name, str(path))
    except Exception:
        if os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass
        raise


@dataclass
class Underwriter:
    raw_name: str
    role: str = "Unknown"


@dataclass
class Deal:
    id: str
    issuer: str
    isin: str
    issue_date: Optional[str]
    currency: Optional[str]
    amount: Optional[Any]
    underwriters: List[Dict[str, Any]]
    source_url: Optional[str]
    pdf_path: str
    extracted_at: str
    published_at: str
    gate_status: str = "published"
    reject_reason: Optional[str] = None
    doc_id: Optional[str] = None
    ste_mmboe: Optional[float] = None
    watchlist_rank: Optional[int] = None
    extraction_method: Optional[str] = None
    n_underwriters: Optional[int] = None
    doc_type_code: Optional[str] = None
    amount_kind: Optional[str] = None
    programme_size: Optional[Any] = None
    allocated_amount: Optional[Any] = None
    maturity_date: Optional[str] = None
    coupon_rate: Optional[Any] = None
    coupon_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Public payload: never include local filesystem paths."""
        d = asdict(self)
        if d.get("reject_reason") is None:
            d.pop("reject_reason", None)
        d.pop("pdf_path", None)
        return d


def make_deal_id(isin: str, doc_id: Optional[str], pdf_path: str) -> str:
    base = f"{isin}|{doc_id or ''}|{Path(pdf_path).name}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def pdf_looks_valid(pdf_path: Path) -> bool:
    try:
        with pdf_path.open("rb") as f:
            head = f.read(5)
        return head == b"%PDF-"
    except OSError:
        return False


def isin_in_text(text: str, isin: str) -> bool:
    if not text or not isin:
        return False
    return isin.upper() in text.upper()


def _meta_size(val: Any) -> Any:
    if val is None or val == "":
        return None
    return val


def classify_deal_amount(meta: Dict[str, Any]) -> Tuple[Optional[Any], str, Optional[Any]]:
    """amount is the issued tranche only; programme ceiling is never returned as amount."""
    issue = _meta_size(meta.get("issue_size"))
    programme = _meta_size(meta.get("programme_size"))
    if issue is not None:
        return issue, "tranche", programme
    if programme is not None:
        return None, "programme", programme
    fallback = _meta_size(meta.get("amount"))
    if fallback is not None:
        return fallback, "unknown", None
    return None, "unknown", None


def content_gates(
    *,
    pdf_path: Path,
    isin: str,
    issuer: str,
    extraction: Dict[str, Any],
    source_url: Optional[str] = None,
    doc_id: Optional[str] = None,
    text_sample: str = "",
    ste_mmboe: Optional[float] = None,
    watchlist_rank: Optional[int] = None,
    require_dealer_table: bool = True,
) -> Tuple[Optional[Deal], Optional[str]]:
    """Return (Deal, None) on pass or (None, reject_reason) on fail."""
    isin_clean = (isin or "").strip().upper()
    if not isin_clean or len(isin_clean) < 12:
        return None, "missing_isin"

    if not pdf_path.exists():
        return None, "pdf_missing"
    if not pdf_looks_valid(pdf_path):
        return None, "not_pdf"

    method = (extraction.get("extraction_method") or "").strip()
    if require_dealer_table and method != EXTRACTION_METHOD_DEALER_TABLE:
        return None, "no_dealer_table"

    meta = extraction.get("metadata") or {}
    banks_raw = extraction.get("extracted_banks") or []
    underwriters = filter_underwriter_banks(banks_raw)
    if not underwriters:
        return None, "no_dealer_table" if require_dealer_table else "no_underwriters"

    extracted_isin = (meta.get("isin") or isin_clean).strip().upper()
    if text_sample and not isin_in_text(text_sample, isin_clean):
        if extracted_isin != isin_clean:
            return None, "isin_not_in_text"

    uw = [
        {
            "raw_name": str(b.get("raw_name") or "").strip(),
            "role": str(b.get("role") or "Unknown"),
        }
        for b in underwriters
        if str(b.get("raw_name") or "").strip()
    ]
    if not uw:
        return None, "no_dealer_table" if require_dealer_table else "no_underwriters"

    amount, amount_kind, programme_size = classify_deal_amount(meta)
    allocated = None
    if amount_kind == "tranche" and amount is not None:
        allocated, _n = compute_allocated_amount(amount, uw)
    for row in uw:
        row["allocated_amount"] = allocated

    now = _utc_now()
    deal = Deal(
        id=make_deal_id(isin_clean, doc_id, str(pdf_path)),
        issuer=issuer,
        isin=isin_clean,
        issue_date=meta.get("issue_date"),
        currency=meta.get("currency"),
        amount=amount,
        underwriters=uw,
        source_url=source_url,
        pdf_path=str(pdf_path).replace("\\", "/"),
        extracted_at=now,
        published_at=now,
        gate_status="published",
        doc_id=str(doc_id) if doc_id else None,
        ste_mmboe=ste_mmboe,
        watchlist_rank=watchlist_rank,
        extraction_method=method or EXTRACTION_METHOD_DEALER_TABLE,
        n_underwriters=len(uw),
        doc_type_code=extraction.get("doc_type_code") or meta.get("doc_type_code"),
        amount_kind=amount_kind,
        programme_size=programme_size,
        allocated_amount=allocated,
        maturity_date=meta.get("maturity_date"),
        coupon_rate=meta.get("coupon_rate"),
        coupon_type=meta.get("coupon_type"),
    )
    return deal, None


def load_deals(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to load deals from %s: %s", path, e)
        return []
    if isinstance(data, list):
        return data
    return data.get("deals") or []


def _public_deal_record(deal: Dict[str, Any]) -> Dict[str, Any]:
    row = dict(deal)
    row.pop("pdf_path", None)
    return row


def save_deals(path: Path, deals: List[Dict[str, Any]]) -> None:
    public = [_public_deal_record(d) for d in deals]
    deals_sorted = sorted(
        public,
        key=lambda d: d.get("published_at") or d.get("issue_date") or "",
        reverse=True,
    )
    _atomic_write_json(path, {"updated_at": _utc_now(), "deals": deals_sorted})


def append_deal(path: Path, deal: Deal) -> bool:
    """Append or upsert by ISIN. Keeps first published_at on replace. Returns True if written."""
    deals = load_deals(path)
    new_d = _public_deal_record(deal.to_dict())
    isin_u = deal.isin.upper()
    for i, existing in enumerate(deals):
        same_id = existing.get("id") == deal.id
        same_isin = (existing.get("isin") or "").upper() == isin_u
        if same_id or same_isin:
            kept_published = existing.get("published_at") or new_d.get("published_at")
            new_d["published_at"] = kept_published
            deals[i] = new_d
            save_deals(path, deals)
            return True
    deals.append(new_d)
    save_deals(path, deals)
    return True


def write_quarantine(quarantine_dir: Path, payload: Dict[str, Any]) -> Path:
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    qid = payload.get("id") or make_deal_id(
        payload.get("isin") or "NA",
        payload.get("doc_id"),
        payload.get("pdf_path") or "unknown",
    )
    out = quarantine_dir / f"{qid}.json"
    payload = dict(payload)
    payload["gate_status"] = "quarantine"
    payload["quarantined_at"] = _utc_now()
    _atomic_write_json(out, payload)
    return out
