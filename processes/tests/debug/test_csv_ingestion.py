"""Quick import + integration sanity check."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

errors = []
profile = None
fs = None

# Test 1: CompanyListHandler imports and loads
try:
    from processes.company_list_handler import CompanyListHandler
    h = CompanyListHandler('data/raw/Urgewald GOGEL 2025 V1.2 with identifiers.csv')
    companies = h.get_all_companies()
    assert len(companies) > 100, f"Expected >100 companies, got {len(companies)}"
    c0 = companies[0]
    assert 'lei' in c0, "Missing 'lei' key"
    assert 'isin_equity' in c0, "Missing 'isin_equity' key"
    assert 'isins_bonds' in c0, "Missing 'isins_bonds' key"
    print(f"PASS: CompanyListHandler loaded {len(companies)} companies with identifiers")
except Exception as e:
    errors.append(f"CompanyListHandler: {e}")
    print(f"FAIL: CompanyListHandler: {e}")

# Test 2: DatabaseHandler imports and loads bank maps
try:
    from processes.database_handler import DatabaseHandler
    db = DatabaseHandler(db_path=":memory:")
    assert len(db.bank_canonical_map) >= 20, f"Expected >=20 banks, got {len(db.bank_canonical_map)}"
    # Test normalization
    assert db._normalize_bank_name("jpmorgan") == "JPMorgan", f"Got: {db._normalize_bank_name('jpmorgan')}"
    assert db._normalize_bank_name("bnp") == "BNP Paribas", f"Got: {db._normalize_bank_name('bnp')}"
    print(f"PASS: DatabaseHandler loaded {len(db.bank_canonical_map)} bank mappings, normalization works")
except Exception as e:
    errors.append(f"DatabaseHandler: {e}")
    print(f"FAIL: DatabaseHandler: {e}")

# Test 3: ESMAScraper profile building with identifiers
try:
    from processes.esma_scraper import ESMAScraper

    class FakeDriverScraper(ESMAScraper):
        def __init__(self):
            self.logger = __import__('logging').getLogger('test')

    fs = FakeDriverScraper()
    # Call _build_company_profile directly
    profile = fs._build_company_profile("BP plc", company_data={
        'lei': 'TEST_LEI_123',
        'isin_equity': 'GB1234567890',
        'isins_bonds': ['XS111', 'XS222'],
        'isins_bonds_subsidiaries': ['XS333'],
    })
    assert profile['lei_codes'] == ['TEST_LEI_123'], f"LEI: {profile['lei_codes']}"
    assert 'GB1234567890' in profile['isins'], f"ISINs: {profile['isins']}"
    assert len(profile['isins']) == 4, f"Expected 4 ISINs, got {len(profile['isins'])}"
    print(f"PASS: Scraper profile has {len(profile['isins'])} ISINs and LEI")
except Exception as e:
    errors.append(f"ESMAScraper profile: {e}")
    print(f"FAIL: ESMAScraper profile: {e}")

# Test 4: Scoring with ISIN match
try:
    details = {'isin': 'GB1234567890', 'issuer_name': 'Something Else Ltd', 'doc_type': 'Final Terms', 'date': '01/01/2025'}
    score, parts = fs._compute_multi_signal_score(details, profile)
    assert score >= 0.9, f"ISIN match should give score >= 0.9, got {score}"
    assert parts['isin_match'] == 1.0, f"isin_match should be 1.0, got {parts['isin_match']}"
    print(f"PASS: ISIN match score = {score:.3f} (isin_match={parts['isin_match']})")
except Exception as e:
    errors.append(f"Scoring: {e}")
    print(f"FAIL: Scoring: {e}")

# Summary
print()
if errors:
    print(f"FAILED: {len(errors)} error(s)")
    for err in errors:
        print(f"  - {err}")
    sys.exit(1)
else:
    print("ALL 4 TESTS PASSED")
