"""
Core Extraction Engine
--------------------
Orchestrates the PDF extraction process using specialized extractors.
"""

import os
import re
import logging
from typing import Dict, Optional, Any, List
import fitz  # PyMuPDF
import pymupdf4llm
import pytesseract
from PIL import Image
import io
from pathlib import Path
from pdf2image import convert_from_path
import tempfile

from .extractors.bank_extractor import BankExtractor
from .extractors.date_extractor import DateExtractor
from .extractors.currency_extractor import CurrencyExtractor
from .extractors.coupon_extractor import CouponExtractor
from .utils.text_processing import TextProcessor

class ExtractionEngine:
    """Orchestrates the PDF extraction process."""
    
    def __init__(self, use_ocr: bool = True, max_workers: int = 4):
        """
        Initialize the extraction engine.
        
        Args:
            use_ocr: Whether to use OCR for text extraction
            max_workers: Maximum number of workers for parallel processing
        """
        self.logger = logging.getLogger(__name__)
        self.text_processor = TextProcessor()
        self.bank_extractor = BankExtractor(self.text_processor)
        self.date_extractor = DateExtractor()
        self.currency_extractor = CurrencyExtractor()
        self.coupon_extractor = CouponExtractor()
        self.use_ocr = use_ocr
        self.max_workers = max_workers
        
        # Configure Tesseract if OCR is enabled
        if self.use_ocr:
            try:
                # Try to find Tesseract executable
                if os.name == 'nt':  # Windows
                    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
                # Add more OS-specific paths if needed
            except Exception as e:
                self.logger.warning(f"Failed to configure Tesseract: {e}")
                self.use_ocr = False
    
    def extract_text(self, pdf_path: str) -> str:
        """
        Extract text from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text
        """
        if not os.path.exists(pdf_path):
            self.logger.error(f"PDF file not found: {pdf_path}")
            return ""
            
        try:
            # Try PyMuPDF first
            with fitz.open(pdf_path) as doc:
                text = ""
                for page in doc:
                    text += page.get_text()
                    
                # If text is too sparse, try pymupdf4llm for more intensive extraction
                if len(text) < 100 * doc.page_count:
                    try:
                        text = pymupdf4llm.get_content(file_path=pdf_path)
                    except Exception as e:
                        self.logger.warning(f"pymupdf4llm extraction failed: {e}")
                        
                # Clean the extracted text
                text = self.text_processor.clean_text(text)
                
                # If text is still too sparse, try OCR
                if len(text) < 100 * doc.page_count and self.use_ocr:
                    return self._extract_text_with_ocr(pdf_path)
                    
                return text
                
        except Exception as e:
            self.logger.error(f"Failed to extract text using PyMuPDF: {e}")
            
            # Fall back to OCR if enabled
            if self.use_ocr:
                return self._extract_text_with_ocr(pdf_path)
                
        return ""
    
    def extract_text_first_pages(self, pdf_path: str, num_pages: int = 2) -> str:
        """
        Extract text from only the first N pages of a PDF (lightweight for quick checks).
        
        Args:
            pdf_path: Path to the PDF file
            num_pages: Number of pages to extract (default: 2)
            
        Returns:
            Extracted text from first pages
        """
        if not os.path.exists(pdf_path):
            self.logger.error(f"PDF file not found: {pdf_path}")
            return ""
            
        try:
            with fitz.open(pdf_path) as doc:
                text = ""
                pages_to_extract = min(num_pages, len(doc))
                
                for page_num in range(pages_to_extract):
                    page = doc[page_num]
                    text += page.get_text()
                
                # Clean the extracted text
                text = self.text_processor.clean_text(text)
                return text
                
        except Exception as e:
            self.logger.error(f"Failed to extract text from first pages: {e}")
            return ""
    
    def _extract_text_with_ocr(self, pdf_path: str) -> str:
        """
        Extract text from a PDF using OCR.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text
        """
        try:
            self.logger.info(f"Using OCR for {pdf_path}")
            
            # Convert PDF to images
            with tempfile.TemporaryDirectory() as temp_dir:
                images = convert_from_path(pdf_path)
                
                # Process each page with OCR
                text = ""
                for i, image in enumerate(images):
                    # Apply OCR to the image
                    text += pytesseract.image_to_string(image)
                    
                # Clean the extracted text
                return self.text_processor.clean_text(text)
                
        except Exception as e:
            self.logger.error(f"OCR extraction failed: {e}")
            
        return ""
    
    def process_text(self, text: str, pdf_path: str) -> Dict[str, Any]:
        """
        Process extracted text to identify all required information.
        
        Args:
            text: The extracted text
            pdf_path: Path to the original PDF file
            
        Returns:
            Dictionary containing all extracted information
        """
        # Extract bank information
        bank_info = self.bank_extractor.extract(text)
        
        # Extract dates
        dates = self.date_extractor.extract(text)
        self.logger.debug(f"Extracted dates: {dates}")
        
        # Extract currency and issue size
        currency_info = self.currency_extractor.extract(text)
        self.logger.debug(f"Extracted currency info: {currency_info}")
        
        # Extract coupon information
        coupon_info = self.coupon_extractor.extract(text)
        self.logger.debug(f"Extracted coupon info: {coupon_info}")
        
        # Extract document sections
        sections = self.text_processor.extract_sections(text)
        
        # Process section-specific information if general extraction failed
        if not dates.get('issue_date') or not dates.get('maturity_date'):
            # Try to find dates in specific sections
            for section_name, section_text in sections.items():
                section_name_lower = section_name.lower()
                
                # For issue date, look in summary, terms, or issuance sections
                if not dates.get('issue_date') and any(term in section_name_lower for term in ['summary', 'terms', 'issuance', 'offer']):
                    section_dates = self.date_extractor.extract(section_text)
                    if section_dates.get('issue_date'):
                        dates['issue_date'] = section_dates['issue_date']
                        self.logger.info(f"Found issue date {dates['issue_date']} in section {section_name}")
                
                # For maturity date, look in redemption or repayment sections
                if not dates.get('maturity_date') and any(term in section_name_lower for term in ['maturity', 'redemption', 'repayment']):
                    section_dates = self.date_extractor.extract(section_text)
                    if section_dates.get('maturity_date'):
                        dates['maturity_date'] = section_dates['maturity_date']
                        self.logger.info(f"Found maturity date {dates['maturity_date']} in section {section_name}")
        
        # Try to extract currency and issue size from specific sections if general extraction failed
        if not currency_info.get('currency') or not currency_info.get('issue_size'):
            for section_name, section_text in sections.items():
                section_name_lower = section_name.lower()
                
                if any(term in section_name_lower for term in ['summary', 'terms', 'offer', 'issuance', 'principal']):
                    section_currency = self.currency_extractor.extract(section_text)
                    if not currency_info.get('currency') and section_currency.get('currency'):
                        currency_info['currency'] = section_currency['currency']
                        self.logger.info(f"Found currency {currency_info['currency']} in section {section_name}")
                    
                    if not currency_info.get('issue_size') and section_currency.get('issue_size'):
                        currency_info['issue_size'] = section_currency['issue_size']
                        self.logger.info(f"Found issue size {currency_info['issue_size']} in section {section_name}")
        
        # Try to extract coupon information from specific sections if general extraction failed
        if not coupon_info.get('coupon_rate') or not coupon_info.get('coupon_type'):
            for section_name, section_text in sections.items():
                section_name_lower = section_name.lower()
                
                if any(term in section_name_lower for term in ['interest', 'coupon', 'payment', 'yield']):
                    section_coupon = self.coupon_extractor.extract(section_text)
                    if not coupon_info.get('coupon_rate') and section_coupon.get('coupon_rate'):
                        coupon_info['coupon_rate'] = section_coupon['coupon_rate']
                        self.logger.info(f"Found coupon rate {coupon_info['coupon_rate']} in section {section_name}")
                    
                    if not coupon_info.get('coupon_type') and section_coupon.get('coupon_type'):
                        coupon_info['coupon_type'] = section_coupon['coupon_type']
                        self.logger.info(f"Found coupon type {coupon_info['coupon_type']} in section {section_name}")
        
        # Combine all metadata
        metadata = {
            **dates,
            **currency_info,
            **coupon_info
        }
        
        # Perform additional normalization and verification of extracted data
        metadata = self._normalize_metadata(metadata)
        
        # Create result dictionary
        result = {
            'filename': os.path.basename(pdf_path),
            'file_path': pdf_path,
            'metadata': metadata,
            'sections': sections,
            'extracted_banks': bank_info.get('extracted_banks', []),
            'bank_sections': bank_info.get('bank_sections', {}),
            'bank_info': bank_info.get('bank_info', {})
        }
        
        # Validate extraction results
        validation_flags = self._validate_extraction_results(
            bank_info, metadata, sections, pdf_path
        )
        result['validation_flags'] = validation_flags
        
        return result
    
    def _normalize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize and clean up extracted metadata.
        
        Args:
            metadata: The metadata dictionary to normalize
            
        Returns:
            Normalized metadata dictionary
        """
        normalized = metadata.copy()
        
        # Normalize currency values - standardize format and remove extra spaces
        if 'currency' in normalized and normalized['currency']:
            normalized['currency'] = normalized['currency'].strip().upper()
        
        # Normalize issue size - ensure consistent number format
        if 'issue_size' in normalized and normalized['issue_size']:
            # Try to convert to standard number format if possible
            try:
                # Replace commas that are thousand separators
                issue_size = normalized['issue_size'].replace(',', '')
                # Convert to float then back to string for standardization
                normalized['issue_size'] = str(float(issue_size))
            except:
                # If conversion fails, keep original format
                pass
        
        # Normalize coupon rate - standardize percentage format
        if 'coupon_rate' in normalized and normalized['coupon_rate']:
            try:
                # Remove % symbol if present
                rate = normalized['coupon_rate'].replace('%', '').strip()
                # Convert to float then back to string with % for standardization
                normalized['coupon_rate'] = f"{float(rate)}%"
            except:
                # If conversion fails, keep original format
                pass
        
        return normalized
    
    def _validate_extraction_results(self, 
                                     bank_info: Dict[str, Any], 
                                     metadata: Dict[str, Any], 
                                     sections: Dict[str, str],
                                     pdf_path: str) -> List[str]:
        """
        Validate extraction results to identify potential issues.
        
        Args:
            bank_info: The extracted bank information
            metadata: The extracted metadata
            sections: The extracted sections
            pdf_path: Path to the original PDF file
            
        Returns:
            List of validation flag strings
        """
        flags = []
        
        # Check if extracted any banks
        if not bank_info.get('extracted_banks'):
            flags.append('no_banks_extracted')
            
        # Check if extracted dates
        if not metadata.get('issue_date') and not metadata.get('maturity_date'):
            flags.append('no_dates_extracted')
            
        # Check if extracted currency information
        if not metadata.get('currency') and not metadata.get('issue_size'):
            flags.append('no_currency_info_extracted')
            
        # Check if extracted coupon information
        if not metadata.get('coupon_rate') and not metadata.get('coupon_type'):
            flags.append('no_coupon_info_extracted')
            
        # Check if found any sections
        if not sections:
            flags.append('no_sections_found')
            
        # Check if the filename suggests this is a prospectus/final terms
        filename = os.path.basename(pdf_path).lower()
        if not any(term in filename for term in ['prospectus', 'final', 'terms', 'offering', 'pricing']):
            flags.append('filename_not_recognized')
            
        return flags
        
    def process_single_pdf(self, pdf_path: str) -> Optional[Dict]:
        """
        Process a single PDF file to extract information.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary containing extracted information
        """
        try:
            # Extract text
            text = self.extract_text(pdf_path)
            if not text:
                return {
                    'filename': os.path.basename(pdf_path),
                    'file_path': pdf_path,
                    'validation_flags': ['text_extraction_failed']
                }
                
            # Process the text
            return self.process_text(text, pdf_path)
            
        except Exception as e:
            self.logger.error(f"Error processing {pdf_path}: {str(e)}")
            return {
                'filename': os.path.basename(pdf_path),
                'file_path': pdf_path,
                'validation_flags': [f'processing_error: {str(e)}']
            } 