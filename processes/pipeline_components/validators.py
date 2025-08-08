import re
from datetime import datetime
import logging
from typing import Dict, Any, List

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