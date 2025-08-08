"""
PDF Document Extractor
--------------------
Extracts and processes text content from PDF documents, specifically designed for ESMA prospectus documents.

Key Features:
- PDF text extraction using pdfplumber and PyMuPDF
- OCR support for scanned documents using Tesseract
- Document structure analysis
- Metadata extraction (dates, ISINs, etc.)
- Section identification and categorization
- Error handling for corrupted PDFs
- Parallel processing support

Dependencies:
- pdfplumber: PDF text extraction
- PyMuPDF: PDF processing
- pytesseract: OCR support
- re: Regular expressions for pattern matching
- logging: Logging functionality
- pandas: Data handling and storage
- concurrent.futures: Parallel processing

Usage:
    from processes.pdf_extractor import PDFExtractor
    
    extractor = PDFExtractor()
    metadata = extractor.process_pdf("path/to/document.pdf")
"""

import os
import concurrent.futures
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
import time

from processes.pdf_extraction.core import ExtractionEngine
from processes.pdf_extraction.extractors.date_extractor import DateExtractor
from processes.pdf_extraction.extractors.currency_extractor import CurrencyExtractor
from processes.pdf_extraction.extractors.coupon_extractor import CouponExtractor
from processes.pdf_extraction.extractors.bank_extractor import BankExtractor
from processes.pdf_extraction.extractors.ai_bank_extractor import AIBankExtractor
from processes.utils.decorators import retry

class PDFExtractor:
    """
    PDF Document Extractor
    --------------------
    Extracts and processes text content from PDF documents,
    specifically designed for ESMA prospectus documents.
    """
    
    def __init__(self, pdf_dir: str = "data/downloads", use_ocr: bool = True, max_workers: int = 4, debug_mode=False, use_ai_extraction: bool = True):
        """
        Initialize the PDF extractor.
        
        Args:
            pdf_dir: Directory containing PDF files
            use_ocr: Whether to use OCR for text extraction
            max_workers: Maximum number of workers for parallel processing
            debug_mode: Whether to enable debug mode
            use_ai_extraction: Whether to use AI-based bank extraction
        """
        self.pdf_dir = pdf_dir
        self.use_ocr = use_ocr
        self.max_workers = max_workers
        self.debug_mode = debug_mode
        self.use_ai_extraction = use_ai_extraction
        self.setup_logging()
        
        # Create the extraction engine
        self.engine = ExtractionEngine(use_ocr=use_ocr, max_workers=max_workers)
        
        # Initialize extractors with debug mode
        self.extractors = {
            'date': DateExtractor(debug_mode=debug_mode),
            'currency': CurrencyExtractor(debug_mode=debug_mode),
            'coupon': CouponExtractor(debug_mode=debug_mode),
            'bank': BankExtractor(debug_mode=debug_mode)
        }
        
        # Initialize AI extractor if enabled
        if self.use_ai_extraction:
            self.ai_extractor = AIBankExtractor(debug_mode=debug_mode)
            if self.debug_mode:
                self.logger.info("AI bank extraction enabled")
        else:
            self.ai_extractor = None
            if self.debug_mode:
                self.logger.info("AI bank extraction disabled")
        
        # PDF text cache to avoid re-reading the same file
        self.text_cache = {}
                
    def setup_logging(self):
        """Set up logging configuration."""
        logging.basicConfig(
            level=logging.DEBUG if self.debug_mode else logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    @retry(max_retries=3, delay=5, backoff=2)
    def process_single_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Process a single PDF and extract all relevant information.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary with extraction results
        """
        start_time = time.time()
        
        if self.debug_mode:
            self.logger.debug(f"Starting extraction for {pdf_path}")
        
        # Extract the text once and cache it
        text = self.extract_text(pdf_path)
        
        if self.debug_mode:
            self.logger.debug(f"Extracted {len(text)} characters from PDF")
            self.logger.debug(f"Start of extracted text (first 2000 chars):\n{text[:2000]}")
            
        # Start building the result dictionary
        filename = os.path.basename(pdf_path)
        result = {
            'filename': filename,
            'file_path': pdf_path,
            'metadata': {},
            'validation_flags': []
        }
        
        # Extract dates (issue date and maturity date)
        if self.debug_mode:
            self.logger.debug("Extracting dates...")
            
        date_info = self.extractors['date'].extract(text)
        result['metadata']['issue_date'] = date_info.get('issue_date')
        result['metadata']['maturity_date'] = date_info.get('maturity_date')
        
        # Validate dates
        if not result['metadata']['issue_date'] or not result['metadata']['maturity_date']:
            result['validation_flags'].append('no_dates_extracted')
            if self.debug_mode:
                self.logger.warning("Failed to extract dates")
                if not result['metadata']['issue_date']:
                    self.logger.warning("No issue date extracted")
                if not result['metadata']['maturity_date']:
                    self.logger.warning("No maturity date extracted")
        
        # Extract currency information
        if self.debug_mode:
            self.logger.debug("Extracting currency information...")
            
        currency_info = self.extractors['currency'].extract(text)
        result['metadata']['currency'] = currency_info.get('currency')
        result['metadata']['issue_size'] = currency_info.get('issue_size')
        
        if currency_info.get('issue_size_range'):
            result['metadata']['issue_size_range'] = currency_info.get('issue_size_range')
        
        # Validate currency info
        if not result['metadata']['currency'] or not result['metadata']['issue_size']:
            result['validation_flags'].append('no_currency_info_extracted')
            if self.debug_mode:
                self.logger.warning("Failed to extract currency information")
                if not result['metadata']['currency']:
                    self.logger.warning("No currency extracted")
                if not result['metadata']['issue_size']:
                    self.logger.warning("No issue size extracted")
        
        # Extract coupon information
        if self.debug_mode:
            self.logger.debug("Extracting coupon information...")
            
        coupon_info = self.extractors['coupon'].extract(text)
        result['metadata']['coupon_rate'] = coupon_info.get('coupon_rate')
        result['metadata']['coupon_type'] = coupon_info.get('coupon_type')
        
        if coupon_info.get('reference_rate'):
            result['metadata']['reference_rate'] = coupon_info.get('reference_rate')
            
        # Validate coupon info
        if not result['metadata']['coupon_rate'] or not result['metadata']['coupon_type']:
            result['validation_flags'].append('no_coupon_info_extracted')
            if self.debug_mode:
                self.logger.warning("Failed to extract coupon information")
                if not result['metadata']['coupon_rate']:
                    self.logger.warning("No coupon rate extracted")
                if not result['metadata']['coupon_type']:
                    self.logger.warning("No coupon type extracted")
        
        # Extract bank information
        try:
            if self.debug_mode:
                self.logger.debug("Extracting bank information...")
            
            # Try AI extraction first if enabled
            if self.ai_extractor and self.ai_extractor.test_connection():
                if self.debug_mode:
                    self.logger.debug("Using AI extraction for banks...")
                bank_info = self.ai_extractor.extract(text)
                result['extracted_banks'] = bank_info.get('extracted_banks', [])
                result['bank_sections'] = bank_info.get('bank_sections', {})
                result['ai_extraction_used'] = True
                result['ai_extraction_metadata'] = {
                    'model_used': bank_info.get('model_used'),
                    'extraction_method': bank_info.get('extraction_method'),
                    'confidence': bank_info.get('confidence'),
                    'extraction_time': bank_info.get('extraction_time')
                }
            else:
                # Fallback to regex extraction
                if self.debug_mode:
                    self.logger.debug("Using regex extraction for banks...")
                bank_info = self.extractors['bank'].extract(text)
                result['extracted_banks'] = bank_info.get('extracted_banks', [])
                result['bank_sections'] = bank_info.get('bank_sections', {})
                result['ai_extraction_used'] = False
            
            # Validate bank info
            if not result['extracted_banks']:
                result['validation_flags'].append('no_banks_extracted')
                if self.debug_mode:
                    self.logger.warning("No banks extracted")
        except Exception as e:
            result['validation_flags'].append('bank_extraction_error')
            result['bank_extraction_error'] = str(e)
            if self.debug_mode:
                self.logger.error(f"Error extracting bank information: {str(e)}")
        
        # Check for validation flags and set confidence level
        if not result['validation_flags']:
            result['metadata']['extraction_confidence'] = 'high'
        elif len(result['validation_flags']) == 1:
            result['metadata']['extraction_confidence'] = 'medium'
        else:
            result['metadata']['extraction_confidence'] = 'low'
            
        if self.debug_mode:
            self.logger.debug(f"Extraction complete with confidence: {result['metadata']['extraction_confidence']}")
            self.logger.debug(f"Validation flags: {result['validation_flags']}")
            
        # Add timing information
        end_time = time.time()
        extraction_time = end_time - start_time
        result['metadata']['extraction_time'] = extraction_time
        
        if self.debug_mode:
            self.logger.debug(f"Extraction completed in {extraction_time:.2f} seconds")
        
        return result
    
    def process_pdfs(self) -> List[Dict]:
        """
        Process all PDFs in the directory.
        
        Returns:
            List of dictionaries containing extracted information
        """
        pdf_files = list(Path(self.pdf_dir).glob("**/*.pdf"))
        self.logger.info(f"Found {len(pdf_files)} PDF files")
            
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Process PDFs in parallel
            future_to_pdf = {executor.submit(self.process_single_pdf, str(pdf)): pdf for pdf in pdf_files}
            
            for future in concurrent.futures.as_completed(future_to_pdf):
                pdf = future_to_pdf[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                        self.logger.info(f"Processed {pdf.name}")
                    else:
                        self.logger.warning(f"Failed to process {pdf.name}")
                except Exception as e:
                    self.logger.error(f"Error processing {pdf.name}: {str(e)}")
        
        return results
        
    def extract_text(self, pdf_path: str) -> str:
        """
        Extract text from a PDF file, with caching.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text content
        """
        # Check cache first
        if pdf_path in self.text_cache:
            if self.debug_mode:
                self.logger.debug(f"Using cached text for {pdf_path}")
            return self.text_cache[pdf_path]
        
        if self.debug_mode:
            self.logger.debug(f"Extracting text from {pdf_path}")
            
        # Extract text using the engine
        try:
            text = self.engine.extract_text(pdf_path)
            
            # Cache the result
            self.text_cache[pdf_path] = text
            
            if self.debug_mode:
                self.logger.debug(f"Extracted {len(text)} characters")
                
            return text
        except Exception as e:
            if self.debug_mode:
                self.logger.error(f"Error extracting text from PDF: {str(e)}")
            return ""
    
    def is_final_terms(self, filename: str) -> bool:
        """
        Check if a filename suggests a final terms document.
        
        Args:
            filename: The filename to check
            
        Returns:
            True if the filename suggests a final terms document
        """
        filename_lower = filename.lower()
        return any(term in filename_lower for term in ['final', 'terms', 'pricing', 'supplement'])
    
    def clean_bank_name(self, bank: str) -> str:
        """
        Clean a bank name.
        
        Args:
            bank: The bank name to clean
            
        Returns:
            Cleaned bank name
        """
        return self.engine.bank_extractor.clean_bank_name(bank)
    
    def is_valid_bank_name(self, bank: str) -> bool:
        """
        Check if a string is likely a valid bank name.
        
        Args:
            bank: The bank name to check
            
        Returns:
            True if likely a valid bank name
        """
        return self.engine.bank_extractor.is_valid_bank_name(bank)

def main():
    """Main entry point for the PDF extractor."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract information from PDF documents')
    parser.add_argument('--pdf_dir', type=str, default='data/downloads', help='Directory containing PDF files')
    parser.add_argument('--use_ocr', action='store_true', help='Use OCR for text extraction')
    parser.add_argument('--max_workers', type=int, default=4, help='Maximum number of workers for parallel processing')
    parser.add_argument('--debug_mode', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    extractor = PDFExtractor(
        pdf_dir=args.pdf_dir,
        use_ocr=args.use_ocr,
        max_workers=args.max_workers,
        debug_mode=args.debug_mode
    )
    
    results = extractor.process_pdfs()
    print(f"Processed {len(results)} PDFs")

if __name__ == '__main__':
    main() 