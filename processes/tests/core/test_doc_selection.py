"""Unit tests for ESMA document tier selection."""

import pytest

from processes.pipeline_components.validators import (
    classify_doc_tier,
    select_esma_rows,
    compute_allocated_amount,
    filter_underwriter_banks,
    compute_completeness_gates,
)


class TestClassifyDocTier:
    def test_bpwo_reject(self):
        assert classify_doc_tier("BPWO", "Base prospectus without Final terms") == "reject"

    def test_ftws_tier1(self):
        assert classify_doc_tier("FTWS", "Final terms, including the summary") == "tier1"

    def test_final_terms_descr_tier1(self):
        assert classify_doc_tier(None, "Final Terms dated 2024") == "tier1"

    def test_pricing_supplement_tier1(self):
        assert classify_doc_tier(None, "Pricing Supplement") == "tier1"


class TestSelectEsmaRows:
    def test_rejects_programme(self):
        rows = [
            {"url": "u1", "isin": "XS1111111111", "doc_type": "Base prospectus without Final terms", "score": 0.9, "isin_match": 1.0},
            {"url": "u2", "isin": "XS1111111111", "doc_type": "Final Terms", "score": 0.7, "isin_match": 1.0},
        ]
        selected = select_esma_rows(rows, policy="strict", min_score=0.55)
        assert len(selected) == 1
        assert selected[0]["url"] == "u2"

    def test_newest_date_wins_over_smaller_file(self):
        rows = [
            {
                "url": "u1",
                "isin": "XS1111111111",
                "doc_type_code": "FTWS",
                "doc_type": "Final Terms",
                "date": "2024-01-01",
                "score": 0.9,
                "isin_match": 1.0,
                "file_size_bytes": 500000,
            },
            {
                "url": "u2",
                "isin": "XS1111111111",
                "doc_type_code": "FTWS",
                "doc_type": "Final Terms",
                "date": "2025-06-01",
                "score": 0.8,
                "isin_match": 1.0,
                "file_size_bytes": 100000,
            },
        ]
        selected = select_esma_rows(rows, policy="strict", min_score=0.55)
        assert len(selected) == 1
        assert selected[0]["url"] == "u2"

    def test_ftws_over_stda_same_isin(self):
        rows = [
            {
                "url": "u_stda",
                "isin": "XS2222222222",
                "doc_type_code": "STDA",
                "doc_type": "Standalone prospectus",
                "date": "2021-01-22",
                "score": 0.95,
                "isin_match": 1.0,
            },
            {
                "url": "u_ftws",
                "isin": "XS2222222222",
                "doc_type_code": "FTWS",
                "doc_type": "Final terms",
                "date": "2024-11-19",
                "score": 0.7,
                "isin_match": 1.0,
            },
        ]
        selected = select_esma_rows(rows, policy="strict", min_score=0.55)
        assert len(selected) == 1
        assert selected[0]["url"] == "u_ftws"


class TestAllocation:
    def test_equal_split(self):
        banks = [
            {"raw_name": "Bank A", "role": "Bookrunner"},
            {"raw_name": "Bank B", "role": "Lead Manager"},
            {"raw_name": "Fiscal Agent", "role": "Fiscal Agent"},
        ]
        amount, n = compute_allocated_amount(600_000_000, banks)
        assert n == 2
        assert amount == 300_000_000

    def test_blocklist(self):
        banks = [{"raw_name": "Fiscal Agent", "role": "Fiscal Agent"}]
        assert filter_underwriter_banks(banks) == []


class TestCompletenessGates:
    def test_ship_when_passing(self):
        report = compute_completeness_gates({
            "isins_in_scope": 10,
            "isins_with_tier1": 8,
            "tier1_downloaded": 8,
            "tier1_valid_underwriter_set": 7,
            "eligible_for_allocation": 7,
            "allocated_rows": 42,
            "benchmark_exact_matches": 2,
            "benchmark_role_hallucinations": False,
        })
        assert report["ship"] is True


class TestDealerTableExtraction:
    def test_omv_style_dealer_block(self):
        from processes.pdf_extraction.extractors.ai_bank_extractor import AIBankExtractor

        snippet = (
            "Dealer/Management Group (specify) Barclays Bank Ireland PLC One Molesworth Street "
            "Erste Group Bank AG Am Belvedere 1 Mizuho Securities Europe GmbH Taunustor 1 "
            "Raiffeisen Bank International AG Am Stadtpark 9 Socit Gnrale Immeuble Basalte "
            "UniCredit Bank GmbH Arabellastrae 12 Subscription Agreement"
        )
        banks = AIBankExtractor(debug_mode=False).extract_dealer_management_banks(snippet)
        names = {b["raw_name"] for b in banks}
        assert len(banks) >= 5
        assert "Barclays Bank Ireland PLC" in names
        assert "Erste Group Bank AG" in names
        assert "Société Générale" in names
