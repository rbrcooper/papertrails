import re
import os
from typing import Dict, List, Any, Optional, Tuple
from ..utils.pattern_registry import PatternRegistry
from ..utils.text_processing import TextProcessor
from .base_extractor import BaseExtractor
from ...utils.bank_standardizer import BankStandardizer

class BankExtractor(BaseExtractor):
    """Extracts bank names and roles from text."""
    
    def __init__(self, text_processor: Optional[TextProcessor] = None, debug_mode: bool = False):
        """
        Initialize the bank extractor.
        
        Args:
            text_processor: Text processor instance for section extraction
            debug_mode: Enable debug prints
        """
        self.patterns = PatternRegistry.get_bank_patterns()
        self.text_processor = text_processor or TextProcessor()
        self.debug_mode = debug_mode # Set the debug_mode attribute
        
        # Calculate absolute path to bank_names.json
        current_dir = os.path.dirname(os.path.abspath(__file__))
        processes_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        bank_names_path = os.path.join(processes_dir, "data", "bank_names.json")
        
        # Initialize bank standardizer with absolute path
        self.bank_standardizer = BankStandardizer(bank_names_file=bank_names_path, debug_mode=self.debug_mode) # Pass debug_mode
        if self.debug_mode:
            if self.bank_standardizer.bank_data:
                print(f"BankExtractor: BankStandardizer initialized with {len(self.bank_standardizer.bank_data)} bank entries.")
            else:
                print("BankExtractor: BankStandardizer initialized with NO bank entries. Check bank_names.json.")
        
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
            # This will store the list of dicts as per prompt's standardized_banks
            'banks': [], 
            'bank_sections': {},
            # 'bank_info' might be deprecated or restructured if not needed by caller
            # For now, let's focus on getting 'banks' list correct.
            # We can still populate bank_info if other parts of system rely on it.
            'bank_info_debug': {} # Temp for preserving some old logic if needed for roles
        }
        
        if not text:
            return result
            
        sections = {}
        for section_type in ['distribution', 'management', 'stabilisation']:
            section = self.text_processor.find_section(text, section_type)
            if section:
                sections[section_type] = section
                
        if not sections:
            sections['full_text'] = text
            
        processed_standardized_banks = set() # To avoid duplicates in the final 'banks' list

        for section_name, section_text in sections.items():
            result['bank_sections'][section_name] = section_text
            bank_roles_in_section = self._find_bank_roles(section_text) # Renamed for clarity
            raw_extracted_banks = self._extract_banks(section_text) # Renamed for clarity
            
            for raw_bank_name in raw_extracted_banks:
                # Standardize using the updated BankStandardizer
                # The standardize_name method in BankStandardizer handles cleaning internally.
                standardization_output = self._standardize_bank_name(raw_bank_name)
                
                standardized_name = standardization_output['standardized_name']
                confidence = standardization_output['confidence']
                method = standardization_output['method']

                # Apply confidence threshold from prompt (Task 1.2)
                if confidence >= 0.85 and self.is_valid_bank_name(standardized_name): # also check validity
                    current_bank_roles = []
                    # Try to associate with roles found in this section
                    # This logic might need refinement to be more precise
                    context_for_roles = self._get_text_around(section_text, raw_bank_name, window=100)
                    for role in bank_roles_in_section:
                        if role in context_for_roles.lower(): # Check role in context of raw_bank_name
                            current_bank_roles.append(role)
                    
                    bank_entry = {
                        'raw_name': raw_bank_name,
                        'standardized_name': standardized_name,
                        'confidence': confidence,
                        'method': method,
                        'roles': list(set(current_bank_roles)), # Unique roles for this instance
                        'found_in_section': section_name
                    }

                    # Avoid adding exact duplicate entries (standardized_name + roles)
                    # A simpler check: add if standardized_name is new, or if new roles are found for existing name.
                    # The prompt for extract_banks just lists them. Let's handle complex merging later if needed.
                    # For now, ensure we don't add the *exact same bank_entry object* multiple times if a bank appears
                    # multiple times with the exact same details from the same extraction pass.
                    # A better approach might be to group by standardized_name and merge roles/raw_names.
                    
                    # Key for uniqueness check: standardized name + sorted roles string
                    unique_key = (standardized_name, tuple(sorted(bank_entry['roles'])))

                    is_existing = False
                    for i, existing_entry in enumerate(result['banks']):
                        if (existing_entry['standardized_name'] == standardized_name and
                            tuple(sorted(existing_entry['roles'])) == tuple(sorted(bank_entry['roles']))):
                            # Could update raw_names list or sections if needed, for now just mark as existing
                            is_existing = True
                            # Potentially merge raw_names or other fields if this new find is better
                            if len(raw_bank_name) < len(existing_entry['raw_name']):
                                result['banks'][i]['raw_name'] = raw_bank_name # Prefer shorter raw name for same std name
                            break
                    
                    if not is_existing:
                        result['banks'].append(bank_entry)
                        processed_standardized_banks.add(unique_key)
                elif self.debug_mode: # Added from my DateExtractor pattern
                    print(f"BankExtractor: Skipping bank '{raw_bank_name}' (std: '{standardized_name}') due to low confidence ({confidence:.2f}) or invalidity.")

        # The prompt wants extract_banks to return {'banks': standardized_banks, 'validation_flags': ...}
        # The current _extract_banks_and_roles returns a more complex dict. 
        # The main extract() method then processes this.
        # For now, let's ensure result['banks'] is correctly populated.
        # The 'validation_flags' part would be generated by a different component or needs new logic.
        # For now, only return what is calculable here.
        # The original result structure had 'extracted_banks', 'bank_sections', 'bank_info'.
        # We have populated result['banks'] and result['bank_sections'].
        # We'll simplify the return of this specific method to be closer to the prompt's example
        # for `extract_banks` if it's the final step for this data.
        # However, the calling `extract` method expects a certain structure.
        
        # Let's adapt the old `result['extracted_banks']` to the new format.
        # The old `result['bank_info']` needs to be reviewed based on new `result['banks']`
        # The prompt structure `{'banks': standardized_banks}` is simple.
        # Current `extract` returns `_extract_banks_and_roles` directly.
        # So, the output of THIS function becomes the main output for bank extraction.
        
        final_output = {
            'banks': result['banks'], 
            'bank_sections_debug': result['bank_sections'], 
            'validation_flags': self._generate_validation_flags(result['banks'])
        }
        return final_output

    def _generate_validation_flags(self, standardized_banks: List[Dict[str, Any]]) -> List[str]:
        """ Generates basic validation flags based on standardized banks. """
        flags = []
        if not standardized_banks:
            flags.append("no_banks_extracted_or_confident_enough")
        
        low_confidence_count = sum(1 for bank in standardized_banks if bank['confidence'] < 0.90) # Example threshold
        if standardized_banks and low_confidence_count == len(standardized_banks):
            flags.append("all_extracted_banks_have_low_confidence")
        elif low_confidence_count > 0:
            flags.append(f"{low_confidence_count}_banks_with_low_confidence")
            
        # Add more validation flags as needed
        return flags
    
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
        
        # Keep the basic cleaning here for backward compatibility
        # The more sophisticated standardization is done by standardize_bank_name
        
        return cleaned
    
    def _standardize_bank_name(self, bank_name: str) -> Dict[str, Any]:
        """Standardize a single bank name using the BankStandardizer."""
        if not self.bank_standardizer:
            self.logger.warning("BankStandardizer not initialized. Returning raw name.")
            return {
                'standardized_name': bank_name,
                'confidence': 0.0,
                'method': 'no_standardizer'
            }
        # Corrected method call
        return self.bank_standardizer.standardize_name(bank_name)
    
    def is_valid_bank_name(self, bank: str) -> bool:
        """
        Check if a string is likely to be a valid bank name.
        
        Args:
            bank: The bank name to check
            
        Returns:
            True if likely a valid bank name, False otherwise
        """
        if not bank or len(bank.strip()) < 3:
            return False
            
        # Check for common terms that are not banks
        common_terms = [
            r'\b(?:page|terms|size|amount|total|date|final|interest|reference|rate|notes)\b', 
            r'\b(?:issuer|issue|maturity|coupon|annex|section|document|prospectus)\b',
            r'\b(?:number|code|identifier|id|isin|cusip|lei)\b'
        ]
        
        for term in common_terms:
            if re.search(term, bank, re.IGNORECASE):
                return False
                
        # Check for too many words (banks usually have 1-5 words)
        word_count = len(bank.split())
        if word_count > 6:
            return False
            
        # Check for mostly numbers or symbols
        alphachars = sum(c.isalpha() for c in bank)
        if alphachars < len(bank) * 0.5:
            return False
            
        # Check if standardizer recognizes this as a bank
        standardized = self._standardize_bank_name(bank)
        if standardized is not None:
            return True
            
        # Otherwise, use heuristics
        return True 

    def _post_process_banks(self, extracted_banks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Post-process extracted bank names to standardize and add confidence."""
        # Implementation of _post_process_banks method
        # ...