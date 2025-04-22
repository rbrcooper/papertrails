from processes.pdf_extractor import PDFExtractor
from processes.pdf_extraction.extractors.currency_extractor import CurrencyExtractor
from processes.pdf_extraction.utils.pattern_registry import PatternRegistry
import re

def debug_currency_extraction(pdf_path):
    print(f"Debugging currency extraction for: {pdf_path}")
    extractor = PDFExtractor()
    
    # Extract the raw text
    text = extractor.extract_text(pdf_path)
    print(f"Raw text length: {len(text)} characters")
    
    # Get currency patterns from registry
    patterns = PatternRegistry.get_currency_patterns()
    
    # Check for currency codes
    print("\nSearching for currency codes:")
    for code in patterns['currency_codes']:
        matches = re.finditer(r'\b' + code + r'\b', text, re.IGNORECASE)
        match_list = list(matches)
        if match_list:
            print(f"  Code '{code}': {len(match_list)} matches")
            for j, match in enumerate(match_list[:3]):  # Show max 3 matches per code
                context = text[max(0, match.start() - 30):min(len(text), match.end() + 30)]
                print(f"    Match {j+1} in context: '...{context}...'")
    
    # Check for currency symbols
    print("\nSearching for currency symbols:")
    for symbol in patterns['currency_symbols']:
        matches = re.finditer(symbol, text)
        match_list = list(matches)
        if match_list:
            print(f"  Symbol '{symbol}': {len(match_list)} matches")
            for j, match in enumerate(match_list[:3]):  # Show max 3 matches per symbol
                context = text[max(0, match.start() - 30):min(len(text), match.end() + 30)]
                print(f"    Match {j+1} in context: '...{context}...'")
    
    # Test issue size patterns
    print("\nTesting issue size patterns:")
    for i, pattern in enumerate(patterns['issue_size']):
        matches = re.finditer(pattern, text, re.IGNORECASE)
        match_list = list(matches)
        if match_list:
            print(f"  Pattern {i+1}: {len(match_list)} matches")
            for j, match in enumerate(match_list[:3]):  # Show max 3 matches per pattern
                full_match = match.group(0)
                context = text[max(0, match.start() - 30):min(len(text), match.end() + 30)]
                print(f"    Match {j+1}: '{full_match}' in context: '...{context}...'")
        else:
            print(f"  Pattern {i+1}: No matches")
    
    # Try direct extraction with CurrencyExtractor
    currency_extractor = CurrencyExtractor()
    normalized_text = currency_extractor._normalize_text(text)
    currency_info = currency_extractor.extract(text)
    
    print(f"\nCurrencyExtractor results:")
    print(f"  Currency: {currency_info.get('currency')}")
    print(f"  Issue size: {currency_info.get('issue_size')}")
    
    # Look for common amount patterns in text
    print("\nSearching for common amount patterns:")
    amount_patterns = [
        r'(?:amount|size|total|principal|issue|value)\s+of\s+(?:\w+\s+){0,3}(?:EUR|USD|GBP|JPY|CHF|\$|€|£|¥)?\s*[\d,.]+\s*(?:million|billion|m|bn)?',
        r'(?:EUR|USD|GBP|JPY|CHF|\$|€|£|¥)\s*[\d,.]+\s*(?:million|billion|m|bn)?',
        r'[\d,.]+\s*(?:million|billion|m|bn)?\s*(?:EUR|USD|GBP|JPY|CHF|\$|€|£|¥)'
    ]
    
    for i, pattern in enumerate(amount_patterns):
        matches = re.finditer(pattern, text, re.IGNORECASE)
        match_list = list(matches)
        if match_list:
            print(f"  Pattern {i+1}: {len(match_list)} matches")
            for j, match in enumerate(match_list[:5]):  # Show max 5 matches per format
                amount_str = match.group(0).strip()
                context = text[max(0, match.start() - 30):min(len(text), match.end() + 30)]
                print(f"    Match {j+1}: '{amount_str}' in context: '...{context}...'")
        else:
            print(f"  Pattern {i+1}: No matches")

if __name__ == "__main__":
    # Test the currency extraction on the file with good results
    debug_currency_extraction('data/downloads/1732028370016_1732028368844_FC298561059_20241119_10978411.pdf')
    
    print("\n" + "="*80 + "\n")
    
    # Test the currency extraction on a file with poor results
    debug_currency_extraction('data/downloads/2025-003500.pdf') 