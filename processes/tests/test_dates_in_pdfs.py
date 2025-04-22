import sys
from pathlib import Path
import argparse
import logging
import re

# Add project root to sys.path to allow importing from processes
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from processes.pdf_extractor import PDFExtractor

def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger('test_dates_in_pdfs')

def manual_date_search(text, logger):
    """Manually search for date-like patterns in the text."""
    logger.info("Performing manual date search...")
    
    # Define common date-related keywords
    date_keywords = [
        "issue date", "dated", "maturity date", "redemption date", 
        "final maturity", "issuance date", "date of issue", "settlement date",
        "trade date", "effective date", "termination date", "value date",
        "issue", "issued on", "will be issued on", "to be issued on"
    ]
    
    # Search for lines containing these keywords
    date_lines = []
    lines = text.splitlines()
    for line in lines:
        line = line.strip().lower()
        if any(keyword in line for keyword in date_keywords):
            date_lines.append(line)
    
    # Print the found lines
    logger.info(f"Found {len(date_lines)} lines with date keywords:")
    for i, line in enumerate(date_lines[:20]):  # Limit to first 20 for readability
        logger.info(f"  {i+1}. {line}")
    
    # Look for date patterns in the text
    date_patterns = [
        r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}',  # DD/MM/YYYY, DD-MM-YYYY
        r'\d{4}[-/]\d{2}[-/]\d{2}',        # YYYY/MM/DD, YYYY-MM-DD
        r'\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}',  # DD Month YYYY
        r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}'  # Month DD, YYYY
    ]
    
    all_dates = []
    for pattern in date_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            all_dates.append(match.group(0))
    
    # Limit to first 20 unique dates
    unique_dates = sorted(set(all_dates))[:20]
    logger.info(f"Found {len(unique_dates)} potential dates in document:")
    for date in unique_dates:
        logger.info(f"  • {date}")
    
    return date_lines, unique_dates

def test_dates_in_pdf(pdf_path, logger):
    """Extract and test dates from a real PDF file."""
    logger.info(f"Testing date extraction in: {pdf_path}")
    
    extractor = PDFExtractor()
    
    # First extract text from the PDF
    logger.info("Extracting text from PDF...")
    text = extractor.extract_text(pdf_path)
    if not text:
        logger.error("Failed to extract text from PDF")
        return False
    
    logger.info(f"Successfully extracted {len(text)} characters")
    
    # Print a sample of the extracted text
    logger.debug(f"First 1000 characters of extracted text:")
    logger.debug(text[:1000])
    
    # Manual search for dates
    date_lines, unique_dates = manual_date_search(text, logger)
    
    # Extract dates using the extractor
    logger.info("Extracting dates using the extractor...")
    date_info = extractor._extract_dates(text)
    
    # Print the result
    logger.info(f"Extracted dates: {date_info}")
    
    # Check if any dates were found
    if date_info['issue_date'] or date_info['maturity_date']:
        logger.info("✅ Success! Found at least one date.")
        return True
    else:
        logger.info("❌ Failed to find any dates.")
        return False

def main():
    parser = argparse.ArgumentParser(description='Test date extraction on PDF files.')
    parser.add_argument('pdf_paths', nargs='+', help='Paths to PDF files to test')
    
    args = parser.parse_args()
    logger = setup_logging()
    
    success_count = 0
    fail_count = 0
    
    for pdf_path in args.pdf_paths:
        if test_dates_in_pdf(pdf_path, logger):
            success_count += 1
        else:
            fail_count += 1
    
    logger.info(f"Summary: {success_count} successes, {fail_count} failures")

if __name__ == "__main__":
    main() 