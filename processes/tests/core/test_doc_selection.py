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

    def test_standalone_prospectus_descr_is_tier1(self):
        assert classify_doc_tier(None, "Standalone prospectus") == "tier1"
        assert classify_doc_tier("STDA", "Standalone prospectus") == "tier1"


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

    def test_high_score_without_isin_match_dropped(self):
        rows = [
            {
                "url": "u_name",
                "isin": "XS9999999999",
                "doc_type": "Final Terms",
                "score": 0.99,
                "isin_match": 0.0,
            },
        ]
        assert select_esma_rows(rows, policy="strict", min_score=0.55) == []

    def test_lei_match_keeps_tier1_without_gogel_isin(self):
        rows = [
            {
                "url": "u_lei",
                "isin": "XS1111111111",
                "doc_type_code": "FTWS",
                "doc_type": "Final Terms",
                "score": 0.95,
                "isin_match": 0.0,
                "lei_match": 1.0,
            },
        ]
        selected = select_esma_rows(rows, policy="strict", min_score=0.55)
        assert len(selected) == 1
        assert selected[0]["url"] == "u_lei"

    def test_no_isin_on_row_not_selected(self):
        rows = [
            {
                "url": "u_empty",
                "isin": "",
                "doc_type": "Final Terms",
                "score": 0.9,
                "isin_match": 0.0,
            },
        ]
        assert select_esma_rows(rows, policy="strict") == []

    def test_one_per_isin(self):
        rows = [
            {
                "url": "u1",
                "isin": "XS1111111111",
                "doc_type_code": "FTWS",
                "doc_type": "Final Terms",
                "date": "2024-01-01",
                "score": 0.9,
                "isin_match": 1.0,
            },
            {
                "url": "u2",
                "isin": "XS1111111111",
                "doc_type_code": "FTWS",
                "doc_type": "Final Terms",
                "date": "2025-01-01",
                "score": 0.8,
                "isin_match": 1.0,
            },
        ]
        selected = select_esma_rows(rows, policy="strict")
        assert len(selected) == 1
        assert selected[0]["url"] == "u2"


class TestSolrDownloadUrlJoin:
    def test_rfss_builds_downloadfile_url(self):
        from processes.esma_scraper import download_url_from_rfss

        url = download_url_from_rfss("14857148,dfc16224b5c7ada6f83c5d0566174e81")
        assert "downloadFile" in url
        assert "fileId=14857148" in url
        assert "checksum=dfc16224b5c7ada6f83c5d0566174e81" in url
        assert download_url_from_rfss("") == ""
        assert download_url_from_rfss("not-a-pair") == ""

    def test_details_href_is_not_a_download_url(self):
        from processes.esma_scraper import resolve_download_url

        row = {
            "url": "https://registers.esma.europa.eu/publication/details?core=esma_registers_priii_securities&docId=20387494",
            "doc_id": "20387494",
        }
        assert resolve_download_url(row) == ""

    def test_attach_solr_url_by_doc_id(self):
        from processes.esma_scraper import attach_solr_download_urls, resolve_download_url

        ui = [{
            "doc_id": "20387494",
            "url": "https://registers.esma.europa.eu/publication/details?core=esma_registers_priii_securities&docId=20387494",
            "isin": "XS2367164576",
        }]
        solr = [{
            "doc_id": "20387494",
            "sec_docRfssId": "14857148,dfc16224b5c7ada6f83c5d0566174e81",
        }]
        n = attach_solr_download_urls(ui, solr)
        assert n == 1
        assert "downloadFile?fileId=14857148" in resolve_download_url(ui[0])


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

    def test_rwe_style_slash_spacing(self):
        from processes.pdf_extraction.extractors.ai_bank_extractor import AIBankExtractor

        snippet = (
            "Dealer / Management Group (specify) SMBC Bank EU AG "
            "Subscription Agreement"
        )
        banks = AIBankExtractor(debug_mode=False).extract_dealer_management_banks(snippet)
        names = {b["raw_name"] for b in banks}
        assert "SMBC Bank EU AG" in names

    def test_romgaz_style_page_break_gap(self):
        from processes.pdf_extraction.extractors.ai_bank_extractor import AIBankExtractor

        snippet = (
            "If syndicated: 8 | Names of Managers: Unicredit Bank GmbH "
            "Barclays Bank Ireland PLC Date of Syndication Agreement"
        )
        banks = AIBankExtractor(debug_mode=False).extract_dealer_management_banks(snippet)
        names = {b["raw_name"] for b in banks}
        assert "UniCredit Bank GmbH" in names
        assert "Barclays Bank Ireland PLC" in names

    def test_preferred_anchor_not_displaced_by_syndicated_line(self):
        from processes.pdf_extraction.extractors.ai_bank_extractor import AIBankExtractor

        snippet = (
            "If syndicated, names of the Managers: decoy only "
            "Active Bookrunners Goldman Sachs Bank Europe SE "
            "Barclays Bank Ireland PLC BofA Securities Europe SA "
            "HSBC Continental Europe SMBC Bank EU AG Natixis "
            "Stabilisation Manager"
        )
        banks = AIBankExtractor(debug_mode=False).extract_dealer_management_banks(snippet)
        names = {b["raw_name"] for b in banks}
        assert names == {
            "Goldman Sachs Bank Europe SE",
            "Barclays Bank Ireland PLC",
            "BofA Securities Europe SA",
            "HSBC Continental Europe",
            "SMBC Bank EU AG",
            "Natixis",
        }

    def test_gasunie_syndicated_names_without_of_managers(self):
        from processes.pdf_extraction.extractors.ai_bank_extractor import AIBankExtractor

        snippet = (
            "Method of distribution: Syndicated (ii) If syndicated, names: "
            "Coöperatieve Rabobank U.A. Crédit Agricole Corporate and Investment Bank "
            "Deutsche Bank Aktiengesellschaft NatWest Markets N.V. "
            "(v) If non-syndicated, name of relevant Dealer: Not Applicable"
        )
        banks = AIBankExtractor(debug_mode=False).extract_dealer_management_banks(snippet)
        names = {b["raw_name"] for b in banks}
        assert "Coöperatieve Rabobank U.A." in names
        assert "Crédit Agricole Corporate and Investment Bank" in names
        assert "Deutsche Bank Aktiengesellschaft" in names
        assert "NatWest Markets N.V." in names

    def test_veolia_skips_cover_as_bookrunners_uses_part_b(self):
        from processes.pdf_extraction.extractors.ai_bank_extractor import AIBankExtractor

        cover = (
            "CIC SOCIÉTÉ GÉNÉRALE as Global Coordinators and Active Bookrunners "
            "BRAND LINE as Active Bookrunners "
        )
        part_b = (
            "Method of distribution Syndicated If syndicated, names of Managers: "
            "Global Coordinators and Active Bookrunners "
            "Crédit Industriel et Commercial S.A. Société Générale "
            "Active Bookrunners Banco Santander, S.A. Commerzbank Aktiengesellschaft "
            "ING Bank N.V., Belgian Branch J.P. Morgan SE MUFG Securities (Europe) N.V. "
            "If non-syndicated, name of Dealer: Not Applicable"
        )
        snippet = cover + (" prospectus boilerplate " * 400) + part_b
        banks = AIBankExtractor(debug_mode=False).extract_dealer_management_banks(snippet)
        names = {b["raw_name"] for b in banks}
        assert "Société Générale" in names
        assert "Crédit Industriel et Commercial S.A." in names
        assert "Banco Santander, S.A." in names
        assert "Commerzbank Aktiengesellschaft" in names

    def test_total_xs2937308737_active_vs_joint(self):
        from processes.pdf_extraction.extractors.ai_bank_extractor import AIBankExtractor

        snippet = (
            "Method of distribution Syndicated (ii) If syndicated, names of the Managers: "
            "Global Coordinators and Active Bookrunners Barclays Bank Ireland PLC "
            "Goldman Sachs Bank Europe SE Joint Active Bookrunners BofA Securities Europe SA "
            "HSBC Continental Europe Natixis SMBC Bank EU AG "
            "(iv) Stabilisation Manager: Barclays Bank Ireland PLC"
        )
        banks = AIBankExtractor(debug_mode=False).extract_dealer_management_banks(snippet)
        by_name = {b["raw_name"]: b["role"] for b in banks}
        assert by_name["Barclays Bank Ireland PLC"] == "Active Bookrunner"
        assert by_name["Goldman Sachs Bank Europe SE"] == "Active Bookrunner"
        assert by_name["BofA Securities Europe SA"] == "Joint Active Bookrunner"
        assert by_name["HSBC Continental Europe"] == "Joint Active Bookrunner"
        assert by_name["Natixis"] == "Joint Active Bookrunner"
        assert by_name["SMBC Bank EU AG"] == "Joint Active Bookrunner"

    def test_vier_gas_xs3170345980_global_active_passive(self):
        from processes.pdf_extraction.extractors.ai_bank_extractor import AIBankExtractor

        snippet = (
            "Dealer/Management Group (specify) "
            "Global Coordinators ING Bank N.V. UniCredit Bank GmbH "
            "Active Bookrunners NatWest Markets N.V. "
            "Passive Bookrunners Commerzbank Aktiengesellschaft "
            "Subscription Agreement"
        )
        banks = AIBankExtractor(debug_mode=False).extract_dealer_management_banks(snippet)
        by_name = {b["raw_name"]: b["role"] for b in banks}
        assert by_name["ING Bank N.V."] == "Global Coordinator"
        assert by_name["UniCredit Bank GmbH"] == "Global Coordinator"
        assert by_name["NatWest Markets N.V."] == "Active Bookrunner"
        assert by_name["Commerzbank Aktiengesellschaft"] == "Passive Bookrunner"

    def test_eni_rwe_ep_stay_dealer_without_split_headings(self):
        from processes.pdf_extraction.extractors.ai_bank_extractor import AIBankExtractor

        extractor = AIBankExtractor(debug_mode=False)
        snippets = (
            (
                "If syndicated, names of Managers: BPER Banca S.p.A. Deutsche Bank Aktiengesellschaft "
                "HSBC Continental Europe Intesa Sanpaolo S.p.A. J.P. Morgan SE NATIXIS "
                "Société Générale UniCredit Bank GmbH Date of Subscription Agreement"
            ),
            (
                "Dealer / Management Group (specify) SMBC Bank EU AG "
                "Deutsche Bank Aktiengesellschaft Subscription Agreement"
            ),
            (
                "If syndicated: (A) Names of Dealers Commerzbank Aktiengesellschaft "
                "Goldman Sachs Bank Europe SE ING Bank N.V. SMBC Bank EU AG "
                "Société Générale (B) Stabilisation Manager(s), if any: Not Applicable"
            ),
        )
        for snippet in snippets:
            banks = extractor.extract_dealer_management_banks(snippet)
            assert banks
            assert {b["role"] for b in banks} == {"Dealer"}

    def test_mixed_roles_still_equal_split_of_tranche(self):
        from processes.pdf_extraction.extractors.ai_bank_extractor import AIBankExtractor

        snippet = (
            "Active Bookrunners Barclays Bank Ireland PLC "
            "Passive Bookrunners UniCredit Bank GmbH Stabilisation Manager"
        )
        banks = AIBankExtractor(debug_mode=False).extract_dealer_management_banks(snippet)
        assert {b["raw_name"]: b["role"] for b in banks} == {
            "Barclays Bank Ireland PLC": "Active Bookrunner",
            "UniCredit Bank GmbH": "Passive Bookrunner",
        }
        amount, n = compute_allocated_amount(600_000_000, banks)
        assert n == 2
        assert amount == 300_000_000

    def test_clean_text_keeps_latin_letters(self):
        from processes.pdf_extraction.utils.text_processing import TextProcessor

        cleaned = TextProcessor().clean_text("Coöperatieve Crédit")
        assert "Coöperatieve" in cleaned
        assert "Crédit" in cleaned
