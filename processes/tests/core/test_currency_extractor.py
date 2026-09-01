"""Focused tests for ISO-4217 currency extraction (not LEI / address trigrams)."""

from processes.pdf_extraction.extractors.currency_extractor import CurrencyExtractor
from processes.pdf_extraction.utils.pattern_registry import PatternRegistry


VIER_GAS_LIKE = """
FINAL TERMS Vier Gas Transport GmbH LEI: 529900AGED6PJE9AVL37 EUR 500,000,000 3.625 per cent. Notes due 2033
issued pursuant to the EUR 5,000,000,000 Debt Issuance Programme
RBC Capital Markets (Europe) GmbH Marienturm, Taunusanlage 9-10 60329 Frankfurt
from the Fiscal Agent
"""

ESB_FTWS = """
Specified Currency or Currencies: Euro (EUR)
Aggregate Nominal Amount: (a) Series: EUR500,000,000 (b) Tranche: EUR500,000,000
"""

LEI_COVER = (
    "Vier Gas Transport GmbH LEI: 529900AGED6PJE9AVL37 EUR 500,000,000 "
    "3.625 per cent. Notes due 2033"
)

TAUNUS_FROM = "RBC Capital Markets Marienturm, Taunusanlage 9-10 60329 Frankfurt from the Fiscal Agent"

GASUNIE_LIKE = """
EUR 7,500,000,000 Euro Medium Term Note Programme
Aggregate Nominal Amount: (i) Series: EUR 650,000,000 (ii) Tranche: EUR 650,000,000
"""

VEOLIA_LIKE = """
Euro 22,000,000,000 Euro Medium Term Note Programme
Tranche: €500,000,000
"""

VIER_GAS_PROGRAMME = """
FINAL TERMS Vier Gas Transport GmbH LEI: 529900AGED6PJE9AVL37 EUR 500,000,000 3.625 per cent. Notes due 2033
issued pursuant to the EUR 7,000,000,000 Debt Issuance Programme
"""

ENEL_LIKE = """
issued under the 35,000,000,000 Euro Medium Term Note Programme
Specified Currency or Currencies EUR
Aggregate Nominal Amount: (i) Series: 1,250,000,000 (ii) Tranche: 1,250,000,000
"""


def test_canonical_iso_rejects_age():
    ext = CurrencyExtractor()
    assert ext._canonical_iso("age") is None
    assert ext._canonical_iso("AGE") is None
    assert ext._canonical_iso("EUR") == "EUR"


def test_map_symbol_to_code_eur():
    ext = CurrencyExtractor()
    assert ext._map_symbol_to_code("EUR") == "EUR"


def test_currency_codes_are_bare_iso():
    codes = PatternRegistry.get_currency_patterns()["currency_codes"]
    assert "EUR" in codes
    assert "AGE" not in codes
    assert not any(c.startswith(r"\b") for c in codes)


def test_vier_gas_like_is_eur_500m_not_age():
    info = CurrencyExtractor().extract(VIER_GAS_LIKE)
    assert info["currency"].upper() == "EUR"
    assert info["currency"].lower() != "age"
    assert info["issue_size"] == "500000000"


def test_esb_ftws_snippet_eur_500m():
    info = CurrencyExtractor().extract(ESB_FTWS)
    assert info["currency"].upper() == "EUR"
    assert info["issue_size"] == "500000000"


def test_taunusanlage_from_does_not_yield_age():
    info = CurrencyExtractor().extract(TAUNUS_FROM)
    currency = info.get("currency")
    if currency:
        assert currency.lower() != "age"
        assert currency.upper() != "AGE"


def test_lei_cover_line_stays_eur():
    info = CurrencyExtractor().extract(LEI_COVER)
    assert info["currency"].upper() == "EUR"
    assert info["issue_size"] == "500000000"


def test_gasunie_like_tranche_not_programme_ceiling():
    info = CurrencyExtractor().extract(GASUNIE_LIKE)
    assert info["currency"].upper() == "EUR"
    assert info["issue_size"] == "650000000"
    assert info["programme_size"] == "7500000000"
    assert info["issue_size"] != info["programme_size"]


def test_veolia_like_tranche_not_programme_ceiling():
    info = CurrencyExtractor().extract(VEOLIA_LIKE)
    assert info["currency"].upper() == "EUR"
    assert info["issue_size"] == "500000000"
    assert info["programme_size"] == "22000000000"


def test_vier_gas_like_500m_not_5bn_or_7bn():
    info = CurrencyExtractor().extract(VIER_GAS_PROGRAMME)
    assert info["currency"].upper() == "EUR"
    assert info["issue_size"] == "500000000"
    assert info["issue_size"] not in ("5000000000", "7000000000")
    assert info["programme_size"] == "7000000000"


def test_enel_like_bare_tranche_not_programme_ceiling():
    info = CurrencyExtractor().extract(ENEL_LIKE)
    assert info["currency"].upper() == "EUR"
    assert info["issue_size"] == "1250000000"
    assert info["programme_size"] == "35000000000"
