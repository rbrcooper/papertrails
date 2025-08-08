"""
Consolidated Debug Extraction Suite
==================================
This file consolidates all debug functionality from multiple scattered debug files:
- debug_all_extractors.py (437 lines)
- debug_extractions_visualizer.py (387 lines)
- debug_extraction_report.py (659 lines)
- batch_debug_extractors.py (230 lines)

Provides unified debugging interface for all extraction components.
"""

import sys
import re
import os
import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from collections import Counter
import logging

# Optional dependencies for enhanced functionality
try:
    from colorama import Fore, Style, init
    init()
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False
    # Fallback color constants
    class Fore:
        GREEN = RED = YELLOW = BLUE = CYAN = MAGENTA = WHITE = ''
    class Style:
        RESET_ALL = BRIGHT = DIM = ''

try:
    import matplotlib.pyplot as plt
    import pandas as pd
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# Add project root to sys.path to allow importing from processes
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from processes.pdf_extraction.core import ExtractionEngine
from processes.pdf_extraction.extractors.date_extractor import DateExtractor
from processes.pdf_extraction.extractors.currency_extractor import CurrencyExtractor
from processes.pdf_extraction.extractors.coupon_extractor import CouponExtractor
from processes.pdf_extraction.extractors.bank_extractor import BankExtractor
from processes.pdf_extraction.utils.pattern_registry import PatternRegistry
from processes.pdf_extractor import PDFExtractor


class ExtractionDebugger:
    """Unified debugging interface for all extraction components."""
    
    def __init__(self, debug_mode=True, quiet=False):
        self.debug_mode = debug_mode
        self.quiet = quiet
        self.logger = self._setup_logging()
        self.extractor = PDFExtractor(debug_mode=debug_mode)
        
        # Initialize individual extractors
        self.date_extractor = DateExtractor(debug_mode=debug_mode)
        self.currency_extractor = CurrencyExtractor(debug_mode=debug_mode)
        self.coupon_extractor = CouponExtractor(debug_mode=debug_mode)
        self.bank_extractor = BankExtractor(debug_mode=debug_mode)
    
    def _setup_logging(self):
        """Configure logging."""
        level = logging.DEBUG if self.debug_mode else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        return logging.getLogger('ExtractionDebugger')
    
    def _print(self, message: str, color: str = None):
        """Print message with optional color if not in quiet mode."""
        if not self.quiet:
            if color and HAS_COLORAMA:
                print(f"{color}{message}{Style.RESET_ALL}")
            else:
                print(message)
    
    def _test_pattern(self, pattern: str, text: str) -> List[re.Match]:
        """Test a regex pattern against text and return all matches."""
        try:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            return matches
        except Exception as e:
            self._print(f"Error testing pattern {pattern}: {e}", Fore.RED)
            return []
    
    def _show_pattern_matches(self, pattern: str, text: str, pattern_index: int = None, 
                             pattern_type: str = None) -> bool:
        """Show detailed information about pattern matches."""
        matches = self._test_pattern(pattern, text)
        
        pattern_info = f"Pattern {pattern_index}: " if pattern_index else "Pattern: "
        if pattern_type:
            pattern_info = f"{pattern_type} {pattern_info}"
        
        if matches:
            self._print(f"{pattern_info}{len(matches)} matches", Fore.GREEN)
            for j, match in enumerate(matches[:3]):  # Show max 3 matches per pattern
                try:
                    if match.lastindex is not None and match.lastindex > 0:
                        group_val = match.group(1)
                        group_str = group_val.strip() if group_val is not None else match.group(0)
                    else:
                        group_str = match.group(0)
                    
                    # Get context
                    start = max(0, match.start() - 30)
                    end = min(len(text), match.end() + 30)
                    context = text[start:end].replace('\n', ' ')
                    
                    self._print(f"  Match {j+1}: '{group_str}' in context:")
                    self._print(f"    ...{context}...\n")
                except (IndexError, AttributeError):
                    self._print(f"  Match {j+1}: Error accessing match groups")
            return True
        else:
            self._print(f"{pattern_info}No matches", Fore.RED)
            return False
    
    def debug_single_pdf(self, pdf_path: str, extractor_type: str = None) -> Dict[str, Any]:
        """
        Debug extraction for a single PDF file.
        Replaces debug_all_extractors.py functionality.
        
        Args:
            pdf_path: Path to PDF file
            extractor_type: Specific extractor to debug ('date', 'currency', 'coupon', 'bank', or None for all)
        """
        start_time = time.time()
        
        self._print(f"\n{'='*80}")
        self._print(f"Processing PDF: {os.path.basename(pdf_path)}")
        self._print(f"{'='*80}")
        
        # Extract text
        text = self.extractor.extract_text(pdf_path)
        if not text:
            self.logger.error("Failed to extract text from PDF")
            return {'success': False, 'error': 'Text extraction failed'}
        
        self._print(f"Successfully extracted {len(text)} characters")
        
        result = {
            'success': True,
            'file_path': pdf_path,
            'text_length': len(text),
            'extraction_time': 0,
            'debug_results': {}
        }
        
        # Debug different extractors based on type
        if extractor_type is None or extractor_type == 'date':
            result['debug_results']['date'] = self._debug_date_extraction(text)
        
        if extractor_type is None or extractor_type == 'currency':
            result['debug_results']['currency'] = self._debug_currency_extraction(text)
        
        if extractor_type is None or extractor_type == 'coupon':
            result['debug_results']['coupon'] = self._debug_coupon_extraction(text)
        
        if extractor_type is None or extractor_type == 'bank':
            result['debug_results']['bank'] = self._debug_bank_extraction(text)
        
        # Generate improvement suggestions
        suggestions = self._generate_improvement_suggestions(text, result['debug_results'])
        result['improvement_suggestions'] = suggestions
        
        # Calculate overall confidence
        confidence = self._calculate_extraction_confidence(result['debug_results'])
        result['extraction_confidence'] = confidence
        
        result['extraction_time'] = time.time() - start_time
        
        self._print_extraction_summary(result)
        
        return result
    
    def _debug_date_extraction(self, text: str) -> Dict[str, Any]:
        """Debug date extraction from text."""
        self._print("\n===== DEBUGGING DATE EXTRACTION =====\n")
        
        # Get date patterns from registry
        issue_date_patterns = PatternRegistry.get_date_patterns()["issue_date"]
        maturity_date_patterns = PatternRegistry.get_date_patterns()["maturity_date"]
        
        pattern_stats = {"issue_date": [], "maturity_date": []}
        
        # Test each issue date pattern
        self._print("Testing issue date patterns:")
        any_issue_date_matches = False
        for i, pattern in enumerate(issue_date_patterns):
            has_matches = self._show_pattern_matches(pattern, text, i+1, "Issue date")
            if has_matches:
                any_issue_date_matches = True
                pattern_stats["issue_date"].append(i+1)
        
        if not any_issue_date_matches:
            self._print("No issue date patterns matched.", Fore.RED)
        
        # Test each maturity date pattern
        self._print("\nTesting maturity date patterns:")
        any_maturity_date_matches = False
        for i, pattern in enumerate(maturity_date_patterns):
            has_matches = self._show_pattern_matches(pattern, text, i+1, "Maturity date")
            if has_matches:
                any_maturity_date_matches = True
                pattern_stats["maturity_date"].append(i+1)
        
        if not any_maturity_date_matches:
            self._print("No maturity date patterns matched.", Fore.RED)
        
        # Extract dates using the extractor
        date_info = self.date_extractor.extract(text)
        
        self._print(f"\nDateExtractor results:")
        self._print(f"  issue_date: {date_info.get('issue_date')}")
        self._print(f"  maturity_date: {date_info.get('maturity_date')}")
        
        return {
            'pattern_stats': pattern_stats,
            'extraction_result': date_info,
            'has_issue_date': any_issue_date_matches,
            'has_maturity_date': any_maturity_date_matches
        }
    
    def _debug_currency_extraction(self, text: str) -> Dict[str, Any]:
        """Debug currency extraction from text."""
        self._print("\n===== DEBUGGING CURRENCY EXTRACTION =====\n")
        
        # Get currency patterns from registry
        currency_patterns = PatternRegistry.get_currency_patterns()["currency"]
        issue_size_patterns = PatternRegistry.get_currency_patterns()["issue_size"]
        
        pattern_stats = {"currency": [], "issue_size": []}
        
        # Test each currency pattern
        self._print("Testing currency patterns:")
        any_currency_matches = False
        for i, pattern in enumerate(currency_patterns):
            has_matches = self._show_pattern_matches(pattern, text, i+1, "Currency")
            if has_matches:
                any_currency_matches = True
                pattern_stats["currency"].append(i+1)
        
        # Test each issue size pattern
        self._print("\nTesting issue size patterns:")
        any_issue_size_matches = False
        for i, pattern in enumerate(issue_size_patterns):
            has_matches = self._show_pattern_matches(pattern, text, i+1, "Issue size")
            if has_matches:
                any_issue_size_matches = True
                pattern_stats["issue_size"].append(i+1)
        
        # Extract currency using the extractor
        currency_info = self.currency_extractor.extract(text)
        
        self._print(f"\nCurrencyExtractor results:")
        self._print(f"  currency: {currency_info.get('currency')}")
        self._print(f"  issue_size: {currency_info.get('issue_size')}")
        self._print(f"  issue_size_range: {currency_info.get('issue_size_range')}")
        
        return {
            'pattern_stats': pattern_stats,
            'extraction_result': currency_info,
            'has_currency': any_currency_matches,
            'has_issue_size': any_issue_size_matches
        }
    
    def _debug_coupon_extraction(self, text: str) -> Dict[str, Any]:
        """Debug coupon extraction from text."""
        self._print("\n===== DEBUGGING COUPON EXTRACTION =====\n")
        
        # Get coupon patterns from registry
        coupon_patterns = PatternRegistry.get_coupon_patterns()["coupon_rate"]
        
        pattern_stats = {"coupon_rate": []}
        
        # Test each coupon pattern
        self._print("Testing coupon rate patterns:")
        any_coupon_matches = False
        for i, pattern in enumerate(coupon_patterns):
            has_matches = self._show_pattern_matches(pattern, text, i+1, "Coupon rate")
            if has_matches:
                any_coupon_matches = True
                pattern_stats["coupon_rate"].append(i+1)
        
        # Extract coupon using the extractor
        coupon_info = self.coupon_extractor.extract(text)
        
        self._print(f"\nCouponExtractor results:")
        self._print(f"  coupon_rate: {coupon_info.get('coupon_rate')}")
        self._print(f"  coupon_type: {coupon_info.get('coupon_type')}")
        self._print(f"  reference_rate: {coupon_info.get('reference_rate')}")
        
        return {
            'pattern_stats': pattern_stats,
            'extraction_result': coupon_info,
            'has_coupon': any_coupon_matches
        }
    
    def _debug_bank_extraction(self, text: str) -> Dict[str, Any]:
        """Debug bank extraction from text."""
        self._print("\n===== DEBUGGING BANK EXTRACTION =====\n")
        
        # Extract banks using the extractor
        bank_info = self.bank_extractor.extract(text)
        
        extracted_banks = bank_info.get('extracted_banks', [])
        bank_sections = bank_info.get('bank_sections', {})
        
        self._print(f"BankExtractor results:")
        self._print(f"  extracted_banks: {len(extracted_banks)} banks found")
        
        for i, bank in enumerate(extracted_banks[:5]):  # Show max 5 banks
            self._print(f"    Bank {i+1}: {bank.get('raw_name')} -> {bank.get('standard_name')}")
            self._print(f"      Role: {bank.get('role', 'unknown')}, Confidence: {bank.get('confidence', 0.0)}")
        
        self._print(f"  bank_sections: {len(bank_sections)} sections found")
        for section_name, section_content in list(bank_sections.items())[:3]:  # Show max 3 sections
            self._print(f"    Section '{section_name}': {len(section_content)} characters")
        
        return {
            'extraction_result': bank_info,
            'has_banks': len(extracted_banks) > 0,
            'bank_count': len(extracted_banks),
            'section_count': len(bank_sections)
        }
    
    def _generate_improvement_suggestions(self, text: str, debug_results: Dict) -> List[str]:
        """Generate suggestions for improving extraction patterns."""
        suggestions = []
        
        # Date suggestions
        if 'date' in debug_results:
            date_result = debug_results['date']
            if not date_result.get('has_issue_date'):
                # Look for potential date patterns in text
                date_patterns = [
                    r'\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}',
                    r'\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{2,4}',
                    r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{2,4}'
                ]
                
                for pattern in date_patterns:
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        suggestions.append(f"Add date pattern to match format like: {match.group(0)}")
                        break  # Only suggest one example per pattern
        
        # Currency suggestions
        if 'currency' in debug_results:
            currency_result = debug_results['currency']
            if not currency_result.get('has_currency'):
                # Look for currency mentions
                currency_patterns = [r'\b(USD|EUR|GBP|JPY|CHF|CAD|AUD)\b', r'\$|\€|\£|\¥']
                for pattern in currency_patterns:
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        suggestions.append(f"Add currency pattern to detect '{match.group(0)}' mentions")
                        break
        
        # Remove duplicates and limit suggestions
        suggestions = list(set(suggestions))[:10]
        return suggestions
    
    def _calculate_extraction_confidence(self, debug_results: Dict) -> str:
        """Calculate overall extraction confidence level."""
        score = 0
        total = 0
        
        for extractor_type, result in debug_results.items():
            if extractor_type == 'date':
                total += 2
                if result.get('has_issue_date'): score += 1
                if result.get('has_maturity_date'): score += 1
            elif extractor_type == 'currency':
                total += 2
                if result.get('has_currency'): score += 1
                if result.get('has_issue_size'): score += 1
            elif extractor_type == 'coupon':
                total += 1
                if result.get('has_coupon'): score += 1
            elif extractor_type == 'bank':
                total += 1
                if result.get('has_banks'): score += 1
        
        if total == 0:
            return "UNKNOWN"
        
        confidence_ratio = score / total
        if confidence_ratio >= 0.8:
            return "HIGH"
        elif confidence_ratio >= 0.5:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _print_extraction_summary(self, result: Dict):
        """Print extraction summary."""
        self._print(f"\n===== EXTRACTION SUMMARY =====")
        self._print(f"File: {os.path.basename(result['file_path'])}")
        self._print(f"Extraction confidence: {result['extraction_confidence']}")
        self._print(f"Extraction time: {result['extraction_time']:.2f} seconds")
        
        # Count successful extractions
        successful_fields = 0
        total_fields = 0
        
        for extractor_type, debug_result in result['debug_results'].items():
            extraction_result = debug_result.get('extraction_result', {})
            if extractor_type == 'date':
                total_fields += 2
                if extraction_result.get('issue_date'): successful_fields += 1
                if extraction_result.get('maturity_date'): successful_fields += 1
            elif extractor_type == 'currency':
                total_fields += 2
                if extraction_result.get('currency'): successful_fields += 1
                if extraction_result.get('issue_size'): successful_fields += 1
            elif extractor_type == 'coupon':
                total_fields += 1
                if extraction_result.get('coupon_rate'): successful_fields += 1
            elif extractor_type == 'bank':
                total_fields += 1
                if extraction_result.get('extracted_banks'): successful_fields += 1
        
        self._print(f"Successfully extracted fields: {successful_fields}/{total_fields}")
        
        # Print improvement suggestions
        if result.get('improvement_suggestions'):
            self._print(f"\n===== IMPROVEMENT SUGGESTIONS =====")
            for i, suggestion in enumerate(result['improvement_suggestions'], 1):
                self._print(f"{i}. {suggestion}")
    
    def batch_debug(self, pdf_dir: str, output_dir: str = "debug_results", 
                   limit: int = None, pattern: str = "*.pdf") -> Dict[str, Any]:
        """
        Process multiple PDFs and generate aggregated statistics.
        Replaces batch_debug_extractors.py functionality.
        """
        pdf_dir = Path(pdf_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Find PDF files
        pdf_files = list(pdf_dir.glob(pattern))
        if limit:
            pdf_files = pdf_files[:limit]
        
        self._print(f"Found {len(pdf_files)} PDF files to process")
        
        results = []
        stats = {
            'total_files': len(pdf_files),
            'successful_extractions': 0,
            'failed_extractions': 0,
            'confidence_levels': Counter(),
            'field_success_rates': {
                'issue_date': 0,
                'maturity_date': 0,
                'currency': 0,
                'issue_size': 0,
                'coupon_rate': 0,
                'banks': 0
            }
        }
        
        # Process files with progress bar if available
        iterator = tqdm(pdf_files, desc="Processing PDFs") if HAS_TQDM else pdf_files
        
        for pdf_file in iterator:
            try:
                result = self.debug_single_pdf(str(pdf_file))
                if result['success']:
                    stats['successful_extractions'] += 1
                    stats['confidence_levels'][result['extraction_confidence']] += 1
                    
                    # Update field success rates
                    for extractor_type, debug_result in result['debug_results'].items():
                        extraction_result = debug_result.get('extraction_result', {})
                        if extractor_type == 'date':
                            if extraction_result.get('issue_date'): 
                                stats['field_success_rates']['issue_date'] += 1
                            if extraction_result.get('maturity_date'): 
                                stats['field_success_rates']['maturity_date'] += 1
                        elif extractor_type == 'currency':
                            if extraction_result.get('currency'): 
                                stats['field_success_rates']['currency'] += 1
                            if extraction_result.get('issue_size'): 
                                stats['field_success_rates']['issue_size'] += 1
                        elif extractor_type == 'coupon':
                            if extraction_result.get('coupon_rate'): 
                                stats['field_success_rates']['coupon_rate'] += 1
                        elif extractor_type == 'bank':
                            if extraction_result.get('extracted_banks'): 
                                stats['field_success_rates']['banks'] += 1
                else:
                    stats['failed_extractions'] += 1
                
                results.append(result)
                
            except Exception as e:
                self.logger.error(f"Error processing {pdf_file}: {str(e)}")
                stats['failed_extractions'] += 1
        
        # Calculate success rates as percentages
        for field in stats['field_success_rates']:
            stats['field_success_rates'][field] = (
                stats['field_success_rates'][field] / stats['total_files'] * 100
                if stats['total_files'] > 0 else 0
            )
        
        # Save results
        results_file = output_dir / "batch_debug_results.json"
        with open(results_file, 'w') as f:
            json.dump({
                'stats': stats,
                'results': results
            }, f, indent=2, default=str)
        
        self._print(f"\nBatch debug completed. Results saved to {results_file}")
        self._print_batch_summary(stats)
        
        return {'stats': stats, 'results': results}
    
    def _print_batch_summary(self, stats: Dict):
        """Print batch processing summary."""
        self._print(f"\n===== BATCH PROCESSING SUMMARY =====")
        self._print(f"Total files processed: {stats['total_files']}")
        self._print(f"Successful extractions: {stats['successful_extractions']}")
        self._print(f"Failed extractions: {stats['failed_extractions']}")
        
        self._print(f"\nConfidence distribution:")
        for level, count in stats['confidence_levels'].items():
            percentage = count / stats['total_files'] * 100 if stats['total_files'] > 0 else 0
            self._print(f"  {level}: {count} ({percentage:.1f}%)")
        
        self._print(f"\nField success rates:")
        for field, rate in stats['field_success_rates'].items():
            self._print(f"  {field}: {rate:.1f}%")


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="Consolidated Debug Extraction Suite")
    parser.add_argument("path", help="Path to PDF file or directory")
    parser.add_argument("--mode", choices=['single', 'batch'], default='single',
                       help="Debug mode: single file or batch processing")
    parser.add_argument("--extractor-type", choices=['date', 'currency', 'coupon', 'bank'],
                       help="Specific extractor to debug (single mode only)")
    parser.add_argument("--output-dir", default="debug_results",
                       help="Output directory for batch results")
    parser.add_argument("--limit", type=int, help="Limit number of files in batch mode")
    parser.add_argument("--pattern", default="*.pdf", help="File pattern for batch mode")
    parser.add_argument("--quiet", action='store_true', help="Suppress detailed output")
    args = parser.parse_args()
    
    debugger = ExtractionDebugger(quiet=args.quiet)
    
    if args.mode == 'single':
        if not os.path.exists(args.path):
            print(f"Error: File not found: {args.path}")
            return
        
        result = debugger.debug_single_pdf(args.path, args.extractor_type)
        if not result['success']:
            print(f"Error: {result.get('error', 'Unknown error')}")
    
    elif args.mode == 'batch':
        if not os.path.isdir(args.path):
            print(f"Error: Directory not found: {args.path}")
            return
        
        debugger.batch_debug(args.path, args.output_dir, args.limit, args.pattern)


if __name__ == "__main__":
    main() 