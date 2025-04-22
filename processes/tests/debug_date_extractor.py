from processes.pdf_extractor import PDFExtractor
from processes.pdf_extraction.extractors.date_extractor import DateExtractor
from processes.pdf_extraction.utils.pattern_registry import PatternRegistry
import re

def debug_date_extraction(pdf_path):
    print(f"Debugging date extraction for: {pdf_path}")
    extractor = PDFExtractor()
    
    # Extract the raw text
    text = extractor.extract_text(pdf_path)
    print(f"Raw text length: {len(text)} characters")
    
    # Get date patterns from registry
    patterns = PatternRegistry.get_date_patterns()
    
    # Test each pattern against the text
    print("\nTesting issue date patterns:")
    for i, pattern in enumerate(patterns['issue_date']):
        matches = re.finditer(pattern, text, re.IGNORECASE)
        match_list = list(matches)
        if match_list:
            print(f"  Pattern {i+1}: {len(match_list)} matches")
            for j, match in enumerate(match_list[:3]):  # Show max 3 matches per pattern
                date_str = match.group(1).strip()
                context = text[max(0, match.start() - 30):min(len(text), match.end() + 30)]
                print(f"    Match {j+1}: '{date_str}' in context: '...{context}...'")
        else:
            print(f"  Pattern {i+1}: No matches")
    
    print("\nTesting maturity date patterns:")
    for i, pattern in enumerate(patterns['maturity_date']):
        matches = re.finditer(pattern, text, re.IGNORECASE)
        match_list = list(matches)
        if match_list:
            print(f"  Pattern {i+1}: {len(match_list)} matches")
            for j, match in enumerate(match_list[:3]):  # Show max 3 matches per pattern
                date_str = match.group(1).strip()
                context = text[max(0, match.start() - 30):min(len(text), match.end() + 30)]
                print(f"    Match {j+1}: '{date_str}' in context: '...{context}...'")
        else:
            print(f"  Pattern {i+1}: No matches")
    
    # Try direct extraction with DateExtractor
    date_extractor = DateExtractor()
    normalized_text = date_extractor._normalize_text(text)
    date_info = date_extractor.extract(text)
    
    print(f"\nDateExtractor results:")
    print(f"  Issue date: {date_info.get('issue_date')}")
    print(f"  Maturity date: {date_info.get('maturity_date')}")
    
    # Find and show common date format examples in the text
    print("\nSearching for common date formats:")
    common_date_formats = [
        r'\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}',  # 01-01-2023, 1/1/23
        r'\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{2,4}',  # 1 January 2023
        r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{2,4}'  # January 1, 2023
    ]
    
    for i, pattern in enumerate(common_date_formats):
        matches = re.finditer(pattern, text, re.IGNORECASE)
        match_list = list(matches)
        if match_list:
            print(f"  Format {i+1}: {len(match_list)} matches")
            for j, match in enumerate(match_list[:5]):  # Show max 5 matches per format
                date_str = match.group(0).strip()
                context = text[max(0, match.start() - 30):min(len(text), match.end() + 30)]
                print(f"    Match {j+1}: '{date_str}' in context: '...{context}...'")
        else:
            print(f"  Format {i+1}: No matches")

if __name__ == "__main__":
    # Test the date extraction on the file with good results
    debug_date_extraction('data/downloads/1732028370016_1732028368844_FC298561059_20241119_10978411.pdf')
    
    print("\n" + "="*80 + "\n")
    
    # Test the date extraction on a file with poor results
    debug_date_extraction('data/downloads/2025-003500.pdf') 