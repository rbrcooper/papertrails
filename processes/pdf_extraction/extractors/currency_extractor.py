import re
import locale
from typing import Dict, Any, Optional, Tuple
from ..utils.pattern_registry import PatternRegistry
from .base_extractor import BaseExtractor

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
            
        # Extract currency and issue size
        currency, issue_size, issue_size_range = self._extract_issue_size_currency(normalized_text)
        
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
        
        # Set confidence based on available data
        if currency_info['currency'] and currency_info['issue_size']:
            currency_info['confidence'] = 'high'
        elif currency_info['currency'] or currency_info['issue_size']:
            currency_info['confidence'] = 'medium'
        else:
            currency_info['confidence'] = 'low'
        
        if self.debug_mode:
            print(f"CurrencyExtractor: Final results - currency: {currency_info['currency']}, issue_size: {currency_info['issue_size']}, confidence: {currency_info['confidence']}")
            
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
                        mapped = self._map_symbol_to_code(group)
                        if mapped:
                            currency = mapped
                            break
                
                # If no currency found in groups, search full_match
                if not currency:
                    # Check for explicit currency codes (e.g., USD, EUR)
                    for code in self.patterns['currency_codes']:
                        search_code = code.strip(r'\b')
                        if re.search(r'\b' + re.escape(search_code) + r'\b', full_match, re.IGNORECASE):
                            currency = search_code.upper()
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
                
                # Basic validation: ignore programme sizes if clearly marked
                if re.search(r'programme|limit|ceiling', full_match, re.IGNORECASE) or \
                   re.search(r'programme|limit|ceiling', text[max(0, match.start()-50):match.start()], re.IGNORECASE):
                    if self.debug_mode:
                        print(f"CurrencyExtractor: Skipping potential programme/limit match: {full_match}")
                    continue

                if currency and issue_size:
                    if self.debug_mode:
                        print(f"CurrencyExtractor: Successfully extracted currency {currency} and size {issue_size}")
                    return currency, issue_size, None # Could add range support back if needed
                    
            if self.debug_mode and match_count == 0:
                print(f"CurrencyExtractor: No matches for issue size pattern {i+1}")
        
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
            range_match = re.search(r'(?:between|from)?\s*(?:([A-Z]{3}|\$|€|£|¥))?\s*([\d,.]+)\s*(?:million|billion|m|bn)?\s*(?:and|to|-)\s*(?:([A-Z]{3}|\$|€|£|¥))?\s*([\d,.]+)\s*(?:million|billion|m|bn)?', text, re.IGNORECASE)
            if range_match:
                # Extract currency (prefer first occurrence, fallback to second)
                currency_symbol = range_match.group(1) or range_match.group(3)
                
                # Convert symbol to code if needed
                if currency_symbol and len(currency_symbol) == 1:
                    currency = self._map_symbol_to_code(currency_symbol)
                else:
                    currency = currency_symbol
                
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
                # Extract currency
                currency_part = match.group(1) if match.lastindex >= 1 else None
                
                # Handle currency codes vs. symbols
                if currency_part:
                    if len(currency_part) == 1 or currency_part in ['$', '€', '£', '¥']:
                        currency = self._map_symbol_to_code(currency_part)
                    else:
                        currency = currency_part
                
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
        currency_codes = self.patterns['currency_codes']
        currency_symbols = self.patterns['currency_symbols']
        
        # Find all currency mentions
        currencies_found = []
        for code in currency_codes:
            if re.search(r'\b' + code + r'\b', text, re.IGNORECASE):
                currencies_found.append(code)
        
        for symbol in currency_symbols:
            if re.search(symbol, text, re.IGNORECASE):
                # Map to code
                code = self._map_symbol_to_code(symbol)
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
                    if currency_amount_match:
                        amount = self._normalize_number(currency_amount_match.group(1))
                        amount = self._apply_multiplier(amount, currency_amount_match.group(0))
                        
                        return currency_code, amount, None
                
                # Look for amount followed by currency code/symbol
                for currency_code in set(currencies_found):
                    amount_currency_match = re.search(
                        amount_pattern + r'\s*\b' + currency_code + r'\b', 
                        text, 
                        re.IGNORECASE
                    )
                    if amount_currency_match:
                        amount = self._normalize_number(amount_currency_match.group(1))
                        amount = self._apply_multiplier(amount, amount_currency_match.group(0))
                        
                        return currency_code, amount, None
                        
                # If we found currencies but no amounts directly associated,
                # return the most common currency but no amount
                return most_common_currency, None, None
        
        # Last resort: just look for any number followed by million/billion
        million_billion_match = re.search(r'([\d,.]+)\s*(?:million|billion|m\b|bn\b)', text, re.IGNORECASE)
        if million_billion_match:
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
        for symbol in ['$', '€', '£', '¥', 'Fr', 'kr', '₽', '₺', 'R', '₹', 'A$', 'C$', 'HK$', 'S$', 'NZ$']:
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
            
        # Check if it's already a currency code
        for code in self.patterns['currency_codes']:
            if symbol.upper() == code:
                return code
                
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