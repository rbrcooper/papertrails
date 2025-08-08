"""
Consolidated PDF Extraction Test Suite
=====================================
This file consolidates all PDF extraction testing from multiple scattered test files:
- test_dates.py
- test_dates_in_pdfs.py  
- debug_date_extractor.py
- test_issue_size_extractor.py
- debug_currency_extractor.py
- test_bank_integration.py
- test_pdf_with_banks.py
- test_extractor.py
- test_pdf_extractor.py
- pdf_extraction/test_extractors.py

Provides comprehensive testing for all extractor components in one place.
"""

import sys
import os
import re
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add project root to sys.path to allow importing from processes
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from processes.pdf_extractor import PDFExtractor
from processes.pdf_extraction.extractors.date_extractor import DateExtractor
from processes.pdf_extraction.extractors.currency_extractor import CurrencyExtractor
from processes.pdf_extraction.extractors.coupon_extractor import CouponExtractor
from processes.pdf_extraction.extractors.bank_extractor import BankExtractor
from processes.pdf_extraction.utils.pattern_registry import PatternRegistry


class TestDateExtraction:
    """Consolidates all date extraction testing from multiple files."""
    
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
        self.logger = self._setup_logging()
        self.extractor = PDFExtractor(debug_mode=debug_mode)
        self.date_extractor = DateExtractor(debug_mode=debug_mode)
    
    def _setup_logging(self):
        """Configure logging."""
        level = logging.DEBUG if self.debug_mode else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        return logging.getLogger('TestDateExtraction')
    
    def test_basic_date_extraction(self):
        """Test date extraction with sample texts (from test_dates.py)."""
        sample_texts = [
            """
            Issue Date: 15/04/2022
            Maturity Date: 15/04/2027
            """,
            
            """
            Date of Issue: 15 April 2022
            Final Maturity: 15 April 2027
            """,
            
            """
            Issuance Date: 2022-04-15
            Redemption Date: 2027-04-15
            """,
            
            """
            Issue Date: 15th April, 2022
            Maturity Date: 15th April, 2027
            """
        ]
        
        self.logger.info("===== Basic Date Extraction Test =====")
        for i, text in enumerate(sample_texts, 1):
            self.logger.info(f"\nTest {i}:")
            self.logger.info(f"Input Text:\n{text}")
            
            date_info = self.date_extractor.extract(text)
            self.logger.info(f"Extracted Dates: {date_info}")
    
    def test_dates_in_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """Test date extraction from a real PDF file (from test_dates_in_pdfs.py)."""
        self.logger.info(f"Testing date extraction in: {pdf_path}")
        
        # Extract text from PDF
        self.logger.info("Extracting text from PDF...")
        text = self.extractor.extract_text(pdf_path)
        if not text:
            self.logger.error("Failed to extract text from PDF")
            return {'success': False, 'error': 'Failed to extract text'}
        
        self.logger.info(f"Successfully extracted {len(text)} characters")
        
        # Manual search for dates
        date_lines, unique_dates = self._manual_date_search(text)
        
        # Extract dates using the extractor
        self.logger.info("Extracting dates using the extractor...")
        date_info = self.date_extractor.extract(text)
        
        # Check if any dates were found
        success = bool(date_info.get('issue_date') or date_info.get('maturity_date'))
        
        result = {
            'success': success,
            'date_info': date_info,
            'date_lines': date_lines,
            'unique_dates': unique_dates,
            'text_length': len(text)
        }
        
        self.logger.info(f"Extraction result: {result}")
        return result
    
    def _manual_date_search(self, text: str) -> tuple[List[str], List[str]]:
        """Manually search for date-like patterns in the text."""
        self.logger.info("Performing manual date search...")
        
        # Define common date-related keywords
        date_keywords = [
            "issue date", "dated", "maturity date", "redemption date", 
            "final maturity", "issuance date", "date of issue", "settlement date",
            "trade date", "effective date", "termination date", "value date",
            "issue", "issued on", "will be issued on", "to be issued on"
        ]
        
        # Search for lines containing these keywords
        date_lines = []
        lines = text.splitlines()
        for line in lines:
            line = line.strip().lower()
            if any(keyword in line for keyword in date_keywords):
                date_lines.append(line)
        
        # Look for date patterns in the text
        date_patterns = [
            r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}',  # DD/MM/YYYY, DD-MM-YYYY
            r'\d{4}[-/]\d{2}[-/]\d{2}',        # YYYY/MM/DD, YYYY-MM-DD
            r'\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}',  # DD Month YYYY
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}'  # Month DD, YYYY
        ]
        
        all_dates = []
        for pattern in date_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                all_dates.append(match.group(0))
        
        # Limit to first 20 unique dates
        unique_dates = sorted(set(all_dates))[:20]
        
        return date_lines, unique_dates
    
    def debug_date_extraction(self, pdf_path: str):
        """Debug date extraction with detailed pattern analysis (from debug_date_extractor.py)."""
        self.logger.info(f"Debugging date extraction for: {pdf_path}")
        
        # Extract the raw text
        text = self.extractor.extract_text(pdf_path)
        self.logger.info(f"Raw text length: {len(text)} characters")
        
        # Get date patterns from registry
        patterns = PatternRegistry.get_date_patterns()
        
        # Test each pattern against the text
        self.logger.info("\nTesting issue date patterns:")
        for i, pattern in enumerate(patterns['issue_date']):
            matches = re.finditer(pattern, text, re.IGNORECASE)
            match_list = list(matches)
            if match_list:
                self.logger.info(f"  Pattern {i+1}: {len(match_list)} matches")
                for j, match in enumerate(match_list[:3]):  # Show max 3 matches per pattern
                    date_str = match.group(1).strip()
                    context = text[max(0, match.start() - 30):min(len(text), match.end() + 30)]
                    self.logger.info(f"    Match {j+1}: '{date_str}' in context: '...{context}...'")
            else:
                self.logger.info(f"  Pattern {i+1}: No matches")
        
        self.logger.info("\nTesting maturity date patterns:")
        for i, pattern in enumerate(patterns['maturity_date']):
            matches = re.finditer(pattern, text, re.IGNORECASE)
            match_list = list(matches)
            if match_list:
                self.logger.info(f"  Pattern {i+1}: {len(match_list)} matches")
                for j, match in enumerate(match_list[:3]):  # Show max 3 matches per pattern
                    date_str = match.group(1).strip()
                    context = text[max(0, match.start() - 30):min(len(text), match.end() + 30)]
                    self.logger.info(f"    Match {j+1}: '{date_str}' in context: '...{context}...'")
            else:
                self.logger.info(f"  Pattern {i+1}: No matches")
        
        # Try direct extraction with DateExtractor
        date_info = self.date_extractor.extract(text)
        
        self.logger.info(f"\nDateExtractor results:")
        self.logger.info(f"  Issue date: {date_info.get('issue_date')}")
        self.logger.info(f"  Maturity date: {date_info.get('maturity_date')}")


class TestCurrencyExtraction:
    """Consolidates all currency and issue size extraction testing."""
    
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
        self.logger = self._setup_logging()
        self.extractor = PDFExtractor(debug_mode=debug_mode)
        self.currency_extractor = CurrencyExtractor(debug_mode=debug_mode)
    
    def _setup_logging(self):
        """Configure logging."""
        level = logging.DEBUG if self.debug_mode else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        return logging.getLogger('TestCurrencyExtraction')
    
    def test_issue_size_extraction(self, pdf_path: str) -> Dict[str, Any]:
        """Test issue size extraction from PDF (from test_issue_size_extractor.py)."""
        self.logger.info(f"Testing issue size extraction in: {pdf_path}")
        
        # Extract text from PDF
        text = self.extractor.extract_text(pdf_path)
        if not text:
            self.logger.error("Failed to extract text from PDF")
            return {'success': False, 'error': 'Failed to extract text'}
        
        # Extract currency information
        currency_info = self.currency_extractor.extract(text)
        
        result = {
            'success': bool(currency_info.get('currency') or currency_info.get('issue_size')),
            'currency_info': currency_info,
            'text_length': len(text)
        }
        
        self.logger.info(f"Currency extraction result: {result}")
        return result
    
    def debug_currency_extraction(self, pdf_path: str):
        """Debug currency extraction with detailed pattern analysis (from debug_currency_extractor.py)."""
        self.logger.info(f"Debugging currency extraction for: {pdf_path}")
        
        # Extract the raw text
        text = self.extractor.extract_text(pdf_path)
        self.logger.info(f"Raw text length: {len(text)} characters")
        
        # Get currency patterns from registry
        patterns = PatternRegistry.get_currency_patterns()
        
        # Test each pattern against the text
        self.logger.info("\nTesting currency patterns:")
        for i, pattern in enumerate(patterns['currency']):
            matches = re.finditer(pattern, text, re.IGNORECASE)
            match_list = list(matches)
            if match_list:
                self.logger.info(f"  Pattern {i+1}: {len(match_list)} matches")
                for j, match in enumerate(match_list[:3]):  # Show max 3 matches per pattern
                    currency_str = match.group(1).strip()
                    context = text[max(0, match.start() - 30):min(len(text), match.end() + 30)]
                    self.logger.info(f"    Match {j+1}: '{currency_str}' in context: '...{context}...'")
            else:
                self.logger.info(f"  Pattern {i+1}: No matches")
        
        self.logger.info("\nTesting issue size patterns:")
        for i, pattern in enumerate(patterns['issue_size']):
            matches = re.finditer(pattern, text, re.IGNORECASE)
            match_list = list(matches)
            if match_list:
                self.logger.info(f"  Pattern {i+1}: {len(match_list)} matches")
                for j, match in enumerate(match_list[:3]):  # Show max 3 matches per pattern
                    size_str = match.group(1).strip()
                    context = text[max(0, match.start() - 30):min(len(text), match.end() + 30)]
                    self.logger.info(f"    Match {j+1}: '{size_str}' in context: '...{context}...'")
            else:
                self.logger.info(f"  Pattern {i+1}: No matches")
        
        # Try direct extraction with CurrencyExtractor
        currency_info = self.currency_extractor.extract(text)
        
        self.logger.info(f"\nCurrencyExtractor results:")
        self.logger.info(f"  Currency: {currency_info.get('currency')}")
        self.logger.info(f"  Issue size: {currency_info.get('issue_size')}")
        self.logger.info(f"  Issue size range: {currency_info.get('issue_size_range')}")


class TestBankExtraction:
    """Consolidates all bank extraction testing."""
    
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
        self.logger = self._setup_logging()
        self.extractor = PDFExtractor(debug_mode=debug_mode)
        self.bank_extractor = BankExtractor(debug_mode=debug_mode)
    
    def _setup_logging(self):
        """Configure logging."""
        level = logging.DEBUG if self.debug_mode else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        return logging.getLogger('TestBankExtraction')
    
    def test_bank_extraction(self, pdf_path: str) -> Dict[str, Any]:
        """Test bank extraction from PDF (from test_bank_integration.py and test_pdf_with_banks.py)."""
        self.logger.info(f"Testing bank extraction in: {pdf_path}")
        
        # Extract text from PDF
        text = self.extractor.extract_text(pdf_path)
        if not text:
            self.logger.error("Failed to extract text from PDF")
            return {'success': False, 'error': 'Failed to extract text'}
        
        # Extract bank information
        bank_info = self.bank_extractor.extract(text)
        
        result = {
            'success': bool(bank_info.get('extracted_banks')),
            'bank_info': bank_info,
            'text_length': len(text)
        }
        
        self.logger.info(f"Bank extraction result: {result}")
        return result
    
    def test_extraction_format(self, extraction_result: Dict) -> bool:
        """Test that bank extraction returns the expected format."""
        self.logger.info("Testing bank extraction format...")
        
        required_fields = ['extracted_banks', 'bank_sections']
        for field in required_fields:
            if field not in extraction_result:
                self.logger.error(f"Missing required field: {field}")
                return False
        
        if not isinstance(extraction_result['extracted_banks'], list):
            self.logger.error("extracted_banks should be a list")
            return False
        
        self.logger.info("✅ Bank extraction format is valid")
        return True


class TestCouponExtraction:
    """Consolidates all coupon extraction testing."""
    
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
        self.logger = self._setup_logging()
        self.extractor = PDFExtractor(debug_mode=debug_mode)
        self.coupon_extractor = CouponExtractor(debug_mode=debug_mode)
    
    def _setup_logging(self):
        """Configure logging."""
        level = logging.DEBUG if self.debug_mode else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        return logging.getLogger('TestCouponExtraction')
    
    def test_coupon_extraction(self, pdf_path: str) -> Dict[str, Any]:
        """Test coupon extraction from PDF."""
        self.logger.info(f"Testing coupon extraction in: {pdf_path}")
        
        # Extract text from PDF
        text = self.extractor.extract_text(pdf_path)
        if not text:
            self.logger.error("Failed to extract text from PDF")
            return {'success': False, 'error': 'Failed to extract text'}
        
        # Extract coupon information
        coupon_info = self.coupon_extractor.extract(text)
        
        result = {
            'success': bool(coupon_info.get('coupon_rate') or coupon_info.get('coupon_type')),
            'coupon_info': coupon_info,
            'text_length': len(text)
        }
        
        self.logger.info(f"Coupon extraction result: {result}")
        return result


class TestPDFExtractionIntegration:
    """Integration tests for the complete PDF extraction pipeline."""
    
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
        self.logger = self._setup_logging()
        self.extractor = PDFExtractor(debug_mode=debug_mode)
    
    def _setup_logging(self):
        """Configure logging."""
        level = logging.DEBUG if self.debug_mode else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        return logging.getLogger('TestPDFExtractionIntegration')
    
    def test_complete_extraction(self, pdf_path: str) -> Dict[str, Any]:
        """Test complete PDF extraction pipeline."""
        self.logger.info(f"Testing complete extraction for: {pdf_path}")
        
        try:
            # Process the PDF
            result = self.extractor.process_single_pdf(pdf_path)
            
            if result is None:
                return {'success': False, 'error': 'Extraction returned None'}
            
            # Validate the result structure
            required_fields = ['filename', 'file_path', 'metadata', 'validation_flags']
            for field in required_fields:
                if field not in result:
                    self.logger.error(f"Missing required field: {field}")
                    return {'success': False, 'error': f'Missing field: {field}'}
            
            # Check if any useful data was extracted
            metadata = result.get('metadata', {})
            useful_fields = ['issue_date', 'maturity_date', 'currency', 'issue_size', 'coupon_rate']
            extracted_fields = [field for field in useful_fields if metadata.get(field)]
            
            success = len(extracted_fields) > 0
            
            result_summary = {
                'success': success,
                'extracted_fields': extracted_fields,
                'validation_flags': result.get('validation_flags', []),
                'has_banks': bool(result.get('extracted_banks')),
                'filename': result.get('filename')
            }
            
            self.logger.info(f"Complete extraction result: {result_summary}")
            return result_summary
            
        except Exception as e:
            self.logger.error(f"Error during complete extraction: {str(e)}")
            return {'success': False, 'error': str(e)}


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="Consolidated PDF Extraction Test Suite")
    parser.add_argument("--pdf-path", type=str, help="Path to PDF file to test")
    parser.add_argument("--test-type", choices=['date', 'currency', 'bank', 'coupon', 'all'], 
                       default='all', help="Type of test to run")
    parser.add_argument("--debug", action='store_true', help="Enable debug mode")
    args = parser.parse_args()
    
    if args.pdf_path and not os.path.exists(args.pdf_path):
        print(f"Error: PDF file not found: {args.pdf_path}")
        return
    
    # Initialize test classes
    date_tester = TestDateExtraction(debug_mode=args.debug)
    currency_tester = TestCurrencyExtraction(debug_mode=args.debug)
    bank_tester = TestBankExtraction(debug_mode=args.debug)
    coupon_tester = TestCouponExtraction(debug_mode=args.debug)
    integration_tester = TestPDFExtractionIntegration(debug_mode=args.debug)
    
    # Run tests based on type
    if args.test_type == 'date' or args.test_type == 'all':
        print("\n" + "="*60)
        print("RUNNING DATE EXTRACTION TESTS")
        print("="*60)
        
        # Run basic tests
        date_tester.test_basic_date_extraction()
        
        # Run PDF tests if path provided
        if args.pdf_path:
            date_tester.test_dates_in_pdf(args.pdf_path)
            date_tester.debug_date_extraction(args.pdf_path)
    
    if args.test_type == 'currency' or args.test_type == 'all':
        print("\n" + "="*60)
        print("RUNNING CURRENCY EXTRACTION TESTS")
        print("="*60)
        
        if args.pdf_path:
            currency_tester.test_issue_size_extraction(args.pdf_path)
            currency_tester.debug_currency_extraction(args.pdf_path)
    
    if args.test_type == 'bank' or args.test_type == 'all':
        print("\n" + "="*60)
        print("RUNNING BANK EXTRACTION TESTS")
        print("="*60)
        
        if args.pdf_path:
            bank_result = bank_tester.test_bank_extraction(args.pdf_path)
            if bank_result.get('success'):
                bank_tester.test_extraction_format(bank_result['bank_info'])
    
    if args.test_type == 'coupon' or args.test_type == 'all':
        print("\n" + "="*60)
        print("RUNNING COUPON EXTRACTION TESTS")
        print("="*60)
        
        if args.pdf_path:
            coupon_tester.test_coupon_extraction(args.pdf_path)
    
    if args.test_type == 'all':
        print("\n" + "="*60)
        print("RUNNING INTEGRATION TESTS")
        print("="*60)
        
        if args.pdf_path:
            integration_tester.test_complete_extraction(args.pdf_path)


if __name__ == "__main__":
    main() 