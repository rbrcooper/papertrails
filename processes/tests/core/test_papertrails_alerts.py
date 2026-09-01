"""Unit tests for PaperTrails watchlist + content gates + dealer-table extract."""

from pathlib import Path
import json
from unittest.mock import MagicMock, patch

import pytest

from papertrails.build_watchlist import (
    METRIC_COLUMN,
    _is_downloadable_ftws_doc,
    _parse_eu_number,
    build_watchlist,
    solr_lei_has_downloadable_ftws,
)
from papertrails.run_alerts import (
    SolrLeiResult,
    _count_issuer_alert_pdfs,
    _download_via_solr_lei,
    _is_nonsyndicated_na,
    extract_and_publish,
    poll_watchlist,
    write_yield_report,
)
from papertrails.schema import (
    EXTRACTION_METHOD_DEALER_TABLE,
    append_deal,
    content_gates,
    make_deal_id,
)
from processes.pdf_extraction.core import ExtractionEngine
from processes.pdf_extraction.extractors.ai_bank_extractor import AIBankExtractor
from processes.pipeline_components.validators import classify_doc_tier

ROOT = Path(__file__).resolve().parents[3]
GOGEL = ROOT / "data" / "raw" / "Urgewald GOGEL 2025 V1.2 with identifiers.csv"

OMV_PDF = (
    ROOT
    / "data/downloads/_audit_l2/OMV/Final_terms_including_the_summ_20240905_2f76b574.pdf"
)
TOTAL_PDF = (
    ROOT
    / "data/alerts/pdfs/TotalEnergies SE/Final_terms_including_the_summ_19112024_47bb733a.pdf"
)
ESB_PDF = (
    ROOT
    / "data/alerts/pdfs/Electricity Supply Board (ESB)/Final_terms_including_the_summ_02102023_72e548c2.pdf"
)
AKER_PDF = (
    ROOT
    / "data/alerts/pdfs/Aker BP ASA/Final_terms_including_the_summ_28052024_ee2fb289.pdf"
)
ENAGAS_PDF = (
    ROOT
    / "data/alerts/pdfs/Enagas SA/Final_terms_including_the_summ_20240124_6c320b01.pdf"
)

OMV_DEALER_NAMES = {
    "Barclays Bank Ireland PLC",
    "Erste Group Bank AG",
    "Mizuho Securities Europe GmbH",
    "Raiffeisen Bank International AG",
    "UniCredit Bank GmbH",
    "Société Générale",
}
TOTAL_DEALER_NAMES = {
    "Goldman Sachs Bank Europe SE",
    "Barclays Bank Ireland PLC",
    "BofA Securities Europe SA",
    "HSBC Continental Europe",
    "SMBC Bank EU AG",
    "Natixis",
}
ESB_DEALER_NAMES = {
    "Barclays Bank Ireland PLC",
    "HSBC Continental Europe",
    "Société Générale",
}

DEALER_TABLE_PDFS = [
    pytest.param(OMV_PDF, "OMV", OMV_DEALER_NAMES, id="omv"),
    pytest.param(TOTAL_PDF, "TotalEnergies", TOTAL_DEALER_NAMES, id="total"),
    pytest.param(ESB_PDF, "ESB", ESB_DEALER_NAMES, id="esb"),
]


def test_parse_european_ste_decimal():
    assert _parse_eu_number("438,11") == 438.11
    assert _parse_eu_number("4857,49") == 4857.49
    assert _parse_eu_number("0") == 0.0


@pytest.mark.skipif(not GOGEL.exists(), reason="GOGEL CSV not present")
def test_build_watchlist_top5_has_meta_and_leis():
    payload = build_watchlist(GOGEL, top=5, include_benchmarks=True)
    assert payload["meta"]["metric_column"] == METRIC_COLUMN
    assert "LEI" in payload["meta"]["eligibility"]
    assert payload["meta"]["eligible_parents_total"] > 0
    issuers = payload["issuers"]
    assert len(issuers) >= 5
    ranked = [i for i in issuers if i.get("rank") is not None]
    assert ranked[0]["ste_mmboe"] >= ranked[-1]["ste_mmboe"]
    assert all(i.get("leis") for i in issuers)
    benches = {i.get("benchmark") for i in issuers if i.get("benchmark")}
    assert "OMV" in benches and "AKER" in benches and "TotalEnergies" in benches


@pytest.mark.skipif(not GOGEL.exists(), reason="GOGEL CSV not present")
def test_eni_ste_rank_and_leis():
    payload = build_watchlist(GOGEL, top=20, include_benchmarks=False)
    eni = next(
        (i for i in payload["issuers"] if i["name_parent"] == "Eni SpA"),
        None,
    )
    assert eni is not None, "Eni SpA missing from STE-ranked LEI-eligible top 20"
    assert eni["ste_mmboe"] > 4000
    assert eni["leis"]
    assert eni["lei"]
    assert eni["rank"] is not None
    enagas = next(
        (i for i in payload["issuers"] if i["name_parent"] == "Enagas SA"),
        None,
    )
    if enagas:
        assert len(enagas["leis"]) >= 2


@pytest.mark.skipif(not GOGEL.exists(), reason="GOGEL CSV not present")
def test_enagas_collects_finance_sub_lei():
    from papertrails.build_watchlist import _load_parent_aggregates

    rows = _load_parent_aggregates(GOGEL)
    enagas = next(r for r in rows if r["name_parent"] == "Enagas SA")
    assert "213800OU3FQKGM4M2U23" in enagas["leis"]
    assert "213800H2FQSU5E19V152" in enagas["leis"]
    assert enagas["leis"][0] == "213800OU3FQKGM4M2U23"


_RFSS_OK = "14857148,dfc16224b5c7ada6f83c5d0566174e81"


def _solr_get_docs(docs):
    mock = MagicMock()
    mock.json.return_value = {"response": {"docs": docs}}
    return mock


def test_downloadable_ftws_predicate_rejects_stda_secn_short_isin_and_no_rfss():
    assert _is_downloadable_ftws_doc(
        {
            "sec_docType": "STDA",
            "sec_isin": "EE0000001303",
            "sec_docRfssId": _RFSS_OK,
        }
    ) is False
    assert _is_downloadable_ftws_doc(
        {
            "sec_docType": "SECN",
            "sec_isin": "NO0010816895",
            "sec_docRfssId": _RFSS_OK,
        }
    ) is False
    assert _is_downloadable_ftws_doc(
        {
            "sec_docType": "FTWS",
            "sec_isin": "XS123",
            "sec_docRfssId": _RFSS_OK,
        }
    ) is False
    assert _is_downloadable_ftws_doc(
        {
            "sec_docType": "FTWS",
            "sec_isin": "XS3388188586",
            "sec_docRfssId": "not-a-pair",
        }
    ) is False
    assert _is_downloadable_ftws_doc(
        {
            "sec_docType": "FTWS",
            "sec_isin": "XS3388188586",
            "sec_docRfssId": _RFSS_OK,
        }
    ) is True


@patch("requests.get")
def test_solr_lei_stda_only_or_empty_is_not_downloadable_ftws(mock_get):
    mock_get.return_value = _solr_get_docs(
        [
            {
                "sec_docType": "STDA",
                "sec_isin": "EE0000001303",
                "sec_docRfssId": _RFSS_OK,
            }
        ]
    )
    assert solr_lei_has_downloadable_ftws("5493005044RTLQ5RZU70") is False
    mock_get.return_value = _solr_get_docs([])
    assert solr_lei_has_downloadable_ftws("5493005044RTLQ5RZU70") is False


@patch("requests.get")
def test_solr_lei_eni_shaped_ftws_is_downloadable(mock_get):
    mock_get.return_value = _solr_get_docs(
        [
            {
                "sec_docType": "FTWS",
                "sec_isin": "XS3388188586",
                "sec_docRfssId": _RFSS_OK,
            }
        ]
    )
    assert solr_lei_has_downloadable_ftws("BUCRF72VH5RBN7X3VL35") is True
    params = mock_get.call_args.kwargs["params"]
    assert "sec_docType:FTWS" in params["q"]
    assert int(params["rows"]) > 0


def test_verify_solr_keeps_eni_drops_no_ftws(monkeypatch, tmp_path):
    from papertrails import build_watchlist as bw

    rows = [
        {
            "name_parent": "Eesti Energia AS",
            "ste_mmboe": 1022.88,
            "production_mmboe": 3.84,
            "lei": "5493005044RTLQ5RZU70",
            "leis": ["5493005044RTLQ5RZU70"],
            "isin_equity": "",
            "bond_isins": [],
        },
        {
            "name_parent": "Eni SpA",
            "ste_mmboe": 5302.86,
            "production_mmboe": 804.3,
            "lei": "BUCRF72VH5RBN7X3VL35",
            "leis": ["BUCRF72VH5RBN7X3VL35"],
            "isin_equity": "",
            "bond_isins": [],
        },
    ]
    monkeypatch.setattr(bw, "_load_parent_aggregates", lambda _p: list(rows))
    hits = {"BUCRF72VH5RBN7X3VL35": True}
    monkeypatch.setattr(
        bw,
        "solr_lei_has_downloadable_ftws",
        lambda lei, timeout=12: bool(hits.get(lei)),
    )
    dummy = tmp_path / "gogel.csv"
    dummy.write_text("x", encoding="utf-8")
    payload = bw.build_watchlist(
        dummy, top=5, include_benchmarks=False, verify_solr=True
    )
    names = [i["name_parent"] for i in payload["issuers"]]
    assert "Eni SpA" in names
    assert "Eesti Energia AS" not in names
    assert "sec_docType:FTWS" in payload["meta"]["verify_solr_query"]
    assert "numFound>0" not in payload["meta"]["verify_solr_query"]


def test_content_gates_require_dealer_table(tmp_path):
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
    assert reason == "no_dealer_table"


def test_content_gates_publish(tmp_path):
    pdf = tmp_path / "ok.pdf"
    pdf.write_bytes(b"%PDF-1.4 minimal")
    deal, reason = content_gates(
        pdf_path=pdf,
        isin="XS1234567890",
        issuer="Test Co",
        extraction={
            "metadata": {
                "issue_date": "2024-01-01",
                "currency": "EUR",
                "issue_size": 600_000_000,
            },
            "extracted_banks": [
                {"raw_name": "Barclays Bank Ireland PLC", "role": "Dealer"},
                {"raw_name": "HSBC Continental Europe", "role": "Dealer"},
            ],
            "extraction_method": EXTRACTION_METHOD_DEALER_TABLE,
            "doc_type_code": "FTWS",
        },
        text_sample="ISIN XS1234567890 Final Terms",
    )
    assert reason is None
    assert deal is not None
    assert deal.isin == "XS1234567890"
    assert deal.underwriters[0]["raw_name"].startswith("Barclays")
    assert deal.extraction_method == EXTRACTION_METHOD_DEALER_TABLE
    assert deal.n_underwriters == 2
    assert deal.doc_type_code == "FTWS"
    assert deal.amount == 600_000_000
    assert deal.amount_kind == "tranche"
    assert deal.allocated_amount == 300_000_000
    assert all(u["allocated_amount"] == 300_000_000 for u in deal.underwriters)
    assert make_deal_id("XS1234567890", None, str(pdf)) == deal.id
    dumped = deal.to_dict()
    assert dumped["amount_kind"] == "tranche"
    assert dumped["allocated_amount"] == 300_000_000
    assert "programme_size" in dumped
    assert "pdf_path" not in dumped
    assert deal.pdf_path  # kept on the in-memory Deal for extract/quarantine

    programme_only, prog_reason = content_gates(
        pdf_path=pdf,
        isin="XS1234567890",
        issuer="Test Co",
        extraction={
            "metadata": {
                "issue_date": "2024-01-01",
                "currency": "EUR",
                "programme_size": 7_500_000_000,
            },
            "extracted_banks": [
                {"raw_name": "Barclays Bank Ireland PLC", "role": "Dealer"},
                {"raw_name": "HSBC Continental Europe", "role": "Dealer"},
            ],
            "extraction_method": EXTRACTION_METHOD_DEALER_TABLE,
            "doc_type_code": "FTWS",
        },
        text_sample="ISIN XS1234567890 Final Terms",
    )
    assert prog_reason is None
    assert programme_only is not None
    assert programme_only.amount is None
    assert programme_only.amount_kind == "programme"
    assert programme_only.programme_size == 7_500_000_000
    assert programme_only.allocated_amount is None
    assert all(u["allocated_amount"] is None for u in programme_only.underwriters)
    prog_dumped = programme_only.to_dict()
    assert prog_dumped["amount_kind"] == "programme"
    assert prog_dumped["programme_size"] == 7_500_000_000
    assert prog_dumped["allocated_amount"] is None
    assert "pdf_path" not in prog_dumped


def test_append_deal_public_payload_omits_pdf_path(tmp_path):
    pdf = tmp_path / "ok.pdf"
    pdf.write_bytes(b"%PDF-1.4 minimal")
    deal, reason = content_gates(
        pdf_path=pdf,
        isin="XS1234567890",
        issuer="Test Co",
        extraction={
            "metadata": {
                "issue_date": "2024-01-01",
                "currency": "EUR",
                "issue_size": 600_000_000,
            },
            "extracted_banks": [
                {"raw_name": "Barclays Bank Ireland PLC", "role": "Dealer"},
            ],
            "extraction_method": EXTRACTION_METHOD_DEALER_TABLE,
            "doc_type_code": "FTWS",
        },
        text_sample="ISIN XS1234567890 Final Terms",
    )
    assert reason is None
    assert deal is not None
    assert "pdf_path" not in deal.to_dict()
    out = tmp_path / "deals.json"
    assert append_deal(out, deal)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["deals"]
    for row in payload["deals"]:
        assert "pdf_path" not in row


def _dealer_names(pdf_path: Path) -> list:
    engine = ExtractionEngine(use_ocr=False)
    text = engine.extract_text(str(pdf_path)) or ""
    assert text.strip(), f"empty text for {pdf_path}"
    helper = AIBankExtractor(debug_mode=False)
    banks_a = helper.extract_dealer_management_banks(text)
    banks_b = helper.extract_dealer_management_banks(text)
    assert banks_a == banks_b, f"non-deterministic dealer-table extract for {pdf_path}"
    return [b.get("raw_name") for b in banks_a if b.get("raw_name")]


@pytest.mark.parametrize("pdf_path,label,expected", DEALER_TABLE_PDFS)
def test_dealer_table_regex_on_known_ftws(pdf_path: Path, label: str, expected: set):
    if not pdf_path.exists():
        pytest.skip(f"PDF missing for {label}: {pdf_path}")
    names = _dealer_names(pdf_path)
    assert names, f"no dealer-table banks for {label}"
    assert set(names) == expected, f"{label} bank set changed: {names}"


def test_aker_syndicated_managers_pdf():
    if not AKER_PDF.exists():
        pytest.skip(f"PDF missing: {AKER_PDF}")
    names = set(_dealer_names(AKER_PDF))
    assert names, "no dealer-table banks for Aker"
    whitelist_hit = names & {
        "Barclays Bank Ireland PLC",
        "Erste Group Bank AG",
        "Mizuho Securities Europe GmbH",
        "Raiffeisen Bank International AG",
        "UniCredit Bank GmbH",
        "Goldman Sachs Bank Europe SE",
        "BofA Securities Europe SA",
        "HSBC Continental Europe",
        "HSBC Bank plc",
        "Natixis",
        "SMBC Bank EU AG",
        "ABN AMRO Bank N.V.",
        "Nordea Bank Abp",
        "Skandinaviska Enskilda Banken AB (publ)",
        "Wells Fargo Securities Europe S.A.",
        "Société Générale",
    }
    assert len(whitelist_hit) >= 6, f"Aker expected ≥6 whitelist names, got {names}"


def test_enagas_syndicated_managers_pdf():
    if not ENAGAS_PDF.exists():
        pytest.skip(f"PDF missing: {ENAGAS_PDF}")
    names = set(_dealer_names(ENAGAS_PDF))
    assert "Barclays Bank Ireland PLC" in names
    assert "Société Générale" in names


# --- FTWS-only poll selection (not L2 classify_doc_tier) ---

_DL = "https://registers.esma.europa.eu/publication/downloadFile?fileId=1&checksum=abc"


def _solr_row(*, isin: str, code: str, date: str, doc_id: str = "1") -> dict:
    descr = {
        "FTWS": "Final terms, including the summary",
        "STDA": "Standalone prospectus",
        "SUPP": "Supplement",
    }[code]
    return {
        "isin": isin,
        "doc_type_code": code,
        "doc_type": descr,
        "date": date,
        "download_url": _DL,
        "url": _DL,
        "doc_id": doc_id,
        "score": 0.95,
        "solr_num_found": 4,
    }


class _FakeScraper:
    def __init__(self, rows_by_lei):
        self.rows_by_lei = rows_by_lei
        self.current_company = None
        self.downloaded_codes = []
        self.downloaded_isins = []
        self.search_and_process = MagicMock(return_value=[])
        self.close = MagicMock()

    def fetch_securities_via_solr(self, lei="", rows=50, isin=""):
        return [dict(r) for r in self.rows_by_lei.get(lei, [])]

    def download_selected_row(self, row):
        self.downloaded_codes.append(str(row.get("doc_type_code") or "").upper())
        self.downloaded_isins.append((row.get("isin") or "").upper())
        return f"/tmp/{row.get('isin')}.pdf"


def _watchlist_issuer(name: str, lei: str) -> dict:
    return {"issuers": [{"name_parent": name, "lei": lei, "leis": [lei]}]}


def test_l2_stda_still_tier1():
    """Leave L2 classify_doc_tier STDA-as-tier1 green (poll is FTWS-only, not this)."""
    assert classify_doc_tier("STDA", "Standalone prospectus") == "tier1"


def test_stda_only_solr_returns_empty_not_download():
    scraper = _FakeScraper(
        {
            "LEI1": [
                _solr_row(isin="EE0000001303", code="STDA", date="2025-05-20", doc_id="s1")
            ]
        }
    )
    result = _download_via_solr_lei(scraper, "Eesti", ["LEI1"], max_docs=1)
    assert isinstance(result, SolrLeiResult)
    assert result.downloads == []
    assert result.solr_row_count == 1
    assert result.ftws_candidates == 0
    assert result.dropped_non_ftws == 1
    assert scraper.downloaded_codes == []

    skipped = _download_via_solr_lei(
        scraper, "Eesti", ["LEI1"], max_docs=1, skip_isins={"EE0000001303"}
    )
    assert skipped.downloads == []
    assert skipped.dropped_non_ftws == 1
    assert scraper.downloaded_codes == []


def test_ftws_wins_over_newer_stda_never_downloads_stda():
    scraper = _FakeScraper(
        {
            "LEI1": [
                _solr_row(isin="NO0013671107", code="STDA", date="2026-01-01", doc_id="s"),
                _solr_row(isin="XS1111111111", code="FTWS", date="2024-06-01", doc_id="f"),
            ]
        }
    )
    result = _download_via_solr_lei(scraper, "IPC", ["LEI1"], max_docs=1)
    assert [d["isin"] for d in result.downloads] == ["XS1111111111"]
    assert result.dropped_non_ftws == 1
    assert scraper.downloaded_codes == ["FTWS"]
    assert "NO0013671107" not in scraper.downloaded_isins


def test_empty_ftws_list_when_only_supp():
    scraper = _FakeScraper(
        {
            "LEI1": [
                _solr_row(isin="CA00829Q1019", code="SUPP", date="2025-01-01", doc_id="p")
            ]
        }
    )
    result = _download_via_solr_lei(scraper, "Meren", ["LEI1"], max_docs=1)
    assert result.downloads == []
    assert result.dropped_non_ftws == 1
    assert scraper.downloaded_isins == []


def test_nonsyndicated_na_try_next_ftws():
    scraper = _FakeScraper(
        {
            "LEI1": [
                _solr_row(isin="XS2343835315", code="FTWS", date="2021-05-25", doc_id="na"),
                _solr_row(isin="XS2894862080", code="FTWS", date="2020-01-01", doc_id="ok"),
            ]
        }
    )

    def peek(path: str) -> bool:
        return "XS2343835315" in path

    result = _download_via_solr_lei(
        scraper, "Repsol", ["LEI1"], max_docs=1, peek_na=peek
    )
    assert [d["isin"] for d in result.downloads] == ["XS2894862080"]
    assert result.na_skipped == 1
    assert scraper.downloaded_isins == ["XS2343835315", "XS2894862080"]


def test_all_nonsyndicated_na_keeps_newest():
    scraper = _FakeScraper(
        {
            "LEI1": [
                _solr_row(isin="XS2222222222", code="FTWS", date="2024-01-01", doc_id="a"),
                _solr_row(isin="XS1111111111", code="FTWS", date="2020-01-01", doc_id="b"),
            ]
        }
    )
    result = _download_via_solr_lei(
        scraper, "X", ["LEI1"], max_docs=1, peek_na=lambda path: True
    )
    assert result.downloads == []
    assert [d["isin"] for d in result.nonsyndicated] == ["XS2222222222"]
    assert result.nonsyndicated[0].get("file_path")
    assert result.na_skipped == 1


def test_all_nonsyndicated_na_never_downloads_stda():
    scraper = _FakeScraper(
        {
            "LEI1": [
                _solr_row(isin="EE0000001303", code="STDA", date="2025-05-20", doc_id="s"),
                _solr_row(isin="XS2222222222", code="FTWS", date="2024-01-01", doc_id="a"),
                _solr_row(isin="XS1111111111", code="FTWS", date="2020-01-01", doc_id="b"),
            ]
        }
    )
    result = _download_via_solr_lei(
        scraper, "X", ["LEI1"], max_docs=1, peek_na=lambda path: True
    )
    assert result.downloads == []
    assert scraper.downloaded_codes == ["FTWS", "FTWS"]
    assert "EE0000001303" not in scraper.downloaded_isins
    assert result.dropped_non_ftws == 1


def test_two_nonsyndicated_na_then_filled_selects_filled():
    scraper = _FakeScraper(
        {
            "LEI1": [
                _solr_row(isin="XS3333333333", code="FTWS", date="2024-01-01", doc_id="n1"),
                _solr_row(isin="XS2222222222", code="FTWS", date="2022-01-01", doc_id="n2"),
                _solr_row(isin="XS1111111111", code="FTWS", date="2020-01-01", doc_id="ok"),
            ]
        }
    )

    def peek(path: str) -> bool:
        return "XS3333333333" in path or "XS2222222222" in path

    result = _download_via_solr_lei(
        scraper, "X", ["LEI1"], max_docs=1, peek_na=peek
    )
    assert [d["isin"] for d in result.downloads] == ["XS1111111111"]
    assert result.nonsyndicated == []
    assert scraper.downloaded_isins == [
        "XS3333333333",
        "XS2222222222",
        "XS1111111111",
    ]


def test_extract_all_na_is_non_syndicated_not_no_dealer_table(monkeypatch, tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-")
    rec = {
        "isin": "XS2343835315",
        "issuer": "Repsol SA",
        "file_path": str(pdf),
    }
    monkeypatch.setattr(
        "papertrails.run_alerts._peek_nonsyndicated_na", lambda path: True
    )
    extract_text = MagicMock(side_effect=AssertionError("extract_text must not run"))
    dealer = MagicMock(side_effect=AssertionError("dealer-table must not run"))
    monkeypatch.setattr(
        "papertrails.run_alerts.ExtractionEngine.extract_text", extract_text
    )
    monkeypatch.setattr(
        "papertrails.run_alerts.AIBankExtractor.extract_dealer_management_banks",
        dealer,
    )
    qdir = tmp_path / "q"
    deals_path = tmp_path / "deals.json"
    stats = extract_and_publish(
        [rec], deals_path=deals_path, quarantine_dir=qdir
    )
    assert stats["quarantine"] == 1
    assert stats["non_syndicated"] == 1
    assert stats["no_dealer_table"] == 0
    payloads = [json.loads(p.read_text(encoding="utf-8")) for p in qdir.glob("*.json")]
    assert len(payloads) == 1
    assert payloads[0]["reject_reason"] == "non_syndicated"
    assert payloads[0]["reject_reason"] != "no_dealer_table"
    extract_text.assert_not_called()
    dealer.assert_not_called()
    if deals_path.exists():
        data = json.loads(deals_path.read_text(encoding="utf-8"))
        assert not data.get("deals")
    assert pdf.exists()


def test_extract_true_regex_miss_still_no_dealer_table(monkeypatch, tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-")
    rec = {
        "isin": "XS0000000000",
        "issuer": "A2A SpA",
        "file_path": str(pdf),
    }
    monkeypatch.setattr(
        "papertrails.run_alerts._peek_nonsyndicated_na", lambda path: False
    )
    monkeypatch.setattr(
        "papertrails.run_alerts.ExtractionEngine.extract_text",
        lambda self, path: "no dealer table in this prospectus",
    )
    monkeypatch.setattr(
        "papertrails.run_alerts.AIBankExtractor.extract_dealer_management_banks",
        lambda self, text: [],
    )
    qdir = tmp_path / "q"
    stats = extract_and_publish(
        [rec], deals_path=tmp_path / "deals.json", quarantine_dir=qdir
    )
    assert stats["quarantine"] == 1
    assert stats["no_dealer_table"] == 1
    assert stats["non_syndicated"] == 0
    payloads = [json.loads(p.read_text(encoding="utf-8")) for p in qdir.glob("*.json")]
    assert len(payloads) == 1
    assert payloads[0]["reject_reason"] == "no_dealer_table"


def test_poll_all_nonsyndicated_na_does_not_ui_or_stda(monkeypatch, tmp_path):
    fake = _FakeScraper(
        {
            "LEI1": [
                _solr_row(isin="XS2222222222", code="FTWS", date="2024-01-01", doc_id="a"),
                _solr_row(isin="XS1111111111", code="FTWS", date="2020-01-01", doc_id="b"),
                _solr_row(isin="EE0000001303", code="STDA", date="2025-05-20", doc_id="s"),
            ]
        }
    )
    monkeypatch.setattr("papertrails.run_alerts.ESMAScraper", lambda *a, **k: fake)
    monkeypatch.setattr(
        "papertrails.run_alerts._peek_nonsyndicated_na", lambda path: True
    )
    seen_path = tmp_path / "seen.json"
    stats = {}
    out = poll_watchlist(
        _watchlist_issuer("Repsol SA", "LEI1"),
        seen_path=seen_path,
        pdf_root=tmp_path / "pdfs",
        headless=True,
        isin_limit_per_issuer=1,
        selection_stats=stats,
    )
    assert out == []
    assert stats.get("non_syndicated") == 1
    assert stats.get("new_ftws", 0) == 0
    fake.search_and_process.assert_not_called()
    seen = json.loads(seen_path.read_text(encoding="utf-8"))
    entries = list(seen["entries"].values())
    assert not any(e.get("status") == "no_tier1" for e in entries)
    downloaded = [e for e in entries if e.get("status") == "downloaded"]
    assert any(e.get("isin") == "XS2222222222" for e in downloaded)
    assert "STDA" not in fake.downloaded_codes
    assert "EE0000001303" not in fake.downloaded_isins


def test_is_nonsyndicated_na_does_not_flag_syndicated_rwe_shape():
    syndicated = (
        "Dealer / Management Group (specify) SMBC Bank EU AG "
        "If syndicated, names of Managers: SMBC Bank EU AG "
        "If non-syndicated, name of Dealer: Not Applicable"
    )
    assert _is_nonsyndicated_na(syndicated) is False
    na = (
        "If syndicated, names of Managers: Not Applicable "
        "If non-syndicated, name of Dealer: N/A"
    )
    assert _is_nonsyndicated_na(na) is True


def test_seen_stda_does_not_count_toward_isin_limit(tmp_path):
    pdf_root = tmp_path / "pdfs"
    issuer_dir = pdf_root / "Eesti Energia AS"
    issuer_dir.mkdir(parents=True)
    stda = issuer_dir / "Standalone_prospectus.pdf"
    stda.write_bytes(b"%PDF-1.4")
    entries = {
        "EE0000001303|Standalone_prospectus.pdf": {
            "issuer": "Eesti Energia AS",
            "status": "downloaded",
            "isin": "EE0000001303",
            "doc_type_code": "STDA",
            "file_path": str(stda),
        }
    }
    assert _count_issuer_alert_pdfs("Eesti Energia AS", entries, pdf_root) == 0


def test_seen_ftws_counts_toward_isin_limit(tmp_path):
    pdf_root = tmp_path / "pdfs"
    issuer_dir = pdf_root / "Repsol SA"
    issuer_dir.mkdir(parents=True)
    ftws = issuer_dir / "Final_terms.pdf"
    ftws.write_bytes(b"%PDF-1.4")
    entries = {
        "XS2343835315|Final_terms.pdf": {
            "issuer": "Repsol SA",
            "status": "downloaded",
            "isin": "XS2343835315",
            "doc_type_code": "FTWS",
            "file_path": str(ftws),
        }
    }
    assert _count_issuer_alert_pdfs("Repsol SA", entries, pdf_root) == 1


def test_poll_does_not_call_ui_when_solr_had_rows_no_ftws(monkeypatch, tmp_path):
    fake = _FakeScraper(
        {
            "LEI1": [
                _solr_row(isin="EE0000001303", code="STDA", date="2025-05-20", doc_id="s1")
            ]
        }
    )
    monkeypatch.setattr("papertrails.run_alerts.ESMAScraper", lambda *a, **k: fake)
    seen_path = tmp_path / "seen.json"
    pdf_root = tmp_path / "pdfs"
    out = poll_watchlist(
        _watchlist_issuer("Eesti Energia AS", "LEI1"),
        seen_path=seen_path,
        pdf_root=pdf_root,
        headless=True,
        isin_limit_per_issuer=1,
    )
    assert out == []
    fake.search_and_process.assert_not_called()
    seen = json.loads(seen_path.read_text(encoding="utf-8"))
    statuses = [e.get("status") for e in seen["entries"].values()]
    assert "no_tier1" in statuses
    assert not any(e.get("status") == "downloaded" for e in seen["entries"].values())


def test_poll_calls_ui_only_when_solr_zero_rows_and_keeps_ftws(monkeypatch, tmp_path):
    fake = _FakeScraper({"LEI1": []})
    fake.search_and_process.return_value = [
        {
            "file_path": str(tmp_path / "stda.pdf"),
            "isin": "EE0000001303",
            "doc_type_code": "STDA",
            "doc_type": "Standalone prospectus",
        },
        {
            "file_path": str(tmp_path / "ftws.pdf"),
            "isin": "XS1111111111",
            "doc_type_code": "FTWS",
            "doc_type": "Final terms, including the summary",
        },
    ]
    monkeypatch.setattr("papertrails.run_alerts.ESMAScraper", lambda *a, **k: fake)
    out = poll_watchlist(
        _watchlist_issuer("Eesti Energia AS", "LEI1"),
        seen_path=tmp_path / "seen.json",
        pdf_root=tmp_path / "pdfs",
        headless=True,
        isin_limit_per_issuer=1,
    )
    fake.search_and_process.assert_called_once()
    assert [d["isin"] for d in out] == ["XS1111111111"]
    assert all(d.get("doc_type_code") == "FTWS" for d in out)


def test_poll_seen_stda_does_not_skip_issuer(monkeypatch, tmp_path):
    pdf_root = tmp_path / "pdfs"
    issuer_dir = pdf_root / "Eesti Energia AS"
    issuer_dir.mkdir(parents=True)
    stda = issuer_dir / "Standalone_prospectus.pdf"
    stda.write_bytes(b"%PDF-1.4")
    seen_path = tmp_path / "seen.json"
    seen_path.write_text(
        json.dumps(
            {
                "entries": {
                    "EE0000001303|Standalone_prospectus.pdf": {
                        "issuer": "Eesti Energia AS",
                        "status": "downloaded",
                        "isin": "EE0000001303",
                        "doc_type_code": "STDA",
                        "file_path": str(stda),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    fake = _FakeScraper(
        {
            "LEI1": [
                _solr_row(isin="XS9999999999", code="FTWS", date="2024-01-01", doc_id="f")
            ]
        }
    )
    monkeypatch.setattr("papertrails.run_alerts.ESMAScraper", lambda *a, **k: fake)
    out = poll_watchlist(
        _watchlist_issuer("Eesti Energia AS", "LEI1"),
        seen_path=seen_path,
        pdf_root=pdf_root,
        headless=True,
        isin_limit_per_issuer=1,
    )
    fake.search_and_process.assert_not_called()
    assert [d["isin"] for d in out] == ["XS9999999999"]


def test_force_ignores_ftws_slot_count(monkeypatch, tmp_path):
    pdf_root = tmp_path / "pdfs"
    issuer_dir = pdf_root / "Repsol SA"
    issuer_dir.mkdir(parents=True)
    old = issuer_dir / "old.pdf"
    old.write_bytes(b"%PDF-1.4")
    seen_path = tmp_path / "seen.json"
    seen_path.write_text(
        json.dumps(
            {
                "entries": {
                    "XS2343835315|old.pdf": {
                        "issuer": "Repsol SA",
                        "status": "downloaded",
                        "isin": "XS2343835315",
                        "doc_type_code": "FTWS",
                        "file_path": str(old),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    fake = _FakeScraper(
        {
            "LEI1": [
                _solr_row(isin="XS2343835315", code="FTWS", date="2021-05-25", doc_id="old"),
                _solr_row(isin="XS2894862080", code="FTWS", date="2020-01-01", doc_id="new"),
            ]
        }
    )
    monkeypatch.setattr("papertrails.run_alerts.ESMAScraper", lambda *a, **k: fake)

    skipped = poll_watchlist(
        _watchlist_issuer("Repsol SA", "LEI1"),
        seen_path=seen_path,
        pdf_root=pdf_root,
        headless=True,
        isin_limit_per_issuer=1,
        force=False,
    )
    assert skipped == []
    assert fake.downloaded_isins == []

    forced = poll_watchlist(
        _watchlist_issuer("Repsol SA", "LEI1"),
        seen_path=seen_path,
        pdf_root=pdf_root,
        headless=True,
        isin_limit_per_issuer=1,
        force=True,
    )
    assert [d["isin"] for d in forced] == ["XS2894862080"]
    assert "XS2343835315" not in fake.downloaded_isins


def test_incremental_second_poll_downloads_zero(monkeypatch, tmp_path):
    fake = _FakeScraper(
        {
            "LEI1": [
                _solr_row(isin="XS1111111111", code="FTWS", date="2024-06-01", doc_id="f")
            ]
        }
    )
    monkeypatch.setattr("papertrails.run_alerts.ESMAScraper", lambda *a, **k: fake)
    seen_path = tmp_path / "seen.json"
    pdf_root = tmp_path / "pdfs"
    first = poll_watchlist(
        _watchlist_issuer("Repsol SA", "LEI1"),
        seen_path=seen_path,
        pdf_root=pdf_root,
        headless=True,
        isin_limit_per_issuer=1,
    )
    assert [d["isin"] for d in first] == ["XS1111111111"]
    n_dl = len(fake.downloaded_isins)
    stats = {}
    second = poll_watchlist(
        _watchlist_issuer("Repsol SA", "LEI1"),
        seen_path=seen_path,
        pdf_root=pdf_root,
        headless=True,
        isin_limit_per_issuer=1,
        selection_stats=stats,
    )
    assert second == []
    assert fake.downloaded_isins[n_dl:] == []
    assert stats.get("new_ftws", 0) == 0


def test_incremental_newer_ftws_downloads_despite_existing(monkeypatch, tmp_path):
    pdf_root = tmp_path / "pdfs"
    issuer_dir = pdf_root / "Repsol SA"
    issuer_dir.mkdir(parents=True)
    old = issuer_dir / "old.pdf"
    old.write_bytes(b"%PDF-1.4")
    seen_path = tmp_path / "seen.json"
    seen_path.write_text(
        json.dumps(
            {
                "entries": {
                    "XS2343835315|old.pdf": {
                        "issuer": "Repsol SA",
                        "status": "downloaded",
                        "isin": "XS2343835315",
                        "doc_type_code": "FTWS",
                        "file_path": str(old),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    fake = _FakeScraper(
        {
            "LEI1": [
                _solr_row(isin="XS9999999999", code="FTWS", date="2026-08-01", doc_id="n"),
                _solr_row(isin="XS2343835315", code="FTWS", date="2021-05-25", doc_id="old"),
            ]
        }
    )
    monkeypatch.setattr("papertrails.run_alerts.ESMAScraper", lambda *a, **k: fake)
    stats = {}
    out = poll_watchlist(
        _watchlist_issuer("Repsol SA", "LEI1"),
        seen_path=seen_path,
        pdf_root=pdf_root,
        headless=True,
        isin_limit_per_issuer=1,
        force=False,
        selection_stats=stats,
    )
    assert [d["isin"] for d in out] == ["XS9999999999"]
    assert stats.get("new_ftws") == 1
    assert "XS2343835315" not in fake.downloaded_isins


def test_skip_published_isin_no_download(monkeypatch, tmp_path):
    deals_path = tmp_path / "deals.json"
    deals_path.write_text(
        json.dumps({"deals": [{"isin": "XS1111111111", "issuer": "Eni SpA"}]}),
        encoding="utf-8",
    )
    fake = _FakeScraper(
        {
            "LEI1": [
                _solr_row(isin="XS1111111111", code="FTWS", date="2026-05-21", doc_id="p")
            ]
        }
    )
    monkeypatch.setattr("papertrails.run_alerts.ESMAScraper", lambda *a, **k: fake)
    stats = {}
    seen_path = tmp_path / "seen.json"
    out = poll_watchlist(
        _watchlist_issuer("Eni SpA", "LEI1"),
        seen_path=seen_path,
        pdf_root=tmp_path / "pdfs",
        headless=True,
        isin_limit_per_issuer=1,
        deals_path=deals_path,
        selection_stats=stats,
    )
    assert out == []
    assert fake.downloaded_isins == []
    assert stats.get("skipped_published") == 1
    assert stats.get("new_ftws", 0) == 0
    seen = json.loads(seen_path.read_text(encoding="utf-8"))
    assert not any(e.get("status") == "no_tier1" for e in seen["entries"].values())


def test_yield_report_incremental_keys(tmp_path):
    seen_path = tmp_path / "seen.json"
    seen_path.write_text(json.dumps({"entries": {}}), encoding="utf-8")
    deals_path = tmp_path / "deals.json"
    deals_path.write_text(json.dumps({"deals": []}), encoding="utf-8")
    report = write_yield_report(
        out_path=tmp_path / "yield.json",
        seen_path=seen_path,
        deals_path=deals_path,
        quarantine_dir=tmp_path / "q",
        pdf_root=tmp_path / "pdfs",
        extract_stats={"published": 0, "quarantine": 0, "skipped": 0},
        poll_downloads=0,
        selection_stats={
            "new_ftws": 0,
            "skipped_published": 2,
            "na_skipped": 1,
            "non_syndicated": 0,
        },
    )
    assert report["incremental"] == {
        "new_ftws": 0,
        "skipped_published": 2,
        "na_skipped": 1,
        "non_syndicated": 0,
    }
    assert report["totals"]["non_syndicated"] == 0
    assert report["totals"]["no_dealer_table"] == 0


def test_yield_report_splits_non_syndicated_from_no_dealer_table(tmp_path):
    seen_path = tmp_path / "seen.json"
    seen_path.write_text(
        json.dumps(
            {
                "entries": {
                    "XS1|a.pdf": {
                        "issuer": "Bapco",
                        "status": "downloaded",
                        "isin": "XS1",
                        "file_path": str(tmp_path / "a.pdf"),
                    },
                    "XS2|b.pdf": {
                        "issuer": "A2A SpA",
                        "status": "downloaded",
                        "isin": "XS2",
                        "file_path": str(tmp_path / "b.pdf"),
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    qdir = tmp_path / "q"
    qdir.mkdir()
    (qdir / "1.json").write_text(
        json.dumps({"isin": "XS1", "reject_reason": "non_syndicated"}),
        encoding="utf-8",
    )
    (qdir / "2.json").write_text(
        json.dumps({"isin": "XS2", "reject_reason": "no_dealer_table"}),
        encoding="utf-8",
    )
    deals_path = tmp_path / "deals.json"
    deals_path.write_text(json.dumps({"deals": []}), encoding="utf-8")
    report = write_yield_report(
        out_path=tmp_path / "yield.json",
        seen_path=seen_path,
        deals_path=deals_path,
        quarantine_dir=qdir,
        pdf_root=tmp_path / "pdfs",
        extract_stats={
            "published": 0,
            "quarantine": 2,
            "skipped": 0,
            "non_syndicated": 1,
            "no_dealer_table": 1,
        },
        poll_downloads=0,
        watchlist={
            "issuers": [{"name_parent": "Bapco"}, {"name_parent": "A2A SpA"}]
        },
        selection_stats={
            "new_ftws": 0,
            "skipped_published": 0,
            "na_skipped": 0,
            "non_syndicated": 1,
        },
    )
    assert report["totals"]["quarantine"] == 2
    assert report["totals"]["non_syndicated"] == 1
    assert report["totals"]["no_dealer_table"] == 1
    assert report["quarantine_by_reason"]["non_syndicated"] == 1
    assert report["quarantine_by_reason"]["no_dealer_table"] == 1
    assert report["extract_this_run"]["non_syndicated"] == 1
    assert report["extract_this_run"]["no_dealer_table"] == 1
    assert report["incremental"]["non_syndicated"] == 1
