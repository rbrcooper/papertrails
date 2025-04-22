import re
from typing import Dict, List, Optional

class TextProcessor:
    """Utility class for text processing operations."""
    
    def __init__(self):
        """Initialize the text processor."""
        # Common section markers
        self.section_markers = {
            'distribution': [
                r'\b(?:plan\s+of\s+)?distribution\b',
                r'\bsubscription\s+and\s+sale\b',
                r'\bplacement\s+of\s+the\s+notes\b'
            ],
            'management': [
                r'\bmanagers?\b',
                r'\bjoint\s+lead\s+managers?\b',
                r'\bbook(?:\-)?runners?\b'
            ],
            'stabilisation': [
                r'\bstabili[sz]ing\s+managers?\b',
                r'\bstabili[sz]ation\s+managers?\b',
                r'\bstabili[sz]ation\b'
            ]
        }
    
    def clean_text(self, text: str) -> str:
        """
        Clean text by removing extra whitespace and normalizing line breaks.
        
        Args:
            text: The text to clean
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
            
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove unwanted characters
        text = re.sub(r'[^\x00-\x7F]+', '', text)
        
        return text.strip()
    
    def find_section(self, text: str, start_marker: str, end_marker: str = None) -> Optional[str]:
        """
        Find a section between start and end markers.
        
        Args:
            text: The text to search in
            start_marker: The marker indicating the start of the section
            end_marker: Optional marker indicating the end of the section
            
        Returns:
            The extracted section or None if not found
        """
        # Implementation based on the original find_section method
        if not text or not start_marker:
            return None
            
        text_lower = text.lower()
        start_marker_lower = start_marker.lower()
        
        # Find the best matching section header
        start_idx = -1
        
        # Check for section type and use appropriate patterns
        if any(var in start_marker_lower for var in ['distribution', 'subscription', 'placement', 'sale']):
            for pattern in self.section_markers['distribution']:
                matches = list(re.finditer(pattern, text_lower))
                if matches:
                    start_idx = matches[0].start()
                    break
        elif any(var in start_marker_lower for var in ['manager', 'book', 'lead', 'underwriter']):
            for pattern in self.section_markers['management']:
                matches = list(re.finditer(pattern, text_lower))
                if matches:
                    start_idx = matches[0].start()
                    break
        else:
            # Default case - direct search
            start_idx = text_lower.find(start_marker_lower)
        
        if start_idx == -1:
            return None
            
        # Find the end of the section
        end_idx = len(text)
        
        if end_marker:
            end_marker_lower = end_marker.lower()
            temp_end_idx = text_lower.find(end_marker_lower, start_idx + len(start_marker))
            if temp_end_idx != -1:
                end_idx = temp_end_idx
        
        # Extract the section
        section = text[start_idx:end_idx].strip()
        return section if section else None
    
    def extract_sections(self, text: str) -> Dict[str, str]:
        """
        Extract standard sections from text.
        
        Args:
            text: The text to extract sections from
            
        Returns:
            Dictionary with section names as keys and extracted text as values
        """
        sections = {}
        
        # Extract standard sections
        sections['distribution'] = self.find_section(text, 'distribution', 'stabilization')
        sections['management'] = self.find_section(text, 'managers', 'stabilization')
        sections['stabilisation'] = self.find_section(text, 'stabilization', 'listing')
        
        # Remove None values
        return {k: v for k, v in sections.items() if v} 