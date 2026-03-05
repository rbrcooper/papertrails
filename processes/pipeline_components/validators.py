import re
from datetime import datetime
import logging
from typing import Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)

class ExtractionValidator:
    """
    Performs comprehensive validation on the data extracted by the PDFExtractor.
    """
    def __init__(self):
        """Initializes the validator with a set of validation rules."""
        self.validation_rules = [
            self.is_metadata_present,
            self.are_dates_valid,
            self.is_issue_date_before_maturity_date,
            self.is_currency_info_valid,
            self.is_coupon_info_present,
            self.is_coupon_rate_reasonable,  # New rule
            self.are_banks_extracted,
            self.is_ai_extraction_effective
        ]

    def validate_extraction(self, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs all validation rules against an extraction result.

        Args:
            extraction_result: The dictionary returned by the PDFExtractor.

        Returns:
            A dictionary containing the validation results.
        """
        if not extraction_result or not isinstance(extraction_result, dict):
            return {
                'is_valid': False,
                'overall_confidence': 0.0,
                'validation_checks': [{'check': 'Overall Structure', 'passed': False, 'details': 'Extraction result is empty or invalid.'}]
            }

        passed_checks = 0
        validation_checks = []

        for rule_func in self.validation_rules:
            passed, details = rule_func(extraction_result)
            if passed:
                passed_checks += 1
            
            validation_checks.append({
                'check': rule_func.__name__,
                'passed': passed,
                'details': details
            })

        overall_confidence = (passed_checks / len(self.validation_rules)) * 100
        is_valid = overall_confidence > 75  # Consider valid if more than 75% of checks pass

        return {
            'is_valid': is_valid,
            'overall_confidence': round(overall_confidence, 2),
            'validation_checks': validation_checks
        }

    def is_metadata_present(self, result: Dict[str, Any]) -> (bool, str):
        """Checks if the main 'metadata' key and its essential sub-keys exist."""
        metadata = result.get('metadata')
        if not metadata or not isinstance(metadata, dict):
            return False, "FAIL: 'metadata' field is missing or not a dictionary."
        
        required_keys = ['issue_date', 'maturity_date', 'currency', 'issue_size', 'coupon_rate']
        missing_keys = [key for key in required_keys if metadata.get(key) is None]

        if missing_keys:
            return False, f"FAIL: Metadata is missing the following keys: {', '.join(missing_keys)}."
        
        return True, "PASS: All essential metadata keys are present."

    def are_dates_valid(self, result: Dict[str, Any]) -> (bool, str):
        """Checks if the extracted date strings are in a valid YYYY-MM-DD format."""
        metadata = result.get('metadata', {})
        issue_date = metadata.get('issue_date')
        maturity_date = metadata.get('maturity_date')
        
        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')

        if issue_date and not date_pattern.match(issue_date):
            return False, f"FAIL: Issue date '{issue_date}' is not in YYYY-MM-DD format."
        
        if maturity_date and not date_pattern.match(maturity_date):
            return False, f"FAIL: Maturity date '{maturity_date}' is not in YYYY-MM-DD format."

        return True, "PASS: Dates are in valid YYYY-MM-DD format."

    def is_issue_date_before_maturity_date(self, result: Dict[str, Any]) -> (bool, str):
        """Checks if the issue date is chronologically before the maturity date."""
        metadata = result.get('metadata', {})
        try:
            issue_date = datetime.strptime(metadata.get('issue_date'), '%Y-%m-%d')
            maturity_date = datetime.strptime(metadata.get('maturity_date'), '%Y-%m-%d')
            if issue_date >= maturity_date:
                return False, f"FAIL: Issue date {issue_date.date()} is not before maturity date {maturity_date.date()}."
        except (ValueError, TypeError):
            return False, "SKIP: Could not compare dates due to invalid format or missing values."
        
        return True, "PASS: Issue date is before maturity date."

    def is_currency_info_valid(self, result: Dict[str, Any]) -> (bool, str):
        """Checks for the presence and basic validity of currency and issue size."""
        metadata = result.get('metadata', {})
        currency = metadata.get('currency')
        issue_size = metadata.get('issue_size')

        if not currency or not isinstance(currency, str) or len(currency) != 3:
            return False, f"FAIL: Currency '{currency}' is invalid or missing."
        
        if not isinstance(issue_size, (int, float)) or issue_size <= 0:
            return False, f"FAIL: Issue size '{issue_size}' is invalid or missing."

        return True, f"PASS: Found valid currency ({currency}) and issue size ({issue_size})."

    def is_coupon_info_present(self, result: Dict[str, Any]) -> (bool, str):
        """Checks for the presence of coupon rate and type."""
        metadata = result.get('metadata', {})
        coupon_rate = metadata.get('coupon_rate')
        coupon_type = metadata.get('coupon_type')

        if coupon_rate is None or coupon_type is None:
            return False, "FAIL: Coupon rate or type is missing."
        
        return True, f"PASS: Found coupon rate ({coupon_rate}) and type ({coupon_type})."

    def are_banks_extracted(self, result: Dict[str, Any]) -> (bool, str):
        """Checks if the list of extracted banks is present and not empty."""
        extracted_banks = result.get('extracted_banks')
        if extracted_banks is None or not isinstance(extracted_banks, list):
            return False, "FAIL: 'extracted_banks' field is missing or not a list."
        
        if not extracted_banks:
            return False, "FAIL: No banks were extracted."

        return True, f"PASS: Extracted {len(extracted_banks)} bank(s)."

    def is_ai_extraction_effective(self, result: Dict[str, Any]) -> (bool, str):
        """Checks if AI was used and if it successfully found banks."""
        ai_used = result.get('ai_extraction_used', False)
        if not ai_used:
            return True, "SKIP: AI extraction was not used."
            
        extracted_banks = result.get('extracted_banks', [])
        if not extracted_banks:
            return False, "FAIL: AI extraction was used but failed to find any banks."
        
        return True, "PASS: AI extraction was used and successfully found banks."

    def quick_first_page_checks(self, pdf_path: str, expected_company: str) -> Dict[str, Any]:
        """
        Quick validation check on first 1-2 pages before full extraction.
        Checks for issuer/guarantor match and ISIN presence.
        
        Args:
            pdf_path: Path to the PDF file
            expected_company: Expected company name
            
        Returns:
            Dictionary with validation results and reasons
        """
        try:
            # Import here to avoid circular dependencies
            from processes.pdf_extraction.core import ExtractionEngine
            
            engine = ExtractionEngine(use_ocr=False)  # Quick check, skip OCR
            first_pages_text = engine.extract_text_first_pages(pdf_path, num_pages=2)
            
            if not first_pages_text or len(first_pages_text) < 50:
                return {
                    'pass': False,
                    'reason': 'Cannot read first pages (possibly scanned PDF or corrupted)',
                    'issuer_match': False,
                    'isin_present': False,
                    'guarantor_mentioned': False
                }
            
            text_lower = first_pages_text.lower()
            
            # Normalize company name for matching
            expected_normalized = self._normalize_company_name(expected_company)
            text_normalized = self._normalize_company_name(first_pages_text)
            
            # Check if expected company appears in first pages
            issuer_match = (
                expected_normalized in text_normalized or
                expected_company.lower() in text_lower or
                any(alias.lower() in text_lower for alias in expected_company.split())
            )
            
            # Strict Language/Type Check:
            english_keywords = ['notes', 'bonds', 'prospectus', 'maturity', 'interest']
            english_keyword_count = sum(1 for kw in english_keywords if kw in text_lower)
            
            it_keywords = ['certificati', 'obbligazioni', 'italiana']
            it_keyword_count = sum(1 for kw in it_keywords if kw in text_lower)
            
            likely_english = english_keyword_count >= 2
            likely_italian = it_keyword_count >= 2

            if not likely_english or likely_italian:
                reasons = [f"Document language mismatch (Eng: {english_keyword_count}, IT: {it_keyword_count})"]
                return {'pass': False, 'reason': '; '.join(reasons)}

            # Check for ISIN pattern (2 letters + 9 digits + 1 check digit)
            isin_pattern = re.compile(r'\b[A-Z]{2}[0-9A-Z]{9}[0-9]\b')
            isin_match = isin_pattern.search(first_pages_text.upper())
            isin_present = isin_match is not None
            
            # Check for guarantor mention (common keywords)
            guarantor_keywords = ['guarantor', 'guarantee', 'guaranteed by', 'guaranteed']
            guarantor_mentioned = any(keyword in text_lower for keyword in guarantor_keywords)
            
            # 1. Language check: ensure document is in English
            english_keywords = ['notes', 'bonds', 'prospectus', 'maturity', 'interest',
                                'underwriter', 'manager', 'coupon', 'redemption', 'issuer']
            english_keyword_count = sum(1 for kw in english_keywords if kw in text_lower)
            likely_english = english_keyword_count >= 3
            
            # 2. ISIN cross-check (if expected ISINs provided)
            # expected_isins can be passed in via kwargs in the future or via result object
            expected_isins = kwargs.get('expected_isins', [])
            isin_mismatch = False
            if expected_isins and isin_present:
                found_isins = set(isin_pattern.findall(first_pages_text.upper()))
                expected_set = set(i.upper() for i in expected_isins if i)
                isin_overlap = found_isins & expected_set
                if not isin_overlap:
                    isin_mismatch = True
            
            reasons = []
            if not issuer_match:
                reasons.append(f"Issuer '{expected_company}' not clearly found in first pages")
            if not isin_present:
                reasons.append("No ISIN pattern found")
            if not likely_english:
                reasons.append(f"Document may not be in English (only {english_keyword_count}/10 financial keywords found)")
            if isin_mismatch:
                reasons.append(f"No ISIN overlap found with expected company ISINs")
                
            # Determine overall pass
            # Pass if it's likely English AND (issuer matches OR (ISIN present AND overlap confirmed if available))
            pass_check = likely_english and (issuer_match or (isin_present and not isin_mismatch))
            
            return {
                'pass': pass_check,
                'reason': '; '.join(reasons) if reasons else 'Basic checks passed',
                'issuer_match': issuer_match,
                'isin_present': isin_present,
                'guarantor_mentioned': guarantor_mentioned,
                'likely_english': likely_english,
                'isin_mismatch': isin_mismatch,
                'text_sample': first_pages_text[:500]  # Sample for debugging
            }
            
        except Exception as e:
            logger.warning(f"Quick first page check failed for {pdf_path}: {e}")
            return {
                'pass': True,  # Default to pass if check fails (don't block on errors)
                'reason': f'Quick check error: {str(e)}',
                'issuer_match': None,
                'isin_present': None,
                'guarantor_mentioned': None
            }
    
    def _normalize_company_name(self, name: str) -> str:
        """Normalize company name for fuzzy matching."""
        if not name:
            return ""
        # Remove common legal suffixes and normalize
        normalized = re.sub(r'[\W_]+', ' ', name.lower())
        normalized = re.sub(r'\b(ag|sa|gmbh|nv|n\.v\.|plc|s\.a\.|s\.p\.a\.|b\.v\.|bv|inc|ltd|limited|corporation|corp)\b', '', normalized)
        return re.sub(r'\s+', ' ', normalized).strip()
    
    def is_coupon_rate_reasonable(self, result: Dict[str, Any]) -> (bool, str):
        """Checks if coupon rate is within reasonable bounds (0-20%)."""
        metadata = result.get('metadata', {})
        coupon_rate = metadata.get('coupon_rate')
        
        if coupon_rate is None:
            return False, "SKIP: Coupon rate is missing."
        
        try:
            rate = float(coupon_rate)
            if rate < 0:
                return False, f"FAIL: Coupon rate {rate}% is negative."
            if rate > 20:
                return False, f"FAIL: Coupon rate {rate}% exceeds reasonable maximum (20%)."
            return True, f"PASS: Coupon rate {rate}% is within reasonable bounds (0-20%)."
        except (ValueError, TypeError):
            return False, f"FAIL: Coupon rate '{coupon_rate}' is not a valid number." 