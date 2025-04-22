from processes.pdf_extractor import PDFExtractor
import os

def test_pdfs():
    extractor = PDFExtractor()
    pdf_files = [
        'data/downloads/2025-003500.pdf', 
        'data/downloads/CD_218194.pdf',
        'data/downloads/1732028370016_1732028368844_FC298561059_20241119_10978411.pdf'
    ]
    
    print(f"{'PDF File':<40} {'Issue Date':<12} {'Maturity':<12} {'Currency':<8} {'Size':<15} {'Flags':<30} {'Banks'}")
    print("-" * 130)
    
    for pdf_file in pdf_files:
        # Get just the filename without path
        filename = os.path.basename(pdf_file)
        
        result = extractor.process_single_pdf(pdf_file)
        metadata = result.get('metadata', {})
        flags = result.get('validation_flags', [])
        banks = len(result.get('extracted_banks', []))
        
        flag_str = ", ".join(flags) if flags else "None"
        if len(flag_str) > 27:
            flag_str = flag_str[:27] + "..."
        
        print(f"{filename:<40} {metadata.get('issue_date') or 'None':<12} {metadata.get('maturity_date') or 'None':<12} {metadata.get('currency') or 'None':<8} {metadata.get('issue_size') or 'None':<15} {flag_str:<30} {banks}")

if __name__ == "__main__":
    test_pdfs() 