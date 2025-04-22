import sys
import logging
import os
from datetime import datetime

sys.path.append(os.path.abspath('.'))
from processes.pdf_extractor import PDFExtractor

# Configure logging
timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
logging.basicConfig(level=logging.INFO, 
                    format=f'{timestamp} - %(levelname)s - %(message)s')

def test_issue_size_extraction(pdf_path):
    """Test the issue size and currency extraction on a specific PDF."""
    logging.info(f"Testing issue size extraction in: {pdf_path}")
    
    # Create extractor instance
    extractor = PDFExtractor()
    
    # Extract text from PDF
    logging.info("Extracting text from PDF...")
    text = extractor.extract_text_from_pdf(pdf_path)
    
    # Print first 1000 characters for context
    logging.debug(f"First 1000 characters of extracted text:")
    logging.debug(text[:1000])
    
    # Extract issue size and currency
    logging.info("Extracting issue size and currency using the extractor...")
    size_info = extractor._extract_issue_size_currency(text)
    
    # Log results
    logging.info(f"Extracted size info: {size_info}")
    
    if size_info and 'issue_size' in size_info and 'currency' in size_info:
        if size_info['issue_size'] and size_info['currency']:
            logging.info(f"✅ Successfully extracted issue size: {size_info['issue_size']} {size_info['currency']}")
            return True
    
    logging.info("❌ Failed to extract issue size and currency.")
    return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_issue_size_extractor.py <pdf_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    success = test_issue_size_extraction(pdf_path)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1) 