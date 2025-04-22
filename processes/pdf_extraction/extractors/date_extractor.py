import re
from datetime import datetime
from typing import Dict, Optional
from ..utils.pattern_registry import PatternRegistry
from .base_extractor import BaseExtractor

class DateExtractor(BaseExtractor):
    """Extracts issue date and maturity date information."""
    
    def __init__(self):
        """Initialize the date extractor."""
        self.patterns = PatternRegistry.get_date_patterns()
        
    def extract(self, text: str) -> Dict[str, Optional[str]]:
        """
        Extract date information from text.
        
        Args:
            text: The text to extract dates from
            
        Returns:
            Dictionary with issue_date and maturity_date keys
        """
        date_info = {'issue_date': None, 'maturity_date': None}
        
        if not text:
            return date_info
            
        # Normalize text for easier processing
        normalized_text = self._normalize_text(text)
        
        # Extract issue date
        for pattern in self.patterns['issue_date']:
            match = re.search(pattern, normalized_text, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                parsed_date = self._parse_date_string(date_str)
                if parsed_date:
                    date_info['issue_date'] = parsed_date.strftime('%Y-%m-%d')
                    break
        
        # Extract maturity date
        for pattern in self.patterns['maturity_date']:
            match = re.search(pattern, normalized_text, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                parsed_date = self._parse_date_string(date_str)
                if parsed_date:
                    date_info['maturity_date'] = parsed_date.strftime('%Y-%m-%d')
                    break
        
        return date_info
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for date extraction.
        
        Args:
            text: The text to normalize
            
        Returns:
            Normalized text
        """
        # Replace various separator characters with a standard one
        normalized = re.sub(r'[/\\\-\.]', '-', text)
        
        # Replace ordinal indicators
        normalized = re.sub(r'(\d+)(?:st|nd|rd|th)', r'\1', normalized)
        
        return normalized
    
    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        """
        Parse a date string into a datetime object.
        
        Args:
            date_str: The date string to parse
            
        Returns:
            Parsed datetime object or None if parsing failed
        """
        if not date_str:
            return None
            
        try:
            # Try common date formats
            formats = [
                '%d-%m-%Y', '%d-%m-%y', '%m-%d-%Y', '%m-%d-%y',
                '%Y-%m-%d', '%y-%m-%d',
                '%d %B %Y', '%d %b %Y', '%B %d %Y', '%b %d %Y',
                '%d %B, %Y', '%d %b, %Y', '%B %d, %Y', '%b %d, %Y'
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            # Try to handle more complex cases
            # Replace month names with numbers
            month_map = {
                'january': '1', 'february': '2', 'march': '3', 'april': '4',
                'may': '5', 'june': '6', 'july': '7', 'august': '8',
                'september': '9', 'october': '10', 'november': '11', 'december': '12',
                'jan': '1', 'feb': '2', 'mar': '3', 'apr': '4',
                'jun': '6', 'jul': '7', 'aug': '8', 'sep': '9', 'oct': '10', 'nov': '11', 'dec': '12'
            }
            
            date_lower = date_str.lower()
            for month_name, month_num in month_map.items():
                if month_name in date_lower:
                    # Extract day and year
                    day_year_parts = re.sub(month_name, '', date_lower).strip()
                    day_match = re.search(r'(\d{1,2})', day_year_parts)
                    year_match = re.search(r'(\d{2,4})', day_year_parts)
                    
                    if day_match and year_match:
                        day = day_match.group(1)
                        year = year_match.group(1)
                        
                        # Standardize 2-digit years
                        if len(year) == 2:
                            year = '20' + year if int(year) < 50 else '19' + year
                            
                        # Create a standardized date string
                        standardized = f"{day.zfill(2)}-{month_num.zfill(2)}-{year}"
                        return datetime.strptime(standardized, '%d-%m-%Y')
            
            return None
                    
        except Exception:
            return None 