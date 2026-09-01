import re
from typing import Dict, Any, Optional, Tuple, List
from ..utils.pattern_registry import (
    ISO_CODE_BOUNDED,
    ISO_CURRENCY_CODES,
    PatternRegistry,
)
from .base_extractor import BaseExtractor

_LEI_RE = re.compile(r'(?<![A-Za-z0-9])[A-Za-z0-9]{20}(?![A-Za-z0-9])')
_PROGRAMME_TOKEN_RE = re.compile(r'programme|limit|ceiling', re.IGNORECASE)
_CUR_AMT_RE = re.compile(
    r'(EUR|USD|GBP|CHF|JPY|€|\$|£|Euro)\s*([\d][\d,.]*)\s*(?:million|billion|m\b|bn)?',
    re.IGNORECASE,
)
_TRANCHE_LABEL_RE = re.compile(
    r'(?:\(\s*(?:ii|b|2)\s*\)\s*)?\btranche\b(?!\s+(?:number|no\.?)\b)\s*[:.]',
    re.IGNORECASE,
)
_ANA_BLOCK_RE = re.compile(
    r'aggregate\s+(?:nominal|principal)\s+amount.{0,400}',
    re.IGNORECASE | re.DOTALL,
)
_ANA_SERIES_RE = re.compile(
    r'(?:\(\s*(?:i|a|1)\s*\)\s*)?series\s*[:.]?\s*(?:of\s+)?'
    r'(EUR|USD|GBP|CHF|JPY|€|\$|£|Euro)\s*([\d][\d,.]*)\s*(?:million|billion|m\b|bn)?',
    re.IGNORECASE,
)
_BARE_AMT_RE = re.compile(r'([\d]{1,3}(?:,\d{3}){2,}|\d{7,})')
_PROGRAMME_TAIL_RE = re.compile(
    r'([\d]{1,3}(?:,\d{3}){2,}|\d{7,})\s*(?:Euro|EUR|€)\s+'
    r'(?:Medium\s*Term\s*Note\s+|Debt\s*Issuance\s+|EMTN\s+)?Programme',
    re.IGNORECASE,
)
_SPECIFIED_CCY_RE = re.compile(
    r'Specified\s+Currency(?:\s+or\s+Currencies)?\s*[:.]?\s*'
    r'(?:\(?(EUR|USD|GBP|CHF|JPY|€|\$|£)\)?|Euro)',
    re.IGNORECASE,
)

class CurrencyExtractor(BaseExtractor):
    """Extracts issue size and currency information."""
    
    def __init__(self, debug_mode=False):
        """Initialize the currency extractor."""
        self.patterns = PatternRegistry.get_currency_patterns()
        self.debug_mode = debug_mode
        
    def extract(self, text: str) -> Dict[str, Any]:
        """
        Extract currency and issue size information from text.
        
        Args:
            text: The text to extract currency and issue size from
            
        Returns:
            Dictionary with issue_size and currency keys
        """
        currency_info = {
            'issue_size': None,
            'currency': None,
            'issue_size_range': None,
            'programme_size': None,
            'confidence': 'medium'  # Default confidence
        }
        
        if not text:
            return currency_info
        
        if self.debug_mode:
            print(f"CurrencyExtractor: Processing {len(text)} characters of text")
            
        # Normalize text
        normalized_text = self._normalize_text(text)
        
        if self.debug_mode:
            print(f"CurrencyExtractor: Processing {len(normalized_text)} characters of normalized text")
            
        labelled_currency, labelled_size = self._extract_labelled_tranche(text)
        if not labelled_size:
            labelled_currency, labelled_size = self._extract_labelled_tranche(normalized_text)
        programme_size = self._extract_programme_size(text) or self._extract_programme_size(
            normalized_text
        )
        currency, issue_size, issue_size_range = self._extract_issue_size_currency(normalized_text)

        if labelled_size:
            issue_size = labelled_size
            if labelled_currency:
                currency = labelled_currency

        if programme_size:
            currency_info['programme_size'] = programme_size
            if self.debug_mode:
                print(f"CurrencyExtractor: Found programme size: {programme_size}")

        if currency:
            currency_info['currency'] = currency
            if self.debug_mode:
                print(f"CurrencyExtractor: Found currency: {currency}")
            
        if issue_size:
            currency_info['issue_size'] = issue_size
            if self.debug_mode:
                print(f"CurrencyExtractor: Found issue size: {issue_size}")
            
        if issue_size_range:
            currency_info['issue_size_range'] = issue_size_range
            if self.debug_mode:
                print(f"CurrencyExtractor: Found issue size range: {issue_size_range}")
            
        # If primary extraction failed, try a simpler approach
        if not currency or not issue_size:
            if self.debug_mode:
                print("CurrencyExtractor: Trying simpler approach for currency and issue size")
                
            simple_currency, simple_size, simple_range = self._extract_simple_currency_amount(normalized_text)
            
            if not currency_info['currency'] and simple_currency:
                currency_info['currency'] = simple_currency
                if self.debug_mode:
                    print(f"CurrencyExtractor: Found currency with simpler approach: {simple_currency}")
                
            if not currency_info['issue_size'] and simple_size:
                currency_info['issue_size'] = simple_size
                if self.debug_mode:
                    print(f"CurrencyExtractor: Found issue size with simpler approach: {simple_size}")
                
            if not currency_info['issue_size_range'] and simple_range:
                currency_info['issue_size_range'] = simple_range
                if self.debug_mode:
                    print(f"CurrencyExtractor: Found issue size range with simpler approach: {simple_range}")
        
        self._drop_programme_as_issue_size(currency_info)

        # Set confidence based on available data
        if currency_info['currency'] and currency_info['issue_size']:
            currency_info['confidence'] = 'high'
        elif currency_info['currency'] or currency_info['issue_size']:
            currency_info['confidence'] = 'medium'
        else:
            currency_info['confidence'] = 'low'
        
        currency_info = self._sanitize_issue_size(currency_info, text)
        self._drop_programme_as_issue_size(currency_info)

        if currency_info.get("currency"):
            canon = self._canonical_iso(currency_info["currency"]) or self._map_symbol_to_code(
                currency_info["currency"]
            )
            currency_info["currency"] = canon

        if self.debug_mode:
            print(f"CurrencyExtractor: Final results - currency: {currency_info['currency']}, issue_size: {currency_info['issue_size']}, confidence: {currency_info['confidence']}")
            
        return currency_info

    def _canonical_iso(self, token: Optional[str]) -> Optional[str]:
        """Return uppercase ISO code if token is in the allowlist, else None."""
        if not token:
            return None
        code = token.strip().upper()
        if code in ISO_CURRENCY_CODES:
            return code
        return None

    def _lei_spans(self, text: str) -> List[Tuple[int, int]]:
        return [m.span() for m in _LEI_RE.finditer(text)]

    def _inside_lei(self, start: int, end: int, lei_spans: List[Tuple[int, int]]) -> bool:
        for ls, le in lei_spans:
            if start >= ls and end <= le:
                return True
        return False

    def _is_programme_context(self, text: str, start: int, end: int, match_text: str = "") -> bool:
        """True when programme/limit/ceiling sits in the match or immediately around it."""
        if match_text and _PROGRAMME_TOKEN_RE.search(match_text):
            return True
        before = text[max(0, start - 50):start]
        after = text[end:min(len(text), end + 80)]
        return bool(_PROGRAMME_TOKEN_RE.search(before) or _PROGRAMME_TOKEN_RE.search(after))

    def _size_from_cur_amt(self, amount_raw: str, context: str) -> Optional[str]:
        size = self._normalize_number(amount_raw)
        if not size:
            return None
        try:
            if float(size) >= 1_000_000:
                return str(int(round(float(size))))
        except (TypeError, ValueError):
            pass
        return self._apply_multiplier(size, context)

    def _currency_from_token(self, token: Optional[str]) -> Optional[str]:
        if not token:
            return None
        return self._canonical_iso(token) or self._map_symbol_to_code(token)

    def _infer_issue_currency(self, text: str) -> Optional[str]:
        m = _SPECIFIED_CCY_RE.search(text or "")
        if m:
            token = m.group(1) or "Euro"
            return self._currency_from_token(token)
        if re.search(r'\bEuro\b|\bEUR\b|€', text[:4000] if text else "", re.IGNORECASE):
            return "EUR"
        return None

    def _parse_bare_or_cur_amount(self, window: str) -> Tuple[Optional[str], Optional[str]]:
        am = _CUR_AMT_RE.match(window) or _CUR_AMT_RE.search(window[:60])
        if am:
            currency = self._currency_from_token(am.group(1))
            size = self._size_from_cur_amt(am.group(2), am.group(0))
            return currency, size
        bm = _BARE_AMT_RE.match(window) or _BARE_AMT_RE.search(window[:48])
        if bm:
            size = self._size_from_cur_amt(bm.group(1), bm.group(1))
            return None, size
        return None, None

    def _extract_labelled_tranche(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Prefer Aggregate Nominal Amount (ii) Tranche, then Series, over cover ceilings."""
        if not text:
            return None, None
        inferred = self._infer_issue_currency(text)
        for tm in _TRANCHE_LABEL_RE.finditer(text):
            window = text[tm.end():min(len(text), tm.end() + 120)].lstrip()
            currency, size = self._parse_bare_or_cur_amount(window)
            if size:
                try:
                    if float(size) < 1_000_000:
                        continue
                except (TypeError, ValueError):
                    continue
                return currency or inferred, size
        ana = _ANA_BLOCK_RE.search(text)
        if ana:
            block = ana.group(0)
            sm = _ANA_SERIES_RE.search(block)
            if sm:
                currency = self._currency_from_token(sm.group(1))
                size = self._size_from_cur_amt(sm.group(2), sm.group(0))
                if size:
                    return currency or inferred, size
            series_bare = re.search(
                r'(?:\(\s*(?:i|a|1)\s*\)\s*)?series\s*[:.]?\s*([\d]{1,3}(?:,\d{3}){2,}|\d{7,})',
                block,
                re.IGNORECASE,
            )
            if series_bare:
                size = self._size_from_cur_amt(series_bare.group(1), series_bare.group(1))
                if size:
                    return inferred, size
            best = None
            best_val = 0.0
            for bm in _BARE_AMT_RE.finditer(block):
                abs_start = ana.start() + bm.start()
                abs_end = ana.start() + bm.end()
                if self._is_programme_context(text, abs_start, abs_end, bm.group(0)):
                    continue
                size = self._size_from_cur_amt(bm.group(1), bm.group(1))
                if not size:
                    continue
                try:
                    val = float(size)
                except (TypeError, ValueError):
                    continue
                if 50_000_000 <= val <= 3_000_000_000 and val > best_val:
                    best_val = val
                    best = size
            if best:
                return inferred, best
        return None, None

    def _extract_programme_size(self, text: str) -> Optional[str]:
        if not text:
            return None
        best: Optional[str] = None
        best_val = 0.0

        def _consider(size: Optional[str]) -> None:
            nonlocal best, best_val
            if not size:
                return
            try:
                val = float(size)
            except (TypeError, ValueError):
                return
            if val > best_val:
                best_val = val
                best = str(int(round(val))) if val >= 1 else size

        for m in _CUR_AMT_RE.finditer(text):
            if not self._is_programme_context(text, m.start(), m.end(), m.group(0)):
                continue
            _consider(self._size_from_cur_amt(m.group(2), m.group(0)))
        for m in _PROGRAMME_TAIL_RE.finditer(text):
            _consider(self._size_from_cur_amt(m.group(1), m.group(0)))
        return best

    def _drop_programme_as_issue_size(self, currency_info: Dict[str, Any]) -> None:
        issue = currency_info.get("issue_size")
        programme = currency_info.get("programme_size")
        if issue is None or programme is None:
            return
        try:
            if float(issue) == float(programme):
                currency_info["issue_size"] = None
        except (TypeError, ValueError):
            if str(issue) == str(programme):
                currency_info["issue_size"] = None

    def _sanitize_issue_size(self, currency_info: Dict[str, Any], text: str) -> Dict[str, Any]:
        """Drop bogus small matches; prefer bond-level EUR amounts over programme limits."""
        raw_currency = currency_info.get("currency")
        canonical = self._canonical_iso(raw_currency) or self._map_symbol_to_code(raw_currency)
        currency_info["currency"] = canonical

        size = currency_info.get("issue_size")
        dropped_small = False
        try:
            if size is not None and float(size) < 1_000_000:
                currency_info["issue_size"] = None
                dropped_small = True
        except (TypeError, ValueError):
            currency_info["issue_size"] = None
            dropped_small = True

        if dropped_small:
            rng = currency_info.get("issue_size_range")
            if rng:
                try:
                    mx = float(rng.get("max") or 0)
                    if mx < 1_000_000:
                        currency_info["issue_size_range"] = None
                except (TypeError, ValueError):
                    currency_info["issue_size_range"] = None

        if currency_info.get("issue_size"):
            return currency_info

        values: List[int] = []
        for m in re.finditer(
            r"\bEUR\s*(\d{1,3}(?:[.,]\d{3})+|\d[\d,]*)\b",
            text,
            re.IGNORECASE,
        ):
            if self._is_programme_context(text, m.start(), m.end(), m.group(0)):
                continue
            raw = m.group(1)
            if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
                num = int(raw.replace(".", ""))
            elif re.fullmatch(r"\d{1,3}(?:,\d{3})+", raw):
                num = int(raw.replace(",", ""))
            else:
                num = int(re.sub(r"[^\d]", "", raw) or "0")
            if num >= 50_000_000:
                values.append(num)

        if not values:
            return currency_info

        bond_sizes = [v for v in values if v <= 3_000_000_000]
        if bond_sizes:
            currency_info["issue_size"] = str(max(bond_sizes))
            currency_info["currency"] = currency_info.get("currency") or "EUR"
        return currency_info
        
    def _extract_issue_size_currency(self, text: str) -> Tuple[Optional[str], Optional[str], Optional[Dict]]:
        """
        Extract issue size and currency from text.
        
        Args:
            text: The text to extract from
            
        Returns:
            A tuple of (currency, issue_size, issue_size_range)
        """
        if not text:
            return None, None, None

        lei_spans = self._lei_spans(text)
            
        # Check for ranges or qualifiers
        is_range = False
        is_up_to = False
        is_at_least = False
        is_approximate = False
        
        if re.search(r'(?:up\s+to|not\s+exceed(?:ing)?|maximum\s+of|no\s+more\s+than)', text, re.IGNORECASE):
            is_up_to = True
            if self.debug_mode:
                print("CurrencyExtractor: Detected 'up to' qualifier")
        
        if re.search(r'(?:at\s+least|minimum\s+of|no\s+less\s+than)', text, re.IGNORECASE):
            is_at_least = True
            if self.debug_mode:
                print("CurrencyExtractor: Detected 'at least' qualifier")
            
        if re.search(r'(?:approximately|around|about|circa|~)', text, re.IGNORECASE):
            is_approximate = True
            if self.debug_mode:
                print("CurrencyExtractor: Detected 'approximate' qualifier")
            
        if re.search(r'(?:between|from|range\s+of)', text, re.IGNORECASE):
            is_range = True
            if self.debug_mode:
                print("CurrencyExtractor: Detected range qualifier")
            
        # Try to find currency and issue size using patterns
        for i, pattern in enumerate(self.patterns['issue_size']):
            if self.debug_mode:
                print(f"CurrencyExtractor: Trying issue size pattern {i+1}")
                
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                full_match = match.group(0)

                if self._inside_lei(match.start(), match.end(), lei_spans):
                    continue
                
                if self.debug_mode:
                    context = text[max(0, match.start() - 30):min(len(text), match.end() + 30)]
                    print(f"CurrencyExtractor: Found match using pattern {i+1}: '{full_match}' in '...{context}...'")
                
                # Extract currency and issue size from groups if possible
                currency = None
                issue_size = None
                groups = match.groups()
                
                # Try to find currency in groups (excluding the amount)
                for group in groups:
                    if group and not any(c.isdigit() for c in group):
                        # Potential currency name or code
                        mapped = self._canonical_iso(group) or self._map_symbol_to_code(group)
                        if mapped:
                            currency = mapped
                            break
                
                # If no currency found in groups, search full_match
                if not currency:
                    for cm in re.finditer(ISO_CODE_BOUNDED, full_match, re.IGNORECASE):
                        abs_start = match.start() + cm.start()
                        abs_end = match.start() + cm.end()
                        if self._inside_lei(abs_start, abs_end, lei_spans):
                            continue
                        mapped = self._canonical_iso(cm.group(0))
                        if mapped:
                            currency = mapped
                            break
                            
                    if not currency:
                        for symbol in self.patterns['currency_symbols']:
                            search_sym = symbol.replace('\\', '')
                            if search_sym in full_match:
                                currency = self._map_symbol_to_code(search_sym)
                                break
                
                # Extract issue size from groups or match
                # Usually the largest numeric group is the amount
                numeric_groups = []
                for group in groups:
                    if group and any(c.isdigit() for c in group):
                        normalized = self._normalize_number(group)
                        if normalized:
                            numeric_groups.append(normalized)
                
                if numeric_groups:
                    # Use the first numeric group as primary
                    issue_size = numeric_groups[0]
                else:
                    # Fallback to searching the full match
                    size_match = re.search(r'([\d,.-]+)(?:\s*(?:million|billion|m|bn))?', full_match)
                    if size_match:
                        issue_size = self._normalize_number(size_match.group(1))
                
                if issue_size:
                    issue_size = self._apply_multiplier(issue_size, full_match)
                
                if self._is_programme_context(text, match.start(), match.end(), full_match):
                    if self.debug_mode:
                        print(f"CurrencyExtractor: Skipping potential programme/limit match: {full_match}")
                    continue

                if currency and issue_size:
                    currency = self._canonical_iso(currency) or self._map_symbol_to_code(currency)
                    if not currency:
                        continue
                    if self.debug_mode:
                        print(f"CurrencyExtractor: Successfully extracted currency {currency} and size {issue_size}")
                    return currency, issue_size, None # Could add range support back if needed
        
        return None, None, None
    
    def _extract_simple_currency_amount(self, text: str) -> Tuple[Optional[str], Optional[str], Optional[Dict]]:
        """
        Try a simpler approach to extract currency and amount when the standard patterns fail.
        
        Args:
            text: The text to extract from
            
        Returns:
            A tuple of (currency, issue_size, issue_size_range)
        """
        # Look for common phrases typically containing issue size
        amount_phrases = [
            r'(?:aggregate\s+nominal\s+amount|issue\s+size|amount\s+of\s+the\s+notes|total\s+issue\s+size)\s*[:]\s*(?:up\s+to\s+)?([A-Z]{3}|\$|€|£|¥)?\s*([\d,\.]+)\s*(?:million|billion|m|bn)?',
            r'(?:issue\s+of|issuance\s+of)\s*(?:up\s+to\s+)?([A-Z]{3}|\$|€|£|¥)?\s*([\d,\.]+)\s*(?:million|billion|m|bn)?',
            r'(?:principal\s+amount)\s*[:]\s*(?:up\s+to\s+)?([A-Z]{3}|\$|€|£|¥)?\s*([\d,\.]+)\s*(?:million|billion|m|bn)?',
            r'nominal\s+amount\s*[:]\s*(?:\([^\)]+\)\s*)?(?:up\s+to\s+)?([A-Z]{3}|\$|€|£|¥)?\s*([\d,\.]+)\s*(?:million|billion|m|bn)?',
            r'([A-Z]{3}|\$|€|£|¥)\s*([\d,\.]+)\s*(?:million|billion|m|bn)?\s*(?:\d{1,2}[\.]\d{1,3})?\s*%\s*(?:notes|bonds)',
            # New patterns for improved extraction
            r'(?:up\s+to\s+)?(?:a\s+)?(?:maximum\s+(?:aggregate\s+)?amount\s+of\s+)?([A-Z]{3}|\$|€|£|¥)?\s*([\d,\.]+)\s*(?:million|billion|thousand|m\b|bn|k\b)?',
            r'(?:up\s+to\s+)?((?:USD|EUR|GBP|JPY|CHF|AUD|CAD|NZD|HKD|SGD|CNY|CNH|SEK|NOK|DKK|CZK|HUF|PLN|RUB|TRY|ZAR))\s*([\d,\.]+)\s*(?:million|billion|thousand|m\b|bn|k\b)?',
            r'(?:programme\s+size|issuance\s+limit|facility\s+amount)\s*(?:of\s+)?(?:up\s+to\s+)?([A-Z]{3}|\$|€|£|¥)?\s*([\d,\.]+)\s*(?:million|billion|thousand|m\b|bn|k\b)?',
            r'(?:issue|issuance)\s+volume\s*(?:of\s+)?(?:up\s+to\s+)?([A-Z]{3}|\$|€|£|¥)?\s*([\d,\.]+)\s*(?:million|billion|thousand|m\b|bn|k\b)?',
            r'(?:total\s+size\s+of\s+the\s+bond)\s*(?:is\s+)?([A-Z]{3}|\$|€|£|¥)?\s*([\d,\.]+)\s*(?:million|billion|thousand|m\b|bn|k\b)?',
            r'(?:value|size)\s+of\s+(?:the\s+)?(?:issue|issuance|offering)\s*[:\-]?\s*([A-Z]{3}|\$|€|£|¥)?\s*([\d,\.]+)\s*(?:million|billion|thousand|m\b|bn|k\b)?',
            r'(?:issued|issuance)\s+in\s+(?:the\s+)?(?:amount\s+of\s+)?([A-Z]{3}|\$|€|£|¥)?\s*([\d,\.]+)\s*(?:million|billion|thousand|m\b|bn|k\b)?'
        ]
        amount_phrases = [p.replace("[A-Z]{3}", ISO_CODE_BOUNDED) for p in amount_phrases]
        lei_spans = self._lei_spans(text)
        
        # Check for "up to" or range qualifiers
        is_up_to = False
        is_at_least = False
        is_approximate = False
        is_range = False
        
        if re.search(r'(?:up\s+to|not\s+exceed(?:ing)?|maximum\s+of|no\s+more\s+than)', text, re.IGNORECASE):
            is_up_to = True
        
        if re.search(r'(?:at\s+least|minimum\s+of|no\s+less\s+than)', text, re.IGNORECASE):
            is_at_least = True
            
        if re.search(r'(?:approximately|around|about|circa|~)', text, re.IGNORECASE):
            is_approximate = True
            
        if re.search(r'(?:between|from|range\s+of)', text, re.IGNORECASE):
            is_range = True
        
        # Check for range patterns first
        currency = None
        issue_size = None
        issue_size_range = None
        
        if is_range:
            range_re = r'(?:between|from)?\s*(?:([A-Z]{3}|\$|€|£|¥))?\s*([\d,.]+)\s*(?:million|billion|m|bn)?\s*(?:and|to|-)\s*(?:([A-Z]{3}|\$|€|£|¥))?\s*([\d,.]+)\s*(?:million|billion|m|bn)?'
            range_re = range_re.replace("[A-Z]{3}", ISO_CODE_BOUNDED)
            range_match = re.search(range_re, text, re.IGNORECASE)
            if (
                range_match
                and not self._inside_lei(range_match.start(), range_match.end(), lei_spans)
                and not self._is_programme_context(
                    text, range_match.start(), range_match.end(), range_match.group(0)
                )
            ):
                # Extract currency (prefer first occurrence, fallback to second)
                currency_symbol = range_match.group(1) or range_match.group(3)
                
                # Convert symbol to code if needed
                if currency_symbol and len(currency_symbol) == 1:
                    currency = self._map_symbol_to_code(currency_symbol)
                else:
                    currency = self._canonical_iso(currency_symbol) or self._map_symbol_to_code(currency_symbol)
                
                # Extract range values
                min_value = self._normalize_number(range_match.group(2))
                max_value = self._normalize_number(range_match.group(4))
                
                # Apply multipliers
                min_value = self._apply_multiplier(min_value, range_match.group(0))
                max_value = self._apply_multiplier(max_value, range_match.group(0))
                
                # Create range object
                issue_size_range = {
                    'min': min_value,
                    'max': max_value
                }
                
                # Use average as main issue size
                if min_value and max_value:
                    try:
                        issue_size = str((float(min_value) + float(max_value)) / 2)
                    except (ValueError, TypeError):
                        issue_size = max_value or min_value
                else:
                    issue_size = max_value or min_value
                
                return currency, issue_size, issue_size_range
        
        # Try each pattern for non-range formats
        for phrase in amount_phrases:
            matches = re.finditer(phrase, text, re.IGNORECASE)
            for match in matches:
                if self._inside_lei(match.start(), match.end(), lei_spans):
                    continue
                if self._is_programme_context(text, match.start(), match.end(), match.group(0)):
                    continue
                # Extract currency
                currency_part = match.group(1) if match.lastindex >= 1 else None
                
                # Handle currency codes vs. symbols
                if currency_part:
                    if len(currency_part) == 1 or currency_part in ['$', '€', '£', '¥']:
                        currency = self._map_symbol_to_code(currency_part)
                    else:
                        currency = self._canonical_iso(currency_part) or self._map_symbol_to_code(currency_part)
                
                # Extract amount
                amount_part = match.group(2) if match.lastindex >= 2 else None
                if amount_part:
                    issue_size = self._normalize_number(amount_part)
                    issue_size = self._apply_multiplier(issue_size, match.group(0))
                    
                    # Handle qualifiers
                    if is_up_to:
                        issue_size_range = {'max': issue_size}
                    elif is_at_least:
                        issue_size_range = {'min': issue_size}
                    elif is_approximate:
                        # For approximate values, create a range of ±10%
                        try:
                            value = float(issue_size)
                            issue_size_range = {
                                'min': str(value * 0.9),
                                'max': str(value * 1.1)
                            }
                        except (ValueError, TypeError):
                            pass
                
                if currency or issue_size:
                    return currency, issue_size, issue_size_range
        
        # Fallback method: Look for any amount with currency in nearby context
        currency_symbols = self.patterns['currency_symbols']
        
        # Find all currency mentions
        currencies_found = []
        for cm in re.finditer(ISO_CODE_BOUNDED, text, re.IGNORECASE):
            if self._inside_lei(cm.start(), cm.end(), lei_spans):
                continue
            mapped = self._canonical_iso(cm.group(0))
            if mapped:
                currencies_found.append(mapped)
        
        for symbol in currency_symbols:
            if re.search(symbol, text, re.IGNORECASE):
                # Map to code
                code = self._canonical_iso(symbol) or self._map_symbol_to_code(symbol)
                if code:
                    currencies_found.append(code)
        
        # Find numbers in the context of currencies
        if currencies_found:
            # Use the most frequent currency
            if currencies_found:
                most_common_currency = max(set(currencies_found), key=currencies_found.count)
                
                # Look for amounts near the currency
                # Pattern for an amount followed by million/billion
                amount_pattern = r'([\d,.]+)\s*(?:million|billion|thousand|m\b|bn|k\b)?'
                
                # Look for currency code/symbol followed by amount
                for currency_code in set(currencies_found):
                    currency_amount_match = re.search(
                        r'\b' + currency_code + r'\s*' + amount_pattern, 
                        text, 
                        re.IGNORECASE
                    )
                    if currency_amount_match and not self._inside_lei(
                        currency_amount_match.start(), currency_amount_match.end(), lei_spans
                    ):
                        if not self._is_programme_context(
                            text,
                            currency_amount_match.start(),
                            currency_amount_match.end(),
                            currency_amount_match.group(0),
                        ):
                            amount = self._normalize_number(currency_amount_match.group(1))
                            amount = self._apply_multiplier(amount, currency_amount_match.group(0))
                            mapped = self._canonical_iso(currency_code) or self._map_symbol_to_code(currency_code)
                            return mapped, amount, None
                
                # Look for amount followed by currency code/symbol
                for currency_code in set(currencies_found):
                    amount_currency_match = re.search(
                        amount_pattern + r'\s*\b' + currency_code + r'\b', 
                        text, 
                        re.IGNORECASE
                    )
                    if amount_currency_match and not self._inside_lei(
                        amount_currency_match.start(), amount_currency_match.end(), lei_spans
                    ):
                        if not self._is_programme_context(
                            text,
                            amount_currency_match.start(),
                            amount_currency_match.end(),
                            amount_currency_match.group(0),
                        ):
                            amount = self._normalize_number(amount_currency_match.group(1))
                            amount = self._apply_multiplier(amount, amount_currency_match.group(0))
                            mapped = self._canonical_iso(currency_code) or self._map_symbol_to_code(currency_code)
                            return mapped, amount, None
                        
                # If we found currencies but no amounts directly associated,
                # return the most common currency but no amount
                mapped = self._canonical_iso(most_common_currency) or self._map_symbol_to_code(most_common_currency)
                return mapped, None, None
        
        # Last resort: just look for any number followed by million/billion
        million_billion_match = re.search(r'([\d,.]+)\s*(?:million|billion|m\b|bn\b)', text, re.IGNORECASE)
        if million_billion_match and not self._is_programme_context(
            text,
            million_billion_match.start(),
            million_billion_match.end(),
            million_billion_match.group(0),
        ):
            amount = self._normalize_number(million_billion_match.group(1))
            amount = self._apply_multiplier(amount, million_billion_match.group(0))
            
            return None, amount, None
        
        return None, None, None
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for currency extraction.
        
        Args:
            text: The text to normalize
            
        Returns:
            Normalized text
        """
        # Replace non-breaking spaces
        normalized = text.replace('\xa0', ' ')
        
        # Standardize spacing around currency symbols
        for symbol in ['$', '€', '£', '¥', 'Fr', 'kr', '₽', '₺', '₹', 'A$', 'C$', 'HK$', 'S$', 'NZ$']:
            normalized = re.sub(f'([{symbol}])\\s+', r'\1', normalized)
            normalized = re.sub(f'\\s+([{symbol}])', r'\1', normalized)
        
        # Standardize European number format (replace decimal comma with period)
        # Only for numbers with thousands separator as period
        normalized = re.sub(r'(\d+)\.(\d{3})(?:\.(\d{3}))?(?:,(\d+))?', lambda m: 
                         m.group(1) + m.group(2) + (m.group(3) or '') + ('.' + m.group(4) if m.group(4) else ''), 
                         normalized)
        
        return normalized
    
    def _normalize_number(self, num_str: str) -> str:
        """
        Normalize a number string by handling different formats.
        
        Args:
            num_str: The number string to normalize
            
        Returns:
            Normalized number string
        """
        if not num_str:
            return None
            
        # Handle European number format (dots as thousand separators, comma as decimal)
        if re.search(r'\d{1,3}(?:\.\d{3})+(?:,\d+)?', num_str):
            # Replace dots with nothing (remove thousand separators)
            num_str = re.sub(r'\.', '', num_str)
            # Replace comma with dot (convert decimal separator)
            num_str = re.sub(r',', '.', num_str)
        # Handle standard format with commas as thousand separators
        elif ',' in num_str and '.' not in num_str:
            # If we have commas but no dots, assume comma is a thousand separator
            num_str = re.sub(r',', '', num_str)
        # Handle both commas and dots (US/UK format)
        elif ',' in num_str and '.' in num_str:
            # Check if comma is thousand separator (typical US/UK format)
            if num_str.find(',') < num_str.find('.'):
                num_str = re.sub(r',', '', num_str)
            # Otherwise, might be European format with both
            else:
                num_str = re.sub(r'\.', '', num_str)
                num_str = re.sub(r',', '.', num_str)
                
        # Handle potential dash as decimal separator if others are absent
        if '-' in num_str and '.' not in num_str and ',' not in num_str:
             if re.search(r'\d-\d{3}', num_str): # Likely 4-000
                 num_str = num_str.replace('-', '.')
        
        # Remove any remaining non-numeric characters except decimal point
        num_str = re.sub(r'[^\d.]', '', num_str)
        
        # Ensure proper decimal format
        try:
            return str(float(num_str))
        except (ValueError, TypeError):
            return None
            
    def _apply_multiplier(self, num_str: str, context: str) -> str:
        """
        Apply multiplier (million, billion) to a number string.
        
        Args:
            num_str: The number string to apply multiplier to
            context: Context with potential multiplier mention
            
        Returns:
            Number string with multiplier applied
        """
        if not num_str:
            return None
            
        try:
            value = float(num_str)
            
            # Check for "million" multiplier
            if re.search(r'million|mn|mill\.?|m\b', context, re.IGNORECASE):
                value *= 1_000_000
            # Check for "billion" multiplier
            elif re.search(r'billion|bn|bill\.?|b\b', context, re.IGNORECASE):
                value *= 1_000_000_000
            # Check for "thousand" multiplier
            elif re.search(r'thousand|k\b', context, re.IGNORECASE):
                value *= 1_000
            # Check for "trillion" multiplier (rarer, but sometimes used)
            elif re.search(r'trillion|tn|trill\.?|t\b', context, re.IGNORECASE):
                value *= 1_000_000_000_000
                
            # Round to nearest whole number if value is large
            if value >= 1_000_000:
                return str(int(round(value)))
            else:
                # Keep decimal places for smaller values
                return str(value)
                
        except (ValueError, TypeError):
            return num_str
    
    def _map_symbol_to_code(self, symbol: str) -> Optional[str]:
        """
        Map currency symbol to currency code.
        
        Args:
            symbol: Currency symbol to map
            
        Returns:
            Currency code or None if not found
        """
        if not symbol:
            return None

        iso = self._canonical_iso(symbol)
        if iso:
            return iso
                
        # Map symbols and names to codes
        mapping = {
            '$': 'USD', '€': 'EUR', '£': 'GBP', '¥': 'JPY',
            'Fr': 'CHF', 'kr': 'NOK', '₽': 'RUB', '₺': 'TRY',
            'R': 'ZAR', '₹': 'INR', 'A$': 'AUD', 'C$': 'CAD',
            'HK$': 'HKD', 'S$': 'SGD', 'NZ$': 'NZD', '₦': 'NGN',
            '₱': 'PHP', '฿': 'THB', '₫': 'VND',
            'euro': 'EUR', 'euros': 'EUR', 'dollar': 'USD', 'dollars': 'USD',
            'pound': 'GBP', 'pounds': 'GBP', 'yen': 'JPY', 'franc': 'CHF'
        }
        
        lower_symbol = symbol.lower().strip()
        for key, code in mapping.items():
            if key in lower_symbol or key == lower_symbol:
                return code
                
        return None