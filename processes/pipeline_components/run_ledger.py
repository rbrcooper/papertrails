import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class CompanyRunRecord:
    company: str
    run_timestamp: str
    region_filter: str
    doc_policy: str
    skip_scraping: bool
    bond_isin_count: int = 0
    tier1_downloaded: int = 0
    pdfs_processed: int = 0
    pdfs_stored: int = 0
    outcome: str = "unknown"
    skip_reason: str = ""
    duration_seconds: float = 0.0


class RunLedger:
    """
    Minimal per-company run ledger.

    - Append-only JSONL for auditability: logs/run_ledger.jsonl
    - Latest-status map for fast lookups: data/processed/company_run_status.json
    """

    def __init__(
        self,
        ledger_path: Path = Path("logs/run_ledger.jsonl"),
        status_path: Path = Path("data/processed/company_run_status.json"),
    ):
        self.ledger_path = ledger_path
        self.status_path = status_path
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.status_path.parent.mkdir(parents=True, exist_ok=True)
        self._status_cache: Optional[Dict[str, Any]] = None

    def load_status(self) -> Dict[str, Any]:
        if self._status_cache is not None:
            return self._status_cache
        if not self.status_path.exists():
            self._status_cache = {}
            return self._status_cache
        try:
            self._status_cache = json.loads(self.status_path.read_text(encoding="utf-8"))
        except Exception:
            self._status_cache = {}
        return self._status_cache

    def update_status(self, record: CompanyRunRecord) -> None:
        status = self.load_status()
        status[record.company] = {
            "run_timestamp": record.run_timestamp,
            "outcome": record.outcome,
            "skip_reason": record.skip_reason,
            "tier1_downloaded": record.tier1_downloaded,
            "pdfs_processed": record.pdfs_processed,
            "pdfs_stored": record.pdfs_stored,
            "duration_seconds": record.duration_seconds,
        }
        self.status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")

    def append(self, record: CompanyRunRecord) -> None:
        payload = asdict(record)
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.update_status(record)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def derive_outcome(
    *,
    pdfs_stored: int,
    tier1_downloaded: int,
    skip_scraping: bool,
    download_dir_exists: bool,
) -> tuple[str, str]:
    """Return (outcome, skip_reason) for a company run."""
    if pdfs_stored > 0:
        return "complete", ""
    if skip_scraping:
        if not download_dir_exists:
            return "no_pdfs", "no_pdfs_or_no_db_stores"
        return "extract_only_failed", "no_pdfs_or_no_db_stores"
    if tier1_downloaded == 0:
        return "no_tier1", "no_db_stores"
    return "extract_only_failed", "no_db_stores"

