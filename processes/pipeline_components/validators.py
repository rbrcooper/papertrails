import re
from datetime import datetime
import logging
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

PROGRAMME_REJECT_CODES = frozenset({"BPWO", "BPFT", "SECN", "REGN", "URGN", "SMRY"})
TIER1_DOC_CODES = frozenset({"FTWS", "STDA", "SUPP"})
DOC_CODE_PRIORITY = {"FTWS": 0, "SUPP": 1, "STDA": 2}

UNDERWRITER_ROLE_KEYWORDS = (
    "bookrunner", "book runner", "lead manager", "joint lead", "active bookrunner",
    "global coordinator", "coordinator", "manager", "underwriter", "arranger",
    "dealer",
)
NON_UNDERWRITER_ROLE_KEYWORDS = (
    "fiscal agent", "paying agent", "clearing system", "clearing", "registrar",
    "calculation agent", "any leading bank",
)
BANK_NAME_BLOCKLIST = frozenset({
    "fiscal agent", "paying agent", "clearing system", "clearing", "registrar",
    "calculation agent", "any leading bank", "the managers", "the manager",
})
NON_BANK_ENTITY_SUBSTRINGS = (
    "national oil",
    "beteiligungs",
    "republic of",
    "government of",
)


def doc_code_rank(doc_type_code: Optional[str] = None, doc_type_descr: Optional[str] = None) -> int:
    """Lower is better: FTWS (0) > SUPP (1) > STDA (2) > unknown (99)."""
    code = _parse_doc_type_code(doc_type_code, doc_type_descr)
    return DOC_CODE_PRIORITY.get(code, 99)


def parse_row_date(row: Dict[str, Any]) -> Optional[datetime]:
    date_text = (row.get("date") or "").strip()
    if not date_text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(date_text[:10], fmt)
        except ValueError:
            continue
    return None


def _parse_doc_type_code(doc_type_code: Optional[str], doc_type_descr: Optional[str]) -> str:
    code = (doc_type_code or "").strip().upper()
    if code and len(code) <= 6 and code.isalnum():
        return code
    descr = (doc_type_descr or doc_type_code or "").upper()
    for known in PROGRAMME_REJECT_CODES | TIER1_DOC_CODES:
        if known in descr.split():
            return known
    m = re.search(r"\b([A-Z]{4})\b", descr)
    return m.group(1) if m else ""


def classify_doc_tier(doc_type_code: Optional[str] = None, doc_type_descr: Optional[str] = None) -> str:
    code = _parse_doc_type_code(doc_type_code, doc_type_descr)
    descr_l = (doc_type_descr or doc_type_code or "").lower()

    if code in PROGRAMME_REJECT_CODES:
        return "reject"
    if "base prospectus" in descr_l:
        if "without final" in descr_l or code == "BPWO":
            return "reject"
        if code == "BPFT":
            return "reject"
    if "securities note" in descr_l and code != "FTWS":
        return "reject"
    if "registration document" in descr_l or "universal registration" in descr_l:
        return "reject"
    if code in TIER1_DOC_CODES:
        return "tier1"
    if any(k in descr_l for k in ("final term", "pricing supplement", "supplemental final")):
        return "tier1"
    if "base prospectus" in descr_l:
        return "tier2"
    return "reject"


def is_underwriter_role(role: str) -> bool:
    if not role:
        return False
    rl = role.lower()
    if any(k in rl for k in NON_UNDERWRITER_ROLE_KEYWORDS):
        return False
    return any(k in rl for k in UNDERWRITER_ROLE_KEYWORDS)


def filter_underwriter_banks(banks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for b in banks:
        if not isinstance(b, dict):
            continue
        raw = (b.get("raw_name") or "").strip()
        raw_l = raw.lower()
        if not raw or raw_l in BANK_NAME_BLOCKLIST:
            continue
        if any(s in raw_l for s in NON_BANK_ENTITY_SUBSTRINGS):
            continue
        if len(raw) < 4:
            continue
        role = b.get("role") or "Unknown"
        if role != "Unknown" and not is_underwriter_role(role):
            continue
        out.append(b)
    return out


def compute_allocated_amount(issue_size: Optional[float], banks: List[Dict[str, Any]]) -> Tuple[Optional[float], int]:
    underwriters = filter_underwriter_banks(banks)
    if not underwriters:
        underwriters = [b for b in banks if isinstance(b, dict) and b.get("raw_name")]
    n = len(underwriters)
    if not issue_size or n == 0:
        return None, n
    try:
        size = float(issue_size)
    except (TypeError, ValueError):
        return None, n
    if size <= 0:
        return None, n
    return round(size / n, 2), n


def select_esma_rows(
    rows: List[Dict[str, Any]],
    policy: str = "strict",
    min_score: float = 0.55,
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for r in rows:
        tier = classify_doc_tier(r.get("doc_type_code"), r.get("doc_type"))
        r = {**r, "doc_tier": tier}
        if tier == "reject":
            continue
        if tier == "tier2" and policy == "strict":
            continue
        score = float(r.get("score") or 0)
        isin_match = float(r.get("isin_match") or 0) > 0
        if tier == "tier1" and (isin_match or score >= min_score):
            candidates.append(r)
        elif tier == "tier2" and policy == "balanced" and score >= min_score:
            candidates.append(r)

    by_isin: Dict[str, List[Dict[str, Any]]] = {}
    no_isin: List[Dict[str, Any]] = []
    for r in candidates:
        isin = (r.get("isin") or "").strip()
        if isin and len(isin) >= 12:
            by_isin.setdefault(isin, []).append(r)
        else:
            no_isin.append(r)

    selected: List[Dict[str, Any]] = []

    def _pick_best(group: List[Dict[str, Any]]) -> Dict[str, Any]:
        def sort_key(x):
            tier_rank = 0 if x.get("doc_tier") == "tier1" else 1
            code_rank = doc_code_rank(x.get("doc_type_code"), x.get("doc_type"))
            dt = parse_row_date(x)
            date_ord = dt.timestamp() if dt else 0.0
            return (tier_rank, code_rank, -date_ord, -float(x.get("score") or 0))

        group.sort(key=sort_key)
        best = group[0]
        best["selection_reason"] = "tier1_best_code_date" if len(group) > 1 else "tier1_only_candidate"
        return best

    for group in by_isin.values():
        selected.append(_pick_best(group))

    if no_isin:
        seen_urls = set()
        def _no_isin_key(x):
            dt = parse_row_date(x)
            date_ord = dt.timestamp() if dt else 0.0
            return (
                doc_code_rank(x.get("doc_type_code"), x.get("doc_type")),
                -date_ord,
                -float(x.get("score") or 0),
            )

        for r in sorted(no_isin, key=_no_isin_key):
            url = r.get("url")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            r["selection_reason"] = "tier1_no_isin_on_row"
            selected.append(r)
            break

    return selected


def compute_completeness_gates(stats: Dict[str, Any]) -> Dict[str, Any]:
    def rate(num, den):
        return round(num / den, 4) if den else 0.0

    g1 = rate(stats.get("isins_with_tier1", 0), stats.get("isins_in_scope", 0))
    g2 = rate(stats.get("tier1_valid_underwriter_set", 0), stats.get("tier1_downloaded", 0))
    g3 = rate(stats.get("allocated_rows", 0), stats.get("eligible_for_allocation", 0))
    g4_pass = stats.get("benchmark_exact_matches", 0) >= 2 and not stats.get("benchmark_role_hallucinations", False)

    gates = {
        "G1_tier1_coverage": {"value": g1, "target": 0.70, "pass": g1 >= 0.70},
        "G2_bank_set_validity": {"value": g2, "target": 0.80, "pass": g2 >= 0.80},
        "G3_amount_emit_rate": {"value": g3, "target": 0.95, "pass": g3 >= 0.95},
        "G4_benchmark_quality": {"value": stats.get("benchmark_exact_matches", 0), "target": 2, "pass": g4_pass},
    }
    return {"gates": gates, "ship": all(g["pass"] for g in gates.values()), "stats": stats}

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

    def quick_first_page_checks(self, pdf_path: str, expected_company: str, **kwargs) -> Dict[str, Any]:
        """
        Quick validation check on first 1-2 pages before full extraction.
        Checks for issuer/guarantor match and ISIN presence.
        
        Args:
            pdf_path: Path to the PDF file
            expected_company: Expected company name
            **kwargs: Flexible arguments (like expected_isins)
            
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
            
            # Check for ISIN pattern (2 letters + 9 digits + 1 check digit)
            isin_pattern = re.compile(r'\b[A-Z]{2}[0-9A-Z]{9}[0-9]\b')
            isin_match = isin_pattern.search(first_pages_text.upper())
            isin_present = isin_match is not None
            
            # Language/Type Check:
            # European bond documents are often English-first but might have Italian/other keywords
            # We want to ensure it's at least mostly English/Financial.
            english_keywords = [
                'notes', 'bonds', 'prospectus', 'maturity', 'interest',
                'underwriter', 'manager', 'coupon', 'redemption', 'issuer',
                'final terms', 'pricing supplement'
            ]
            english_keyword_count = sum(1 for kw in english_keywords if kw in text_lower)
            
            # Lowered threshold to 1 for quick check, 2-3 preferred
            likely_english = english_keyword_count >= 1
            
            it_keywords = ['certificati', 'obbligazioni', 'italiana']
            it_keyword_count = sum(1 for kw in it_keywords if kw in text_lower)
            # Only flag as non-English if it's HEAVILY Italian and lacks English keywords
            # (Relaxed this to avoid false positives for EU cross-listings)
            language_mismatch = it_keyword_count > english_keyword_count and it_keyword_count >= 2

            # Check for guarantor mention (common keywords)
            guarantor_keywords = ['guarantor', 'guarantee', 'guaranteed by', 'guaranteed']
            guarantor_mentioned = any(keyword in text_lower for keyword in guarantor_keywords)
            
            # ISIN cross-check (if expected ISINs provided)
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
                reasons.append(f"Document may not be financial/English (found {english_keyword_count} keywords)")
            if language_mismatch:
                reasons.append(f"Italian language mismatch (IT: {it_keyword_count}, Eng: {english_keyword_count})")
            if isin_mismatch:
                reasons.append(f"No ISIN overlap found with expected company ISINs")
                
            max_pdf_chars = kwargs.get('max_pdf_chars', 80000)
            pdf_path_obj = Path(pdf_path)
            section_only = False
            if pdf_path_obj.exists():
                if pdf_path_obj.stat().st_size > 1_000_000:
                    section_only = True
                elif len(first_pages_text) * 20 > max_pdf_chars:
                    section_only = True

            pass_check = likely_english and not language_mismatch and (issuer_match or (isin_present and not isin_mismatch))

            return {
                'pass': pass_check,
                'reason': '; '.join(reasons) if reasons else 'Basic checks passed',
                'issuer_match': issuer_match,
                'isin_present': isin_present,
                'guarantor_mentioned': guarantor_mentioned,
                'likely_english': likely_english,
                'isin_mismatch': isin_mismatch,
                'section_only': section_only,
                'text_sample': first_pages_text[:500],
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