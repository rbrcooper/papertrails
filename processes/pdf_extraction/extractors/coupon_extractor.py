import re
from typing import Dict, Any, Optional
from ..utils.pattern_registry import PatternRegistry
from .base_extractor import BaseExtractor

class CouponExtractor(BaseExtractor):
    """Extracts coupon rate and type information."""
    
    def __init__(self):
        """Initialize the coupon extractor."""
        self.patterns = PatternRegistry.get_coupon_patterns()
        
    def extract(self, text: str) -> Dict[str, Any]:
        """
        Extract coupon information from text.
        
        Args:
            text: The text to extract coupon information from
            
        Returns:
            Dictionary with coupon_rate and coupon_type keys
        """
        coupon_info = {
            'coupon_rate': None,
            'coupon_type': None
        }
        
        if not text:
            return coupon_info
            
        # Extract coupon rate and type
        coupon_rate, coupon_type = self._extract_coupon(text)
        
        if coupon_rate:
            coupon_info['coupon_rate'] = coupon_rate
            
        if coupon_type:
            coupon_info['coupon_type'] = coupon_type
            
        return coupon_info
        
    def _extract_coupon(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """
        Extract coupon rate and type from text.
        
        Args:
            text: The text to extract from
            
        Returns:
            A tuple of (coupon_rate, coupon_type)
        """
        if not text:
            return None, None
            
        # Normalize text for easier processing
        normalized_text = self._normalize_text(text)
        
        # Find coupon rate
        coupon_rate = None
        for pattern in self.patterns['coupon_rate']:
            matches = re.finditer(pattern, normalized_text, re.IGNORECASE)
            for match in matches:
                rate_str = match.group(1)
                try:
                    # Validate that we have a proper rate
                    rate = float(rate_str)
                    if 0 <= rate <= 20:  # Reasonable rate range
                        coupon_rate = rate_str
                        break
                except ValueError:
                    continue
            if coupon_rate:
                break
                
        # Find coupon type
        coupon_type = None
        for pattern in self.patterns['coupon_types']:
            if re.search(pattern, normalized_text, re.IGNORECASE):
                # Extract the matching type
                match = re.search(pattern, normalized_text, re.IGNORECASE)
                if match:
                    coupon_type = match.group(0).strip().lower()
                    # Standardize type format
                    coupon_type = re.sub(r'\s+', ' ', coupon_type)
                    break
        
        # If we found a rate but no type, assume it's fixed rate
        if coupon_rate and not coupon_type:
            coupon_type = "fixed rate"
            
        # Special case: if we find 'zero coupon' or similar, set rate to '0'
        if not coupon_rate and coupon_type and 'zero' in coupon_type:
            coupon_rate = '0'
            
        return coupon_rate, coupon_type
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for coupon extraction.
        
        Args:
            text: The text to normalize
            
        Returns:
            Normalized text
        """
        # Replace variations in percentage notation
        normalized = re.sub(r'per\s*cent\.?', '%', text)
        normalized = re.sub(r'percent', '%', normalized)
        
        # Standardize spacing around percentage symbol
        normalized = re.sub(r'\s+%', '%', normalized)
        
        # Replace decimal separators if needed
        normalized = re.sub(r'(\d+),(\d+)', r'\1.\2', normalized)
        
        return normalized 