import sys
from pathlib import Path

# Add project root to sys.path to allow importing from processes
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from processes.pdf_extractor import PDFExtractor
except ImportError as e:
    print(f"Error importing PDFExtractor: {e}")
    print("Ensure the script is run from the project root or the project structure is correct.")
    sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_sections.py <pdf_path> [--banks-only]")
        sys.exit(1)
        
    pdf_path = sys.argv[1]
    banks_only = "--banks-only" in sys.argv
    
    print(f"Analyzing PDF: {pdf_path}")
    
    # Initialize the extractor
    extractor = PDFExtractor()
    
    # Extract text from the PDF
    text = extractor.extract_text(pdf_path)
    if not text:
        print("Failed to extract text from the PDF")
        sys.exit(1)
    
    # Extract bank information using the detailed method
    print("\n==== BANK EXTRACTION RESULTS ====")
    bank_info = extractor._extract_banks_and_roles(text)
    
    if not bank_info["extracted_banks"]:
        print("No banks found in the document.")
    else:
        print(f"Found {len(bank_info['extracted_banks'])} banks:")
        for i, bank in enumerate(bank_info["extracted_banks"], 1):
            print(f"\n[{i}] {bank['cleaned_name']}")
            print(f"  Raw Name: {bank['raw_name']}")
            print(f"  Role: {bank['role']}")
            print(f"  Confidence: {bank['confidence']:.2f}")
            print(f"  Source: {bank['source']}")
    
    print("\n==== BANK SECTIONS FOUND ====")
    if not bank_info["bank_sections"]:
        print("No specific bank sections identified.")
    else:
        for section_name, section_text in bank_info["bank_sections"].items():
            print(f"\n--- {section_name.upper()} SECTION ---")
            print(section_text[:500] + "..." if len(section_text) > 500 else section_text)
    
    # If not banks-only flag, also show the original section checks
    if not banks_only:
        # Get relevant sections
        print("\n==== DISTRIBUTION SECTION ====")
        distribution_section = extractor.find_section(text, "Distribution")
        if distribution_section:
            print(distribution_section)
        else:
            print("No distribution section found")
            
        print("\n==== MANAGERS SECTION ====")
        managers_section = extractor.find_section(text, "Managers")
        if managers_section:
            print(managers_section)
        else:
            print("No managers section found")
            
        print("\n==== STABILISATION SECTION ====")
        stabilisation_section = extractor.find_section(text, "Stabilisation Manager")
        if stabilisation_section:
            print(stabilisation_section)
        else:
            print("No stabilisation section found")
        
        # Search for specific bank names in the entire document
        print("\n==== SEARCHING FOR BANK NAMES ====")
        bank_names = [
            "BNP Paribas", "Deutsche Bank", "Credit Suisse", "Morgan Stanley", 
            "Goldman Sachs", "JP Morgan", "HSBC", "Barclays", "UBS", "Citigroup",
            "Bank of America", "BofA Securities", "Quadra Energy"
        ]
        
        for bank in bank_names:
            occurrences = text.count(bank)
            if occurrences > 0:
                print(f"Found '{bank}' {occurrences} times")
                # Show context for each occurrence
                start_idx = 0
                for i in range(occurrences):
                    start_idx = text.find(bank, start_idx)
                    if start_idx == -1:
                        break
                        
                    context_start = max(0, start_idx - 100)
                    context_end = min(len(text), start_idx + len(bank) + 100)
                    context = text[context_start:context_end]
                    
                    print(f"\nOccurrence {i+1}: context around '{bank}':")
                    print("..." + context + "...")
                    
                    start_idx += len(bank)  # Move past current occurrence

if __name__ == "__main__":
    main() 