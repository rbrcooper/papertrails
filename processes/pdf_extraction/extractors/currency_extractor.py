import re
from typing import Dict, Any, Optional
from ..utils.pattern_registry import PatternRegistry
from .base_extractor import BaseExtractor

class CurrencyExtractor(BaseExtractor):
    """Extracts issue size and currency information."""
    
    def __init__(self):
        """Initialize the currency extractor."""
        self.patterns = PatternRegistry.get_currency_patterns()
        
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
            'currency': None
        }
        
        if not text:
            return currency_info
            
        # Extract currency and issue size
        currency, issue_size = self._extract_issue_size_currency(text)
        
        if currency:
            currency_info['currency'] = currency
            
        if issue_size:
            currency_info['issue_size'] = issue_size
            
        # If primary extraction failed, try a simpler approach
        if not currency or not issue_size:
            simple_currency, simple_size = self._extract_simple_currency_amount(text)
            
            if not currency_info['currency'] and simple_currency:
                currency_info['currency'] = simple_currency
                
            if not currency_info['issue_size'] and simple_size:
                currency_info['issue_size'] = simple_size
        
        return currency_info
        
    def _extract_issue_size_currency(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """
        Extract issue size and currency from text.
        
        Args:
            text: The text to extract from
            
        Returns:
            A tuple of (currency, issue_size)
        """
        if not text:
            return None, None
            
        # Normalize text
        text = self._normalize_text(text)
        
        # Try to find currency and issue size using patterns
        for pattern in self.patterns['issue_size']:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Extract the full match to analyze
                full_match = match.group(0)
                
                # Extract currency symbol or code
                currency = None
                for currency_pattern in self.patterns['currency_codes']:
                    if re.search(r'\b' + currency_pattern + r'\b', full_match, re.IGNORECASE):
                        currency = currency_pattern
                        break
                        
                if not currency:
                    for idx, group in enumerate(match.groups()):
                        if group and any(re.search(pattern, group) for pattern in self.patterns['currency_symbols']):
                            # Map currency symbol to code
                            symbol_map = {
                                '$': 'USD', '€': 'EUR', '£': 'GBP', '¥': 'JPY',
                                'Fr': 'CHF', 'kr': 'NOK', '₽': 'RUB', '₺': 'TRY',
                                'R': 'ZAR', '₹': 'INR'
                            }
                            for symbol, code in symbol_map.items():
                                if symbol in group:
                                    currency = code
                                    break
                            break
                
                # Extract issue size
                issue_size = None
                # Find numbers in the match
                size_match = re.search(r'([\d,.]+)\s*(?:million|billion|m|bn)?', full_match)
                if size_match:
                    issue_size = size_match.group(1).replace(',', '')
                    # Check for million/billion multiplier
                    if 'billion' in full_match or 'bn' in full_match:
                        try:
                            issue_size = str(float(issue_size) * 1000000000)
                        except ValueError:
                            pass
                    elif 'million' in full_match or 'm' in full_match:
                        try:
                            issue_size = str(float(issue_size) * 1000000)
                        except ValueError:
                            pass
                
                if currency or issue_size:
                    return currency, issue_size
        
        return None, None
    
    def _extract_simple_currency_amount(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """
        Try a simpler approach to extract currency and amount when the standard patterns fail.
        
        Args:
            text: The text to extract from
            
        Returns:
            A tuple of (currency, issue_size)
        """
        # Look for common phrases typically containing issue size
        amount_phrases = [
            r'(?:aggregate\s+nominal\s+amount|issue\s+size|amount\s+of\s+the\s+notes|total\s+issue\s+size)\s*[:]\s*([A-Z]{3}|\$|€|£|¥)?\s*([\d,\.]+)\s*(?:million|billion|m|bn)?',
            r'(?:issue\s+of|issuance\s+of)\s*([A-Z]{3}|\$|€|£|¥)?\s*([\d,\.]+)\s*(?:million|billion|m|bn)?',
            r'(?:principal\s+amount)\s*[:]\s*([A-Z]{3}|\$|€|£|¥)?\s*([\d,\.]+)\s*(?:million|billion|m|bn)?',
            r'nominal\s+amount\s*[:]\s*(?:\([^\)]+\)\s*)?([A-Z]{3}|\$|€|£|¥)?\s*([\d,\.]+)\s*(?:million|billion|m|bn)?',
            r'([A-Z]{3}|\$|€|£|¥)\s*([\d,\.]+)\s*(?:million|billion|m|bn)?\s*(?:\d{1,2}[\.]\d{1,3})?\s*%\s*(?:notes|bonds)'
        ]
        
        # Check for these patterns
        for pattern in amount_phrases:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                groups = match.groups()
                if len(groups) >= 2:
                    currency_symbol = groups[0]
                    amount = groups[1].replace(',', '')
                    
                    # Convert the amount if it has a multiplier
                    match_text = match.group(0).lower()
                    if 'billion' in match_text or 'bn' in match_text:
                        try:
                            amount = str(float(amount) * 1000000000)
                        except ValueError:
                            pass
                    elif 'million' in match_text or 'm' in match_text:
                        try:
                            amount = str(float(amount) * 1000000)
                        except ValueError:
                            pass
                    
                    # Map currency symbol to code if needed
                    currency = None
                    if currency_symbol:
                        symbol_map = {
                            '$': 'USD', '€': 'EUR', '£': 'GBP', '¥': 'JPY',
                            'Fr': 'CHF', 'kr': 'NOK', '₽': 'RUB', '₺': 'TRY',
                            'R': 'ZAR', '₹': 'INR'
                        }
                        
                        # Check if it's already a currency code
                        for code in self.patterns['currency_codes']:
                            if currency_symbol.upper() == code:
                                currency = code
                                break
                                
                        # If not, check if it's a symbol
                        if not currency:
                            for symbol, code in symbol_map.items():
                                if symbol in currency_symbol:
                                    currency = code
                                    break
                    
                    # If we found an amount but no currency, look for currency mentions nearby
                    if amount and not currency:
                        # Look for currency in surrounding context (50 chars before and after)
                        context_start = max(0, match.start() - 50)
                        context_end = min(len(text), match.end() + 50)
                        context = text[context_start:context_end]
                        
                        # Check for currency codes in context
                        for code in self.patterns['currency_codes']:
                            if re.search(r'\b' + code + r'\b', context, re.IGNORECASE):
                                currency = code
                                break
                    
                    # Return the results if we found something
                    if amount or currency:
                        return currency, amount
        
        # Special case for "Euro Medium Term Note Programme" which often includes the programme size
        euro_mtn_match = re.search(r'([\d,\.]+)\s*(?:billion|bn|million|m)?\s+Euro\s+Medium\s+Term\s+Note\s+Programme', text, re.IGNORECASE)
        if euro_mtn_match:
            amount = euro_mtn_match.group(1).replace(',', '')
            # Apply multiplier
            match_text = euro_mtn_match.group(0).lower()
            if 'billion' in match_text or 'bn' in match_text:
                try:
                    amount = str(float(amount) * 1000000000)
                except ValueError:
                    pass
            elif 'million' in match_text or 'm' in match_text:
                try:
                    amount = str(float(amount) * 1000000)
                except ValueError:
                    pass
            return 'EUR', amount
            
        return None, None
        
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
        for symbol in ['$', '€', '£', '¥', 'Fr', 'kr', '₽', '₺', 'R', '₹']:
            normalized = re.sub(f'([{symbol}])\\s+', r'\1', normalized)
            normalized = re.sub(f'\\s+([{symbol}])', r'\1', normalized)
        
        return normalized 