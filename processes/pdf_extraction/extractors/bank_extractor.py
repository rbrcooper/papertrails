import re
from typing import Dict, List, Any, Optional
from ..utils.pattern_registry import PatternRegistry
from ..utils.text_processing import TextProcessor
from .base_extractor import BaseExtractor

class BankExtractor(BaseExtractor):
    """Extracts bank names and roles from text."""
    
    def __init__(self, text_processor: Optional[TextProcessor] = None):
        """
        Initialize the bank extractor.
        
        Args:
            text_processor: Text processor instance for section extraction
        """
        self.patterns = PatternRegistry.get_bank_patterns()
        self.text_processor = text_processor or TextProcessor()
        
    def extract(self, text: str) -> Dict[str, Any]:
        """
        Extract bank information from text.
        
        Args:
            text: The text to extract banks and roles from
            
        Returns:
            Dictionary with extracted_banks, bank_sections, etc.
        """
        if not text:
            return {
                'extracted_banks': [],
                'bank_sections': {}
            }
            
        # Extract bank information from the text
        return self._extract_banks_and_roles(text)
    
    def _extract_banks_and_roles(self, text: str) -> Dict[str, Any]:
        """
        Extract banks and their roles from text.
        
        Args:
            text: The text to extract from
            
        Returns:
            Dictionary with extracted banks and related information
        """
        result = {
            'extracted_banks': [],
            'bank_sections': {},
            'bank_info': {}
        }
        
        if not text:
            return result
            
        # Find relevant sections in the text
        sections = {}
        for section_type in ['distribution', 'management', 'stabilisation']:
            section = self.text_processor.find_section(text, section_type)
            if section:
                sections[section_type] = section
                
        # If no specific sections found, use the entire text
        if not sections:
            sections['full_text'] = text
            
        # Process each section
        for section_name, section_text in sections.items():
            result['bank_sections'][section_name] = section_text
            
            # Find bank roles in the section
            bank_roles = self._find_bank_roles(section_text)
            
            # Find banks in the section
            extracted_banks = self._extract_banks(section_text)
            
            # Associate banks with roles
            for bank in extracted_banks:
                cleaned_bank = self.clean_bank_name(bank)
                if cleaned_bank and self.is_valid_bank_name(cleaned_bank):
                    if cleaned_bank not in result['bank_info']:
                        result['bank_info'][cleaned_bank] = {
                            'roles': [],
                            'sections': []
                        }
                    
                    # Add section to bank info
                    if section_name not in result['bank_info'][cleaned_bank]['sections']:
                        result['bank_info'][cleaned_bank]['sections'].append(section_name)
                    
                    # Try to associate with roles
                    for role in bank_roles:
                        role_text = self._get_text_around(section_text, bank, 100)
                        if role in role_text.lower():
                            if role not in result['bank_info'][cleaned_bank]['roles']:
                                result['bank_info'][cleaned_bank]['roles'].append(role)
                    
                    # Add to extracted banks list if not already there
                    if cleaned_bank not in result['extracted_banks']:
                        result['extracted_banks'].append(cleaned_bank)
        
        return result
    
    def _find_bank_roles(self, text: str) -> List[str]:
        """
        Find bank roles mentioned in the text.
        
        Args:
            text: The text to search in
            
        Returns:
            List of bank roles found
        """
        roles = []
        for pattern in self.patterns['bank_roles']:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                role = match.group(0).lower().strip()
                if role and role not in roles:
                    roles.append(role)
        return roles
    
    def _extract_banks(self, text: str) -> List[str]:
        """
        Extract bank names from text.
        
        Args:
            text: The text to extract banks from
            
        Returns:
            List of bank names
        """
        banks = []
        
        # Look for common bank names
        for pattern in self.patterns['common_banks']:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                bank = match.group(0)
                if bank and bank not in banks:
                    banks.append(bank)
        
        # Look for potential banks near role indicators
        for role_pattern in self.patterns['bank_roles']:
            matches = re.finditer(role_pattern, text, re.IGNORECASE)
            for match in matches:
                role_pos = match.start()
                
                # Look for entity names around the role
                context = self._get_text_around(text, match.group(0), 100)
                lines = context.split('\n')
                
                for line in lines:
                    # Skip lines that are too short
                    if len(line.strip()) < 3:
                        continue
                        
                    # Skip lines that are clearly not bank names
                    if re.search(r'\b(?:Notes|Securities|Bonds|Issuer|Issue|Maturity|Coupon|Rate|if|and|or|the|dated|will)\b', line, re.IGNORECASE):
                        continue
                        
                    # Look for capitalized words that could be bank names
                    potential_banks = re.findall(r'\b[A-Z][a-zA-Z\s&\']+(?:\([^)]+\))?\b', line)
                    for bank in potential_banks:
                        # Skip common non-bank terms
                        if re.search(r'\b(?:Page|Terms|Size|Amount|Total|Date|Final|Interest|Reference|Rate)\b', bank):
                            continue
                            
                        if bank and bank not in banks:
                            banks.append(bank)
        
        return banks
    
    def _get_text_around(self, text: str, target: str, window: int = 50) -> str:
        """
        Get text around a target string.
        
        Args:
            text: The text to search in
            target: The target string to find
            window: Number of characters to include before and after
            
        Returns:
            Text around the target
        """
        if not text or not target:
            return ""
            
        # Find the target in the text
        text_lower = text.lower()
        target_lower = target.lower()
        
        start_idx = text_lower.find(target_lower)
        if start_idx == -1:
            return ""
            
        # Calculate start and end positions
        start_pos = max(0, start_idx - window)
        end_pos = min(len(text), start_idx + len(target) + window)
        
        return text[start_pos:end_pos]
    
    def clean_bank_name(self, bank: str) -> str:
        """
        Clean a bank name by removing noise and standardizing format.
        
        Args:
            bank: The bank name to clean
            
        Returns:
            Cleaned bank name
        """
        if not bank:
            return ""
            
        # Remove common suffixes and qualifiers
        cleaned = re.sub(r'\s+(?:AG|plc|ltd|limited|inc|incorporated|llc|gmbh|sa|corp|corporation|group|s\.?[ap]\.?|n\.?v\.?|[&,]?\s+co(?:mpany)?)\.?$', '', bank, flags=re.IGNORECASE)
        
        # Remove common prefixes
        cleaned = re.sub(r'^(?:the|by)\s+', '', cleaned, flags=re.IGNORECASE)
        
        # Normalize spaces
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Standard name replacements
        replacements = {
            'j.p. morgan': 'JPMorgan',
            'j. p. morgan': 'JPMorgan',
            'jp morgan': 'JPMorgan',
            'jpmorgan chase': 'JPMorgan',
            'bank of america merrill lynch': 'Bank of America',
            'bofa': 'Bank of America',
            'bofa securities': 'Bank of America',
            'barclays capital': 'Barclays',
            'bnp': 'BNP Paribas',
            'socgen': 'Societe Generale',
            'société générale': 'Societe Generale',
            'deutsche': 'Deutsche Bank',
            'ubs ag': 'UBS',
            'rbc capital': 'RBC',
            'rbc capital markets': 'RBC',
            'royal bank of canada': 'RBC'
        }
        
        # Check for name standardization
        cleaned_lower = cleaned.lower()
        for old, new in replacements.items():
            if cleaned_lower == old or cleaned_lower.startswith(old + ' '):
                return new
                
        return cleaned
        
    def is_valid_bank_name(self, bank: str) -> bool:
        """
        Check if a string is likely a valid bank name.
        
        Args:
            bank: The bank name to check
            
        Returns:
            True if likely a valid bank name, False otherwise
        """
        if not bank or len(bank) < 3:
            return False
            
        # Check for common non-bank terms that might be mistaken for banks
        invalid_terms = [
            'issuer', 'notes', 'bonds', 'securities', 'issue date', 'maturity date',
            'interest rate', 'coupon', 'form', 'date', 'page', 'terms', 'conditions',
            'final terms', 'base prospectus', 'offering', 'offer', 'document', 'series',
            'rating', 'summary', 'financial', 'amount', 'size', 'currency'
        ]
        
        bank_lower = bank.lower()
        for term in invalid_terms:
            if term == bank_lower or f"{term}s" == bank_lower:
                return False
                
        # Check against common bank patterns for higher confidence
        for pattern in self.patterns['common_banks']:
            if re.search(pattern, bank, re.IGNORECASE):
                return True
                
        # Additional checks for likely bank names
        # Common bank endings
        if re.search(r'(?:bank|capital|securities|asset|credit|invest|partners|financial|markets)$', bank_lower):
            return True
            
        # Has multiple capitalized words (like "Bank of America")
        if re.search(r'^[A-Z][a-z]+(?:\s+(?:of|and|&)\s+[A-Z][a-z]+)+$', bank):
            return True
            
        # Default to accepting strings that look like proper names
        return re.search(r'^[A-Z][a-zA-Z\s&\']+$', bank) is not None 