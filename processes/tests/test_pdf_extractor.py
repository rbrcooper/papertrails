from processes.pdf_extractor import PDFExtractor
import sys

def test_pdf_file(pdf_path):
    print(f"Processing: {pdf_path}")
    extractor = PDFExtractor()
    
    # First, just try to extract text
    raw_text = extractor.extract_text(pdf_path)
    print(f"Raw text extraction: {len(raw_text)} characters")
    if raw_text:
        print(f"Text preview: {raw_text[:200]}...\n")
    
    # Process the PDF
    result = extractor.process_single_pdf(pdf_path)
    
    # Print extracted information
    print(f"Extracted banks: {result.get('extracted_banks', [])}")
    print(f"Metadata: {result.get('metadata', {})}")
    print(f"Validation flags: {result.get('validation_flags', [])}")
    
    # Print sections
    print("\nExtracted Sections:")
    for section_name, section_text in result.get('sections', {}).items():
        print(f"  {section_name}: {len(section_text)} characters")
        # Print first 100 characters of each section for context
        if section_text:
            print(f"    Preview: {section_text[:100]}...")
    
    print("\n" + "-"*80 + "\n")
    
    return result

if __name__ == "__main__":
    # List of PDF files to test
    pdf_files = [
        'data/downloads/2025-003500.pdf',
        'data/downloads/CD_218194.pdf',
        'data/downloads/1732028370016_1732028368844_FC298561059_20241119_10978411.pdf'
    ]
    
    # Process each file
    results = {}
    for pdf_file in pdf_files:
        try:
            results[pdf_file] = test_pdf_file(pdf_file)
        except Exception as e:
            print(f"Error processing {pdf_file}: {str(e)}")
            
    # Print summary
    print("\nSummary:")
    for pdf_file, result in results.items():
        banks = len(result.get('extracted_banks', []))
        flags = len(result.get('validation_flags', []))
        print(f"{pdf_file}: {banks} banks, {flags} validation flags") 