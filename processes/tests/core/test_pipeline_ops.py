"""Tests for pipeline ops: run ledger outcomes and company queue helpers."""
import json
import tempfile
from pathlib import Path

import pytest

from processes.pipeline_components.run_ledger import (
    CompanyRunRecord,
    RunLedger,
    derive_outcome,
    now_iso,
)


class TestDeriveOutcome:
    def test_complete_when_stored(self):
        outcome, reason = derive_outcome(
            pdfs_stored=1,
            tier1_downloaded=0,
            skip_scraping=True,
            download_dir_exists=False,
        )
        assert outcome == "complete"
        assert reason == ""

    def test_no_pdfs_skip_scrape(self):
        outcome, _ = derive_outcome(
            pdfs_stored=0,
            tier1_downloaded=0,
            skip_scraping=True,
            download_dir_exists=False,
        )
        assert outcome == "no_pdfs"

    def test_no_tier1_when_scrape_empty(self):
        outcome, _ = derive_outcome(
            pdfs_stored=0,
            tier1_downloaded=0,
            skip_scraping=False,
            download_dir_exists=True,
        )
        assert outcome == "no_tier1"

    def test_extract_failed_with_pdfs_present(self):
        outcome, _ = derive_outcome(
            pdfs_stored=0,
            tier1_downloaded=2,
            skip_scraping=False,
            download_dir_exists=True,
        )
        assert outcome == "extract_only_failed"


class TestRunLedger:
    def test_status_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = RunLedger(
                ledger_path=Path(tmp) / "ledger.jsonl",
                status_path=Path(tmp) / "status.json",
            )
            rec = CompanyRunRecord(
                company="TestCo",
                run_timestamp=now_iso(),
                region_filter="eu",
                doc_policy="strict",
                skip_scraping=True,
                outcome="no_pdfs",
                skip_reason="test",
            )
            ledger.append(rec)
            status = ledger.load_status()
            assert status["TestCo"]["outcome"] == "no_pdfs"
            lines = (Path(tmp) / "ledger.jsonl").read_text(encoding="utf-8").strip().splitlines()
            assert len(lines) == 1
            assert json.loads(lines[0])["company"] == "TestCo"
