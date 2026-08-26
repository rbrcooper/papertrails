"""Unit tests for PaperTrails watchlist + content gates (no ESMA)."""

from pathlib import Path

import pytest

from papertrails.build_watchlist import METRIC_COLUMN, build_watchlist
from papertrails.schema import content_gates, make_deal_id

ROOT = Path(__file__).resolve().parents[3]
GOGEL = ROOT / "data" / "raw" / "Urgewald GOGEL 2025 V1.2 with identifiers.csv"


@pytest.mark.skipif(not GOGEL.exists(), reason="GOGEL CSV not present")
def test_build_watchlist_top5_has_meta_and_isins():
    payload = build_watchlist(GOGEL, top=5, include_benchmarks=True)
    assert payload["meta"]["metric_column"] == METRIC_COLUMN
    assert payload["meta"]["eligible_parents_total"] > 0
    issuers = payload["issuers"]
    assert len(issuers) >= 5
    ranked = [i for i in issuers if i.get("rank") is not None]
    assert ranked[0]["ste_mmboe"] >= ranked[-1]["ste_mmboe"]
    assert all(i["bond_isins"] for i in issuers)
    benches = {i.get("benchmark") for i in issuers if i.get("benchmark")}
    assert "OMV" in benches and "AKER" in benches and "TotalEnergies" in benches


def test_content_gates_require_underwriters(tmp_path):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 minimal")
    deal, reason = content_gates(
        pdf_path=pdf,
        isin="XS1234567890",
        issuer="Test",
        extraction={"metadata": {}, "extracted_banks": []},
        text_sample="XS1234567890",
    )
    assert deal is None
    assert reason == "no_underwriters"


def test_content_gates_publish(tmp_path):
    pdf = tmp_path / "ok.pdf"
    pdf.write_bytes(b"%PDF-1.4 minimal")
    deal, reason = content_gates(
        pdf_path=pdf,
        isin="XS1234567890",
        issuer="Test Co",
        extraction={
            "metadata": {"issue_date": "2024-01-01", "currency": "EUR", "issue_size": 500},
            "extracted_banks": [
                {"raw_name": "Barclays Bank Ireland PLC", "role": "Dealer"},
            ],
        },
        text_sample="ISIN XS1234567890 Final Terms",
    )
    assert reason is None
    assert deal is not None
    assert deal.isin == "XS1234567890"
    assert deal.underwriters[0]["raw_name"].startswith("Barclays")
    assert make_deal_id("XS1234567890", None, str(pdf)) == deal.id
