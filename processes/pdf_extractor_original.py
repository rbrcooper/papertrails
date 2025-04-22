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
from typing import Dict, List, Optional
from pathlib import Path

from processes.pdf_extraction.core import ExtractionEngine

class PDFExtractor:
    """
    PDF Document Extractor
    --------------------
    Extracts and processes text content from PDF documents,
    specifically designed for ESMA prospectus documents.
    """
    
    def __init__(self, pdf_dir: str = "data/downloads", use_ocr: bool = True, max_workers: int = 4):
        """
        Initialize the PDF extractor.
        
        Args:
            pdf_dir: Directory containing PDF files
            use_ocr: Whether to use OCR for text extraction
            max_workers: Maximum number of workers for parallel processing
        """
        self.pdf_dir = pdf_dir
        self.use_ocr = use_ocr
        self.max_workers = max_workers
        self.setup_logging()
        
        # Create the extraction engine
        self.engine = ExtractionEngine(use_ocr=use_ocr, max_workers=max_workers)
        
    def setup_logging(self):
        """Set up logging configuration."""
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def process_single_pdf(self, pdf_path: str) -> Optional[Dict]:
        """
        Process a single PDF file to extract bank information and other metadata.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary containing extracted information
        """
        return self.engine.process_single_pdf(pdf_path)
    
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
    
    # For backward compatibility, we delegate to the corresponding methods in the engine
    def extract_text(self, pdf_path: str) -> str:
        """
        Extract text from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text
        """
        return self.engine.extract_text(pdf_path)
    
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
    
    args = parser.parse_args()
    
    extractor = PDFExtractor(
        pdf_dir=args.pdf_dir,
        use_ocr=args.use_ocr,
        max_workers=args.max_workers
    )
    
    results = extractor.process_pdfs()
    print(f"Processed {len(results)} PDFs")

if __name__ == '__main__':
    main()
