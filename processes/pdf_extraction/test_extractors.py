#!/usr/bin/env python3
"""
Test script for enhanced extractors
"""

import os
import sys
import logging
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pdf_extraction.extractors.date_extractor import DateExtractor
from pdf_extraction.extractors.currency_extractor import CurrencyExtractor
from pdf_extraction.extractors.coupon_extractor import CouponExtractor
from pdf_extraction.core import ExtractionEngine

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def test_date_extractor():
    """Test the enhanced date extractor with various formats"""
    date_extractor = DateExtractor()
    
    test_cases = [
        # Issue dates
        "Issue Date: 15 January 2023",
        "Issue Date: 15.01.2023",
        "Issue Date: 2023-01-15",
        "Issue Date: 15/01/2023",
        "Date of Issue: January 15, 2023",
        "Settlement Date: 15th January, 2023",
        "Issue Date: on or about 15 January 2023",
        "Closing Date: 15.01.2023",
        "These Final Terms are dated 15 January 2023",
        
        # Maturity dates
        "Maturity Date: 15 January 2030",
        "Maturity Date: 15.01.2030",
        "Maturity Date: 2030-01-15",
        "Will mature on 15 January 2030",
        "Notes due 15 January 2030",
        "Scheduled maturity on 15 January 2030",
        "Notes maturing in 2030",
        "Term: maturing 15 January 2030",
        "The Notes shall mature on 15 January 2030"
    ]
    
    print("\n===== DATE EXTRACTOR TEST =====")
    for idx, test_case in enumerate(test_cases):
        print(f"\nTest {idx+1}: {test_case}")
        result = date_extractor.extract(test_case)
        print(f"Result: {json.dumps(result, indent=2)}")

def test_currency_extractor():
    """Test the enhanced currency extractor with various formats"""
    currency_extractor = CurrencyExtractor()
    
    test_cases = [
        # Standard formats
        "Aggregate Nominal Amount: EUR 500,000,000",
        "Issue Size: USD 1,000,000,000",
        "Principal Amount: $500 million",
        "Issue Size: €1.5 billion",
        
        # European formats
        "Aggregate Nominal Amount: EUR 500.000.000",
        "Issue Size: EUR 1.000.000.000,50",
        
        # Special cases
        "Up to EUR 750,000,000",
        "Between EUR 500,000,000 and EUR 750,000,000",
        "Maximum issuance amount: $1bn",
        "Programme Size: €5,000m",
        "Approximately EUR 650 million",
        "Issue of USD 500,000,000 2.5% Notes due 2030"
    ]
    
    print("\n===== CURRENCY EXTRACTOR TEST =====")
    for idx, test_case in enumerate(test_cases):
        print(f"\nTest {idx+1}: {test_case}")
        result = currency_extractor.extract(test_case)
        print(f"Result: {json.dumps(result, indent=2)}")

def test_coupon_extractor():
    """Test the enhanced coupon extractor with various formats"""
    coupon_extractor = CouponExtractor()
    
    test_cases = [
        # Fixed rate cases
        "Interest Rate: 3.5%",
        "Coupon Rate: 4.25 per cent",
        "Fixed Rate: 2.75%",
        "Notes bearing a coupon of 3.125%",
        "Coupon: 2.5%",
        
        # Floating rate cases
        "Floating Rate: 3-month EURIBOR + 0.5%",
        "Interest Rate: SOFR + 45 basis points",
        "Variable Rate: LIBOR + 0.75%",
        "Interest calculated by reference to 6m SONIA + 0.35%",
        "Floating rate notes with interest based on EURIBOR",
        
        # Step-up/down cases
        "Step-up Coupon: Initial rate of 3.5% increasing to 4.0% after 5 years",
        "Interest rate increases by 0.25% every year starting from 2.5%",
        "Step-down notes with rates decreasing from 4.0% to 3.5% after 3 years",
        "3.0% for the first 3 years, 3.5% thereafter",
        
        # Zero coupon
        "Zero Coupon Notes",
        "Notes issued at a discount with no periodic interest"
    ]
    
    print("\n===== COUPON EXTRACTOR TEST =====")
    for idx, test_case in enumerate(test_cases):
        print(f"\nTest {idx+1}: {test_case}")
        result = coupon_extractor.extract(test_case)
        print(f"Result: {json.dumps(result, indent=2)}")

def main():
    """Run all tests"""
    test_date_extractor()
    test_currency_extractor()
    test_coupon_extractor()
    
    # Test on sample PDF if available
    data_dir = Path(__file__).parent.parent.parent / "data" / "downloads"
    if data_dir.exists():
        pdf_files = list(data_dir.glob('**/*.pdf'))
        if pdf_files:
            sample_pdf = pdf_files[0]
            print(f"\n\n===== TESTING ON SAMPLE PDF: {sample_pdf} =====")
            engine = ExtractionEngine(use_ocr=False)
            results = engine.process_single_pdf(str(sample_pdf))
            print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main() 