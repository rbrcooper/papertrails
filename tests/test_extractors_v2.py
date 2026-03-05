import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.extractor.extractors.date_extractor import DateExtractor
from src.extractor.extractors.currency_extractor import CurrencyExtractor
from src.extractor.extractors.coupon_extractor import CouponExtractor
from src.extractor.extractors.bank_extractor import BankExtractor

def test_extractors():
    print("Testing V2 Extractors...")
    
    # Sample text
    text = """
    FINAL TERMS
    
    Issue of EUR 500,000,000 3.500 per cent. Notes due 20 July 2028
    
    Issue Date: 20 July 2023
    Maturity Date: 20 July 2028
    
    Interest: 3.500 per cent. Fixed Rate
    
    Managers:
    Deutsche Bank AG, London Branch
    J.P. Morgan SE
    Société Générale
    
    The Notes have been issued in an aggregate nominal amount of EUR 500,000,000.
    """
    
    print("\n--- Date Extractor ---")
    date_ext = DateExtractor(debug_mode=True)
    dates = date_ext.extract(text)
    print(json.dumps(dates, indent=2))
    
    print("\n--- Currency Extractor ---")
    curr_ext = CurrencyExtractor(debug_mode=True)
    curr = curr_ext.extract(text)
    print(json.dumps(curr, indent=2))
    
    print("\n--- Coupon Extractor ---")
    coup_ext = CouponExtractor(debug_mode=True)
    coup = coup_ext.extract(text)
    print(json.dumps(coup, indent=2))
    
    print("\n--- Bank Extractor ---")
    # Disable AI for this quick test to avoid network calls/latency
    bank_ext = BankExtractor(debug_mode=True, use_ai=False) 
    banks = bank_ext.extract(text)
    print(json.dumps(banks, indent=2))
    
if __name__ == "__main__":
    test_extractors()
