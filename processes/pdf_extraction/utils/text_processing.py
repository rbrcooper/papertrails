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
        Extract document sections from text.
        
        Args:
            text: The text to extract sections from
            
        Returns:
            Dictionary mapping section names to section text
        """
        if not text:
            return {}
        
        # List of section patterns to match against
        section_patterns = [
            # Numbered section headers (e.g., "1. Introduction")
            r'(?:^|\n)(\d+\.\s+[A-Z][A-Za-z\s]+)(?:\n|:|$)',
            
            # Capital letter section headers (e.g., "INTRODUCTION")
            r'(?:^|\n)([A-Z][A-Z\s]{3,}:?)(?:\n|:|$)',
            
            # Title case section headers (e.g., "Summary of Terms")
            r'(?:^|\n)([A-Z][a-zA-Z\s]+:)(?:\n|:|$)',
            
            # Specific financial sections
            r'(?:^|\n)((?:Final )?Terms and Conditions:?)(?:\n|:|$)',
            r'(?:^|\n)(Issuer?:?)(?:\n|:|$)',
            r'(?:^|\n)(Issue Size:?)(?:\n|:|$)',
            r'(?:^|\n)(Issue Date:?)(?:\n|:|$)',
            r'(?:^|\n)(Maturity Date:?)(?:\n|:|$)',
            r'(?:^|\n)(Coupon:?)(?:\n|:|$)',
            r'(?:^|\n)(Interest:?)(?:\n|:|$)',
            r'(?:^|\n)(Redemption:?)(?:\n|:|$)',
            r'(?:^|\n)(Lead Manager:?)(?:\n|:|$)',
            r'(?:^|\n)(Book Runner:?)(?:\n|:|$)',
            r'(?:^|\n)(Arranger:?)(?:\n|:|$)',
        ]
        
        # Extract section headers and their positions
        sections = []
        for pattern in section_patterns:
            for match in re.finditer(pattern, text, re.MULTILINE):
                section_title = match.group(1).strip()
                start_pos = match.start()
                sections.append((start_pos, section_title))
        
        # Sort sections by their position in the text
        sections.sort(key=lambda x: x[0])
        
        # If no sections were found, return the whole text as one section
        if not sections:
            return {'Document': text}
        
        # Extract section content
        result = {}
        for i in range(len(sections)):
            start_pos = sections[i][0]
            section_title = sections[i][1]
            
            # For the last section, content goes to end of text
            if i == len(sections) - 1:
                section_content = text[start_pos:].strip()
            else:
                # Otherwise, content goes until next section
                end_pos = sections[i + 1][0]
                section_content = text[start_pos:end_pos].strip()
            
            # Remove the section title from the content if it starts with it
            if section_content.startswith(section_title):
                section_content = section_content[len(section_title):].strip()
            
            # Normalize section titles to remove potential duplicates
            normalized_title = section_title.replace(':', '').strip()
            
            # Handle duplicate section names by appending a number
            base_title = normalized_title
            counter = 1
            while normalized_title in result:
                normalized_title = f"{base_title} ({counter})"
                counter += 1
            
            result[normalized_title] = section_content
        
        # Add special summary section for top of document (first 10% of text)
        summary_length = max(min(len(text) // 10, 5000), 1000)  # Between 1000-5000 chars
        if summary_length < len(text):
            result['Summary'] = text[:summary_length].strip()
        
        return result

    def extract_paragraphs(self, text: str) -> List[str]:
        """
        Extract paragraphs from text.
        
        Args:
            text: The text to extract paragraphs from
            
        Returns:
            List of paragraphs
        """
        if not text:
            return []
        
        # Split text into paragraphs
        paragraphs = re.split(r'\n\s*\n', text)
        
        # Clean paragraphs
        cleaned_paragraphs = []
        for para in paragraphs:
            para = para.strip()
            if para and len(para) > 10:  # Ignore very short paragraphs
                cleaned_paragraphs.append(para)
            
        return cleaned_paragraphs 