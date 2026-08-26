"""
Deal schema and auto-publish content gates for PaperTrails alerts.

No human approve step: pass gates → published; fail → quarantine.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from processes.pipeline_components.validators import filter_underwriter_banks


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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
    underwriters: List[Dict[str, str]]
    source_url: Optional[str]
    pdf_path: str
    extracted_at: str
    published_at: str
    gate_status: str = "published"
    reject_reason: Optional[str] = None
    doc_id: Optional[str] = None
    ste_mmboe: Optional[float] = None
    watchlist_rank: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d.get("reject_reason") is None:
            d.pop("reject_reason", None)
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
) -> Tuple[Optional[Deal], Optional[str]]:
    """Return (Deal, None) on pass or (None, reject_reason) on fail."""
    if not pdf_path.exists():
        return None, "pdf_missing"
    if not pdf_looks_valid(pdf_path):
        return None, "not_pdf"

    if text_sample and not isin_in_text(text_sample, isin):
        # Soft: metadata may still have ISIN; check extraction metadata later
        pass

    meta = extraction.get("metadata") or {}
    banks_raw = extraction.get("extracted_banks") or []
    underwriters = filter_underwriter_banks(banks_raw)
    if not underwriters:
        underwriters = [b for b in banks_raw if isinstance(b, dict) and b.get("raw_name")]
    if not underwriters:
        return None, "no_underwriters"

    # Prefer explicit ISIN match in text when available
    extracted_isin = (meta.get("isin") or isin or "").strip().upper()
    if text_sample and isin and not isin_in_text(text_sample, isin):
        if extracted_isin != isin.upper():
            return None, "isin_not_in_text"

    uw = [
        {"raw_name": str(b.get("raw_name") or "").strip(), "role": str(b.get("role") or "Unknown")}
        for b in underwriters
        if str(b.get("raw_name") or "").strip()
    ]
    if not uw:
        return None, "no_underwriters"

    now = _utc_now()
    deal = Deal(
        id=make_deal_id(isin, doc_id, str(pdf_path)),
        issuer=issuer,
        isin=isin.upper(),
        issue_date=meta.get("issue_date"),
        currency=meta.get("currency"),
        amount=meta.get("issue_size") or meta.get("amount"),
        underwriters=uw,
        source_url=source_url,
        pdf_path=str(pdf_path).replace("\\", "/"),
        extracted_at=now,
        published_at=now,
        gate_status="published",
        doc_id=str(doc_id) if doc_id else None,
        ste_mmboe=ste_mmboe,
        watchlist_rank=watchlist_rank,
    )
    return deal, None


def load_deals(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("deals") or []


def save_deals(path: Path, deals: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Newest first
    deals_sorted = sorted(
        deals,
        key=lambda d: d.get("published_at") or d.get("issue_date") or "",
        reverse=True,
    )
    with path.open("w", encoding="utf-8") as f:
        json.dump({"updated_at": _utc_now(), "deals": deals_sorted}, f, indent=2)


def append_deal(path: Path, deal: Deal) -> bool:
    """Append if id (or same ISIN) not already present. Returns True if newly added."""
    deals = load_deals(path)
    if any(d.get("id") == deal.id for d in deals):
        return False
    if any((d.get("isin") or "").upper() == deal.isin.upper() for d in deals):
        return False
    deals.append(deal.to_dict())
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
    with out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return out
