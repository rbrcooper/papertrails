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

import fitz  # PyMuPDF
import os
import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging
import pymupdf4llm
import pytesseract
from PIL import Image
import io
import concurrent.futures
from pathlib import Path
import numpy as np
from pdf2image import convert_from_path
import tempfile
from dateutil.parser import parse

class PDFExtractor:
    def __init__(self, pdf_dir: str = "data/downloads", use_ocr: bool = True, max_workers: int = 4):
        self.pdf_dir = pdf_dir
        self.use_ocr = use_ocr
        self.max_workers = max_workers
        self.setup_logging()
        
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
                
    def setup_logging(self):
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def find_section(self, text: str, start_marker: str, end_marker: str = None) -> Optional[str]:
        """Find a section between start and end markers"""
        try:
            # Convert text and markers to lowercase for case-insensitive matching
            text_lower = text.lower()
            start_marker_lower = start_marker.lower()
            
            # Common variations of section headers in Final Terms
            section_variations = {
                'distribution': [
                    r'\b(?:plan\s+of\s+)?distribution\b',
                    r'\bsubscription\s+and\s+sale\b',
                    r'\bplacement\s+of\s+the\s+notes\b',
                    r'\bplacement\s+and\s+underwriting\b',
                    r'\bunderwriting\s+(?:and\s+placement|arrangement)?\b',
                    r'\bsyndicate\b',
                    r'\bselling\s+(?:restrictions|arrangements)\b',
                    r'\boffer(?:ing)?\s+(?:and|of|structure)?\b',
                    r'\bplacement\s+(?:of\s+securities|structure)\b',
                    r'\bdistribution\s+arrangement\b',
                    # Additional distribution patterns
                    r'\bsummary\s+of\s+the\s+offer\b',
                    r'\bgeneral\s+information\s+on\s+the\s+offer\b',
                    r'\boffer\s+structure\s+and\s+conditions\b',
                    r'\bterms\s+and\s+conditions\s+of\s+the\s+offer\b',
                    r'\bmethod\s+of\s+distribution\b',
                    r'\bdistribution\s+of\s+the\s+notes\b',
                    r'\bplacing\s+and\s+(?:underwriting|sale)\b',
                    r'\bpurchase\s+and\s+sale\s+of\s+the\s+notes\b',
                    r'\bterms\s+of\s+the\s+offering\b',
                    r'\boffer\s+and\s+(?:listing|admission)\b'
                ],
                'management': [
                    r'\bmanagers?\b',
                    r'\bjoint\s+lead\s+managers?\b',
                    r'\bbook(?:\-)?runners?\b',
                    r'\bnames\s+(?:and\s+addresses\s+)?of\s+(?:the\s+)?managers?\b',
                    r'\bunderwriters?\b',
                    r'\bdealers?\b',
                    r'\bsyndicate\s+members?\b',
                    r'\b(?:lead|global|principal)\s+(?:manager|arranger)s?\b',
                    r'\bmanagement\s+(?:and\s+underwriting|group|team)\b',
                    r'\bco-managers?\b',
                    r'\bplacement\s+agents?\b',
                    r'\b(?:managers?|bookrunners?|underwriters?|dealers?)\s+information\b',
                    # Additional management patterns
                    r'\bglobal\s+coordinators?\b',
                    r'\bjoint\s+book(?:\-)?runners?\b',
                    r'\bdealer\s+managers?\b',
                    r'\blead\s+structur(?:ing|ers?)\b',
                    r'\barrangers?\b',
                    r'\bsole\s+(?:bookrunner|manager|arranger|structurer)\b',
                    r'\bco(?:-|\s+)lead\s+managers?\b',
                    r'\bjoint\s+managers?\b',
                    r'\bindividual\s+dealers?\b',
                    r'\bselling\s+agents?\b',
                    r'\bsecurities\s+houses?\b',
                    r'\b(?:the\s+)?managers?\s+are\b'
                ],
                'stabilisation': [
                    r'\bstabili[sz]ing\s+managers?\b',
                    r'\bstabili[sz]ation\s+managers?\b',
                    r'\bstabili[sz]ation\b',
                    r'\bmarket\s+stabili[sz]ation\b',
                    r'\bprice\s+stabili[sz]ation\b',
                    r'\bmarket\s+making\b',
                    # Additional stabilization patterns
                    r'\bstabili[sz]ation\s+agent\b',
                    r'\bstabili[sz]ation\s+provisions\b',
                    r'\bstabili[sz]ing\s+activities\b',
                    r'\bstabili[sz]ation\s+activities\b',
                    r'\bstabili[sz]ation\s+undertaking\b',
                    r'\bsupport\s+transactions\b',
                    r'\bover(?:-|\s+)allotment\s+option\b'
                ],
                # Additional section headers that might contain bank information
                'participants': [
                    r'\b(?:transaction|programme|program)\s+participants\b',
                    r'\bparties\s+to\s+the\s+(?:transaction|offer|programme|program)\b',
                    r'\bparticipating\s+(?:entities|institutions|banks)\b',
                    # Additional participants patterns
                    r'\bparties\s+involved\b',
                    r'\bkey\s+(?:parties|participants)\b',
                    r'\bnames\s+of\s+entities\b',
                    r'\badditional\s+information\s+on\s+(?:the\s+)?(?:dealers|managers|underwriters)\b',
                    r'\bother\s+advisers\b',
                    r'\bfiscal\s+and\s+paying\s+agents?\b',
                    r'\b(?:issuer\'?s?\s+)?advisers?\b',
                    r'\bfurther\s+information\s+about\s+the\s+(?:managers|dealers|underwriters)\b',
                    r'\ballocation\s+of\s+responsibilities\b'
                ],
                'general': [
                    r'\broles\s+and\s+responsibilities\b',
                    r'\bsummary\s+of\s+participants\b',
                    r'\battending\s+(?:banks|parties)\b',
                    r'\binformation\s+on\s+the\s+(?:dealer|manager|arranger|bank)s?\b',
                    r'\borganisation\s+of\s+the\s+offer\b',
                    r'\bcontact\s+information\b',
                    # Additional general patterns
                    r'\bbank\s+details\b',
                    r'\bcontact\s+details\b',
                    r'\baddresses\b',
                    r'\bnames\s+and\s+addresses\b',
                    r'\bfinal\s+terms\b', # Final terms often have banks listed in a standard format
                    r'\bgeneral\s+information\b',
                    r'\bissue\s+specific\s+summary\b',
                    r'\bpricing\s+supplement\b',
                    r'\bsummary\s+of\s+(?:terms|the\s+issue)\b',
                    r'\badditional\s+information\b',
                    r'\blisting\s+(?:agent|particulars)\b',
                    r'\bauthorised\s+signatories\b',
                    r'\bapproval\s+of\s+the\s+(?:base\s+)?prospectus\b'
                ]
            }
            
            # Find the best matching section header based on the requested start_marker
            start_idx = -1
            matched_pattern = ""
            
            # Check for distribution section
            if any(var in start_marker_lower for var in ['distribution', 'subscription', 'placement', 'sale', 'syndicate', 'selling', 'offer']):
                for pattern in section_variations['distribution']:
                    matches = list(re.finditer(pattern, text_lower))
                    if matches:
                        # Choose the most prominent match (usually earlier in the document)
                        start_idx = matches[0].start()
                        matched_pattern = pattern
                        self.logger.info(f"Found distribution section with pattern: {pattern}")
                        break
            
            # Check for management/manager/bookrunner section                
            elif any(var in start_marker_lower for var in ['manager', 'book', 'bookrunner', 'lead', 'underwriter', 'dealer', 'arranger']):
                for pattern in section_variations['management']:
                    matches = list(re.finditer(pattern, text_lower))
                    if matches:
                        start_idx = matches[0].start()
                        matched_pattern = pattern
                        self.logger.info(f"Found management section with pattern: {pattern}")
                        break
            
            # Check for stabilisation section
            elif any(var in start_marker_lower for var in ['stabili', 'market making']):
                for pattern in section_variations['stabilisation']:
                    matches = list(re.finditer(pattern, text_lower))
                    if matches:
                        start_idx = matches[0].start()
                        matched_pattern = pattern
                        self.logger.info(f"Found stabilisation section with pattern: {pattern}")
                        break
                        
            # Check for participants section
            elif any(var in start_marker_lower for var in ['participant', 'parties', 'entities']):
                for pattern in section_variations['participants']:
                    matches = list(re.finditer(pattern, text_lower))
                    if matches:
                        start_idx = matches[0].start()
                        matched_pattern = pattern
                        self.logger.info(f"Found participants section with pattern: {pattern}")
                        break
                        
            # Check for general bank-related sections
            elif any(var in start_marker_lower for var in ['role', 'summary', 'information', 'contact']):
                for pattern in section_variations['general']:
                    matches = list(re.finditer(pattern, text_lower))
                    if matches:
                        start_idx = matches[0].start()
                        matched_pattern = pattern
                        self.logger.info(f"Found general section with pattern: {pattern}")
                        break
            
            # Default case - direct search
            else:
                start_idx = text_lower.find(start_marker_lower)
                if start_idx != -1:
                    matched_pattern = start_marker_lower
                
            # If no match, try a more general approach by looking for all section types
            if start_idx == -1:
                self.logger.debug(f"Could not find specific section for marker '{start_marker}', trying all section types...")
                
                # Try all section types as a fallback
                for section_type, patterns in section_variations.items():
                    for pattern in patterns:
                        matches = list(re.finditer(pattern, text_lower))
                        if matches:
                            start_idx = matches[0].start()
                            matched_pattern = pattern
                            self.logger.info(f"Found {section_type} section with pattern: {pattern} (fallback)")
                            break
                    if start_idx != -1:
                        break
                        
            # If still no section found, return None
            if start_idx == -1:
                return None
                
            # If end marker is provided, find it after the start marker
            if end_marker:
                end_marker_lower = end_marker.lower()
                end_idx = text_lower.find(end_marker_lower, start_idx)
                if end_idx == -1:
                    # Try to find the next section header if no specific end marker
                    next_section_pattern = r'\n\s*(?:[IVX]+\.|[A-Z]\.|\d+\.|\([a-z]\)|\d+\))?[A-Z][A-Z\s]{2,50}(?:\n|$)'
                    next_section_match = re.search(next_section_pattern, text[start_idx:])
                    if next_section_match:
                        end_idx = start_idx + next_section_match.start()
                    else:
                        end_idx = len(text)
            else:
                # If no end marker, try to find the next section header using improved patterns
                # This looks for various types of section headers
                next_section_patterns = [
                    r'\n\s*(?:[IVX]+\.|[A-Z]\.|\d+\.|\([a-z]\)|\d+\))(?:[A-Z][a-z]+\s)+(?:\n|$)',  # Title case with numbering
                    r'\n\s*[-—–•]\s*[A-Z][A-Z\s]{2,50}(?:\n|$)',  # All caps with bullet point
                    r'\n\s*(?:SECTION|PART|ARTICLE)\s+(?:[IVX]+|\d+)[:\s]+[A-Z][A-Z\s]+',  # Formal section markers
                    r'\n\s*\*\s*\*\s*\*',  # Section breaks with asterisks
                    r'\n\s*_{3,}|={3,}|-{3,}',  # Horizontal rules/lines as section breaks
                    r'\n\s*<strong>.*?</strong>',  # HTML strong tags (for some PDF extractions)
                    r'\n\s*[A-Z][A-Z\s]{3,}(?:\n|$)',  # All caps section title
                    r'\n\s*[\d\.]+\s+[A-Z][A-Za-z\s]{3,}(?:\n|$)',  # Numbered section like "1.1 SECTION NAME"
                    r'\n\s*.*?\n\s*={3,}|-{3,}',  # Title followed by underline
                    r'\n\s*\[\s*[A-Z][A-Za-z\s]{3,}\s*\](?:\n|$)'  # [SECTION NAME] format
                ]
                
                end_idx = len(text)  # Default to end of text
                
                # Find the earliest next section header
                for pattern in next_section_patterns:
                    # Skip a bit to avoid matching current section, but not too much
                    # Minimum offset of 100 chars to ensure we have enough context
                    search_start = min(start_idx + 100, len(text) - 1)
                    
                    if search_start < len(text):
                        next_section_match = re.search(pattern, text[search_start:])
                        if next_section_match:
                            potential_end_idx = search_start + next_section_match.start()
                            if potential_end_idx < end_idx and potential_end_idx > start_idx + 50:  # Ensure minimum section length
                                end_idx = potential_end_idx
                
            # Get the section text and perform basic cleaning
            section_text = text[start_idx:end_idx].strip()
            
            # Remove any excessive whitespace or line breaks
            section_text = re.sub(r'\n{3,}', '\n\n', section_text)
            
            self.logger.debug(f"Extracted section text with pattern '{matched_pattern}' (first 200 chars): {section_text[:200]}...")
            
            # Check if the section is too short to be useful
            if len(section_text) < 30:  # Less than 30 chars is probably not a valid section
                self.logger.debug(f"Section text is too short ({len(section_text)} chars), likely not a valid section")
                return None
                
            return section_text
            
        except Exception as e:
            self.logger.error(f"Error finding section: {str(e)}")
            return None
    
    def extract_text(self, pdf_path: str) -> str:
        """Extract text from a PDF file using multiple methods"""
        try:
            self.logger.info(f"Processing {pdf_path}")
            
            # First try pymupdf4llm
            text = pymupdf4llm.to_markdown(pdf_path)
            
            # If text extraction yields little content, try OCR
            if self.use_ocr and (not text or len(text.strip()) < 100):
                self.logger.info("Text extraction yielded little content, trying OCR")
                ocr_text = self._extract_text_with_ocr(pdf_path)
                if ocr_text and len(ocr_text.strip()) > len(text.strip()):
                    text = ocr_text
                    
            if not text:
                self.logger.warning(f"No text extracted from {pdf_path}")
                return ""
                
            # Clean and normalize text
            text = self._clean_text(text)
            
            self.logger.info(f"Successfully extracted {len(text)} characters")
            self.logger.debug(f"First 1000 characters of extracted text:\n{text[:1000]}")
            return text
            
        except Exception as e:
            self.logger.error(f"Error processing PDF {pdf_path}: {str(e)}", exc_info=True)
            return ""
    
    def _extract_text_with_ocr(self, pdf_path: str) -> str:
        """Extract text from PDF using OCR"""
        try:
            # Convert PDF pages to images
            images = convert_from_path(pdf_path)
            
            # Process each page with OCR
            texts = []
            for i, image in enumerate(images):
                # Convert PIL image to bytes
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='PNG')
                img_byte_arr = img_byte_arr.getvalue()
                
                # Perform OCR
                text = pytesseract.image_to_string(Image.open(io.BytesIO(img_byte_arr)))
                texts.append(text)
                
            return "\n\n".join(texts)
            
        except Exception as e:
            self.logger.error(f"Error in OCR processing: {str(e)}")
            return ""
            
    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove page numbers and headers/footers
        text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
        
        # Fix common OCR errors
        text = text.replace('|', 'I')  # Common OCR mistake
        text = text.replace('0', 'O')  # In certain contexts
        
        # Remove duplicate lines
        return text
    
    def is_final_terms(self, filename: str) -> bool:
        """Check if a file is a final terms document"""
        return 'Final_terms' in filename or 'Final terms' in filename
    
    def clean_bank_name(self, bank: str) -> str:
        """Clean up bank name by removing noise and standardizing format"""
        if not bank or not isinstance(bank, str) or len(bank) < 3:
            return None
            
        # Remove common prefixes
        bank = re.sub(r'^(?:The\s+|M[rs]\.\s+|Messrs\.\s+|Each\s+of\s+(?:the\s+)?|to\s+|and\s+|with\s+|by\s+|or\s+|namely\s+|listed\s+below:?\s+)', '', bank, flags=re.IGNORECASE)
        
        # Remove any HTML or markdown
        bank = re.sub(r'<[^>]+>|\*\*|\[|\]|_{1,2}|~', '', bank)
        
        # Remove parenthetical text and bracketed content
        bank = re.sub(r'\([^)]*\)|\[[^\]]*\]|\{[^}]*\}', '', bank)
        
        # Remove common suffixes that include role descriptions
        role_patterns = [
            r'(?i)\s*(?:as\s+(?:global\s+coordinator|(?:joint\s+(?:lead\s+)?)manager|book(?:\-)?runner|joint\s+book(?:\-)?runner|co-manager|dealer|intermediary|stabili[sz]ation\s+manager|calculation\s+agent|paying\s+agent|trustee|registrar)s?)\s*$',
            r'(?i)\s*(?:is|are|has\s+been\s+appointed\s+(?:as)?)\s+(?:the|a|an|one\s+of\s+the|one\s+of)\s+(?:global\s+coordinator|(?:joint\s+(?:lead\s+)?)manager|book(?:\-)?runner|joint\s+book(?:\-)?runner|co-(?:lead\s+)?manager|dealer|intermediary|stabili[sz]ation\s+manager|calculation\s+agent|paying\s+agent|trustee|registrar)s?$',
            r'(?i)\s*(?:acts|acting|will\s+act|to\s+act|shall\s+act)\s+as\s+(?:the|a|an)\s+(?:global\s+coordinator|(?:joint\s+(?:lead\s+)?)manager|book(?:\-)?runner|joint\s+book(?:\-)?runner|co-manager|dealer|intermediary|stabili[sz]ation\s+manager|calculation\s+agent|paying\s+agent|trustee|registrar)s?$',
            r'(?i)\s*(?:in\s+its\s+capacity\s+as|in\s+the\s+capacity\s+of)\s+(?:the|a|an)\s+(?:global\s+coordinator|(?:joint\s+(?:lead\s+)?)manager|book(?:\-)?runner|joint\s+book(?:\-)?runner|co-manager|dealer|intermediary|stabili[sz]ation\s+manager|calculation\s+agent|paying\s+agent|trustee|registrar)s?$',
            # Added additional role patterns
            r'(?i)\s*(?:has|have)\s+been\s+(?:appointed|named|selected|chosen|engaged)\s+(?:as|to\s+be|to\s+act\s+as)\s+(?:the|a|an)\s+(?:global\s+coordinator|(?:joint\s+(?:lead\s+)?)manager|book(?:\-)?runner|joint\s+book(?:\-)?runner|co-manager|dealer|arranger|intermediary|stabili[sz]ation\s+manager|calculation\s+agent|paying\s+agent|trustee|registrar)s?$',
            r'(?i)\s*(?:together\s+with)?\s*(?:and\s+the\s+other)?\s*(?:joint\s+(?:lead\s+)?)managers?$',
            r'(?i)\s*(?:will\s+be|are|is)\s+the\s+(?:global\s+coordinator|(?:joint\s+(?:lead\s+)?)manager|book(?:\-)?runner|joint\s+book(?:\-)?runner|co-manager|dealer|arranger|intermediary|stabili[sz]ation\s+manager)s?$',
            r'(?i)\s*(?:which\s+(?:will|shall)\s+act\s+as)\s+(?:the|a|an)\s+(?:global\s+coordinator|(?:joint\s+(?:lead\s+)?)manager|book(?:\-)?runner|joint\s+book(?:\-)?runner|co-manager|dealer|arranger|intermediary|stabili[sz]ation\s+manager)s?$'
        ]
        
        for pattern in role_patterns:
            bank = re.sub(pattern, '', bank)
        
        # Remove common commercial/legal suffixes - but be careful with entities that include these in main name
        bank = re.sub(r'(?i)\s+(?:AG|S\.?A|N\.?V|plc|LLC|Ltd|Limited|Inc(?:orporated)?|Corporation|Corp|Group|GmbH|&\s*Co|KG|KGaA|S\.p\.A\.|S\.e\.n\.C\.S|International|Holdings|B\.V\.|Ges\.m\.b\.H\.|Co\.,\s*KG|Pty\s*Ltd\.?)$', '', bank)
        
        # Remove any trailing directional/geographical indicators (if standalone)
        bank = re.sub(r'(?i)\s+(?:SE|UK|USA|NA|US|GB|GR|FR|IT|DE|ES|NL|CH|AT|PL|DK|FI|NO|SE)$', '', bank)
        
        # Remove common location words at the end (if standalone)
        bank = re.sub(r'(?i)\s+(?:London|New\s+York|Frankfurt|Paris|Milan|Madrid|Amsterdam|Brussels|Zurich|Geneva|Vienna|Dublin)$', '', bank)
        
        # Remove punctuation from the end and excessive internal punctuation
        bank = re.sub(r'[.,;:\'\"]+$', '', bank)
        bank = re.sub(r'\s*[,;:]\s*(?=\s*[,;:])', ' ', bank)  # Remove duplicate punctuation
        
        # Clean up whitespace
        bank = re.sub(r'\s+', ' ', bank).strip()
        
        # Remove any remaining leading/trailing dash, colon, bullets, etc.
        bank = re.sub(r'^[-–—:•*=…]+|[-–—:•*=…]+$', '', bank).strip()
        
        # Skip if too short after cleaning
        if not bank or len(bank) < 3:
            return None
            
        # Standardize common bank names to handle variations
        bank_aliases = {
            # Major European banks
            r'(?i)^deutsche\s*(?:bank|securities|sec)(?:\s+(?:ag|aktiengesellschaft))?': 'Deutsche Bank',
            r'(?i)^(?:credit\s*suisse|cs\s+(?:securities|sec))(?:\s+(?:ag|sa|international))?': 'Credit Suisse',
            r'(?i)^(?:bnp\s*paribas|bnpp|fortis|bnp\s+fortis)(?:\s+(?:sa|securities|sec))?': 'BNP Paribas',
            r'(?i)^(?:societe\s*generale|socgen|société\s*générale|sg\s+(?:corporate|securities))(?:\s+(?:sa|cib))?': 'Société Générale',
            r'(?i)^(?:hsbc(?:\s+(?:bank|global|continental|securities|holdings|france|trinkaus))?|hongkong\s+and\s+shanghai\s+banking)': 'HSBC',
            r'(?i)^(?:barclays(?:\s+(?:bank|capital|investment|securities))?|barclays\s+securities)': 'Barclays',
            r'(?i)^(?:ing(?:\s+(?:bank|groep|group))?|ing\s+diba)': 'ING',
            r'(?i)^(?:unicredit(?:\s+(?:bank|spa|ag))?|hypovereinsbank|ucb|uni\s*credit)': 'UniCredit',
            r'(?i)^(?:banco\s+santander|santander(?:\s+(?:bank|securities|global|uk|investment))?)': 'Santander',
            r'(?i)^(?:crédit\s*agricole|ca\s*cib|credit\s*agricole|calyon)(?:\s+(?:cib|corporate|investment))?': 'Crédit Agricole',
            r'(?i)^(?:commerzbank|commerz)(?:\s+(?:ag|aktiengesellschaft))?': 'Commerzbank',
            r'(?i)^(?:natixis|natexis)(?:\s+(?:securities|bank|sa))?': 'Natixis',
            r'(?i)^(?:intesa\s+sanpaolo|intesa|banca\s+imi)(?:\s+(?:spa|bank))?': 'Intesa Sanpaolo',
            r'(?i)^(?:bbva|banco\s+bilbao\s+vizcaya\s+argentaria)(?:\s+(?:sa|securities))?': 'BBVA',
            r'(?i)^(?:abn\s+amro|abn|amro)(?:\s+(?:bank|group|nv))?': 'ABN AMRO',
            r'(?i)^(?:rabobank|rabobanknederland|coöperatieve\s+rabobank\s+u\.a\.)': 'Rabobank',
            r'(?i)^(?:dnb(?:\s+(?:bank|markets|asa|nor|group))?)': 'DNB',
            r'(?i)^(?:kbc(?:\s+(?:bank|group|securities|groep))?)': 'KBC',
            r'(?i)^(?:nordea(?:\s+(?:bank|markets|abp))?)': 'Nordea',
            r'(?i)^(?:seb|skandinaviska\s+enskilda\s+banken)(?:\s+(?:ab|bank))?': 'SEB',
            r'(?i)^(?:danske\s+bank|danske)(?:\s+(?:a/s|as|markets))?': 'Danske Bank',
            r'(?i)^(?:caixabank|la\s+caixa)(?:\s+(?:sa|s\.a\.))?': 'CaixaBank',
            r'(?i)^(?:ubi\s+banca|unione\s+di\s+banche)(?:\s+(?:italiane|s\.p\.a\.))?': 'UBI Banca',
            r'(?i)^(?:ubs(?:\s+(?:investment\s+bank|ag|limited|group|securities|europe))?)': 'UBS',
            r'(?i)^(?:banco\s+bpm|bpm|banca\s+popolare\s+di\s+milano)(?:\s+(?:s\.p\.a\.|s\.c\.a\.r\.l\.))?': 'Banco BPM',
            r'(?i)^(?:erste\s+group|erste)(?:\s+(?:bank|ag))?': 'Erste Group',
            r'(?i)^(?:crédit\s+mutuel|credit\s+mutuel)(?:\s+(?:cic|arkea|group))?': 'Crédit Mutuel',
            r'(?i)^(?:banca\s+monte\s+dei\s+paschi(?:\s+di\s+siena)?)(?:\s+(?:s\.p\.a\.|spa))?': 'Monte dei Paschi',
            r'(?i)^(?:bank\s+of\s+ireland|boi)(?:\s+(?:global\s+markets|group))?': 'Bank of Ireland',
            r'(?i)^(?:caixa\s+geral\s+de\s+depositos|cgd)': 'Caixa Geral de Depósitos',
            r'(?i)^(?:skandinaviska\s+enskilda\s+banken|seb)(?:\s+(?:ab|bank))?': 'SEB',
            r'(?i)^(?:belfius\s+bank|belfius)(?:\s+(?:sa|nv))?': 'Belfius',
            r'(?i)^(?:handelsbanken|svenska\s+handelsbanken)(?:\s+(?:ab|capital\s+markets))?': 'Handelsbanken',
            r'(?i)^(?:dz\s+bank|dz)(?:\s+(?:ag|deutsche\s+zentral-genossenschaftsbank))?': 'DZ Bank',
            r'(?i)^(?:la\s+banque\s+postale|lbp)': 'La Banque Postale',
            
            # Major US banks
            r'(?i)^(?:morgan\s*stanley(?:\s+(?:&\s+co|securities|sec|smith\s+barney|dean\s+witter))?)': 'Morgan Stanley',
            r'(?i)^(?:goldman\s*sachs(?:\s+(?:&\s+co|group|international|bank))?)(?:\s+(?:securities|sec))?': 'Goldman Sachs',
            r'(?i)^(?:j\.?p\.?\s*morgan(?:\s+(?:chase|securities|stanley|cazenove|sec))?)': 'JP Morgan',
            r'(?i)^(?:jpmorgan|jpm|j\.?p\.?m\.?)(?:\s+(?:chase|securities|sec))?': 'JP Morgan',
            r'(?i)^(?:citi(?:group|corp|bank)?|citigroup\s+global\s+markets)(?:\s+(?:inc|international|global|securities|europe|na))?': 'Citigroup',
            r'(?i)^(?:bofa(?:\s+(?:securities|merrill\s*lynch))?|merrill\s*lynch|bank\s*of\s*america(?:\s+securities)?)': 'BofA Securities',
            r'(?i)^(?:wells\s*fargo(?:\s+(?:securities|bank|advisors))?)': 'Wells Fargo',
            r'(?i)^(?:rbc(?:\s+(?:capital\s+markets|dominion\s+securities|cm|europe))?|royal\s+bank\s+of\s+canada)': 'RBC',
            r'(?i)^(?:scotiabank|scotia\s*(?:bank|capital)?|bank\s+of\s+nova\s+scotia)': 'Scotiabank',
            r'(?i)^(?:td\s+(?:bank|securities|global)|toronto(?:\-|\s+)dominion)': 'TD Securities',
            r'(?i)^(?:bmo(?:\s+(?:capital\s+markets|financial\s+group|nesbitt\s+burns))?|bank\s+of\s+montreal)': 'BMO',
            r'(?i)^(?:pnc(?:\s+(?:bank|financial\s+services|capital\s+markets))?)': 'PNC',
            r'(?i)^(?:us\s+bancorp|u\.?s\.?\s+bank)': 'US Bank',
            r'(?i)^(?:jefferies(?:\s+(?:llc|group|international))?)': 'Jefferies',
            r'(?i)^(?:raymond\s+james(?:\s+(?:financial|investment\s+services))?)': 'Raymond James',
            r'(?i)^(?:stifel(?:\s+(?:nicolaus|financial))?)': 'Stifel',
            r'(?i)^(?:cowen(?:\s+(?:and\s+company|group|inc))?)': 'Cowen',
            
            # Major Asian banks
            r'(?i)^(?:nomura(?:\s+(?:international|securities|holdings|sec))?)': 'Nomura',
            r'(?i)^(?:mizuho(?:\s+(?:international|securities|bank|financial\s+group|sec))?)': 'Mizuho',
            r'(?i)^(?:mufg|mitsubishi\s+ufj|mitsubishi\s+financial\s+group)(?:\s+(?:securities|sec))?': 'MUFG',
            r'(?i)^(?:sumitomo\s+mitsui|smbc|smbc\s+nikko)(?:\s+(?:banking\s+corporation|financial\s+group))?': 'SMBC',
            r'(?i)^(?:dbs(?:\s+(?:bank|group))?)': 'DBS',
            r'(?i)^(?:standard\s*chartered|stanchart)(?:\s+(?:bank|plc|securities))?': 'Standard Chartered',
            r'(?i)^(?:icbc(?:\s+(?:standard\s+bank|asia|international))?)': 'ICBC',
            r'(?i)^(?:bank\s+of\s+china|boc(?:\s+(?:international|securities|hong\s+kong)))': 'Bank of China',
            r'(?i)^(?:china\s+(?:construction|development)\s+bank|ccb)(?:\s+(?:asia|international))?': 'China Construction Bank',
            r'(?i)^(?:agricultural\s+bank\s+of\s+china|abc)': 'Agricultural Bank of China',
            r'(?i)^(?:australia(?:n)?\s+and\s+new\s+zealand\s+banking\s+group|anz)(?:\s+(?:bank|banking\s+group|securities))?': 'ANZ',
            r'(?i)^(?:commonwealth\s+bank\s+of\s+australia|cba)': 'Commonwealth Bank',
            r'(?i)^(?:national\s+australia(?:n)?\s+bank|nab)': 'National Australia Bank',
            r'(?i)^(?:westpac(?:\s+(?:banking\s+corporation|group))?)': 'Westpac',
            r'(?i)^(?:macquarie(?:\s+(?:bank|group|capital))?)': 'Macquarie',
            r'(?i)^(?:bank\s+of\s+communications|bocom)': 'Bank of Communications',
            
            # Other international banks
            r'(?i)^(?:national\s+bank\s+of\s+canada|nbc)': 'National Bank of Canada',
            r'(?i)^(?:bank\s+of\s+america|bofa)': 'Bank of America',
            r'(?i)^(?:danske\s+bank|danske)': 'Danske Bank',
            r'(?i)^(?:la\s+caixa|caixabank)': 'CaixaBank',
            r'(?i)^(?:dekabank|deka)': 'DekaBank',
            r'(?i)^(?:landesbank\s+baden\-wuerttemberg|lbbw)': 'LBBW',
            r'(?i)^(?:bayerische\s+landesbank|bayernlb)': 'BayernLB',
            r'(?i)^(?:landesbank\s+hessen\-thueringen|helaba)': 'Helaba',
            r'(?i)^(?:norddeutsche\s+landesbank|nord\s*lb)': 'NORD/LB',
            r'(?i)^(?:nykredit)': 'Nykredit',
            r'(?i)^(?:investec(?:\s+(?:bank|securities))?)': 'Investec',
            r'(?i)^(?:standard\s+bank(?:\s+of\s+south\s+africa)?)': 'Standard Bank',
            r'(?i)^(?:nedbank(?:\s+(?:group|limited))?)': 'Nedbank',
            r'(?i)^(?:absa(?:\s+(?:bank|group|capital))?)': 'Absa',
            r'(?i)^(?:itau(?:\s+(?:unibanco|bba))?)': 'Itau',
            r'(?i)^(?:bradesco(?:\s+(?:bBI|securities|s\.a\.))?)': 'Bradesco',
            r'(?i)^(?:banco\s+do\s+brasil|bb(?:\s+securities)?)': 'Banco do Brasil'
        }
        
        for pattern, replacement in bank_aliases.items():
            if re.search(pattern, bank):
                return replacement
                
        return bank
    
    def is_valid_bank_name(self, bank: str) -> bool:
        """
        Check if a string is likely a valid bank name and not a false positive.
        Returns True if the string is likely a bank name, False otherwise.
        
        This method is specifically tailored to handle various PDF formats,
        including TotalEnergies PDFs which may have special formatting.
        """
        if not bank or not isinstance(bank, str):
            return False
            
        # Clean up the string
        bank = bank.strip()
        if bank == "" or len(bank) < 3:
            return False

        # List of terms known not to be bank names, but might be extracted
        invalid_banks = {
            "n/a", "none", "nil", "tbc", "tbd", "not applicable", "not appointed", 
            "not available", "see above", "see below", "to be determined", "to be completed",
            "to be appointed", "to be confirmed", "as above", "as defined", "as specified", 
            "as detailed", "as outlined", "as indicated", "as set out", "as described",
            "for the avoidance of doubt", "please refer to", "please see", "as mentioned",
            "in this respect", "in accordance with", "refer to", "see note", "see section",
            "please note", "please contact", "issued by", "guaranteed by", "not relevant",
            "not required", "if applicable", "if any", "if needed", "any dealer",
            "calculation agent", "paying agent", "fiscal agent", "listing agent",
            "transfer agent", "determination agent", "settlement agent", "subscription",
            "securities", "payment date", "issuer", "settlement date",
            "maturity date", "redemption date", "issue date", "clearing system",
            # More document-specific terms
            "the base prospectus", "base prospectus", "final terms", "pricing supplement",
            "information memorandum", "offering circular", "offering document",
            "listing document", "registration document", "programme document",
            # Common formatting and placeholders
            "[•]", "[...]", "[name]", "[details]", "[•••]", "[bank]", "[party]", 
            "********", "________", "xxx", "xxxxxx", "insert", "specify",
            # Units and numbers
            "eur", "usd", "gbp", "jpy", "chf", "cad", "aud", "nzd", "%", "bps",
            "original face", "outstanding", "principal amount", "billion", "million", "thousand",
            "page", "annex", "paragraph", "section", "clause",
            # Additional invalid terms
            "this prospectus", "dated", "agent", "n.v", "sa", "s.a", "ag", "plc", "ltd", "inc", 
            "set forth", "set out", "set forth in", "set out in", "indicated in", "described in",
            "amended", "modified", "supplemented", "replaced", "novated",
            "applicable", "relevant", "respective", "corresponding", "appropriate",
            "administrator", "trustee", "benchmark", "index", "rate", "reference",
            "principal", "interest", "coupon", "issuance", "tranche", "series",
            "legal entity identifier", "lei", "isin", "cusip", "sedol", "wkn", "valor",
            "stock exchange", "market", "regulated market", "trading venue", "listing",
            "jurisdiction", "authority", "regulator", "competent authority",
            "the company", "the corporation", "the entity", "the institution", "the enterprise",
            "as set forth", "as set out", "as described in", "as defined in", "as specified in",
            "each manager", "each dealer", "each of the managers", "each of the dealers",
            "collectively", "together", "separately", "individually", "on behalf of",
            "as to", "with respect to", "in respect of", "on the basis of", "by virtue of",
            "code", "euroclear", "clearstream", "dtc", "cbf", "exchanges", "trading"
        }
        
        # Lowercase the bank name for case-insensitive matching
        bank_lower = bank.lower()
        
        # Check if this is an exact match with an invalid term
        if bank_lower in invalid_banks:
            return False
            
        # Check if the bank name consists of mostly/only digits
        if re.match(r'^\d+\.?$|^\d{1,3}(?:,\d{3})*(?:\.\d+)?$', bank_lower):  # Numbers or currency amounts
            return False
            
        # Check for invalid starts with characters that suggest it's not a proper name
        if bank.startswith((':', '.', '-', '/', '*', '(', ')', '[', ']', '{', '}', '"', '"', "'", "'", "<", ">")):
            return False
            
        # Check for phrases that indicate the string is likely not a bank name
        invalid_phrases = [
            # Indicators of form content rather than a bank name  
            r'(?i)^(?:to be|not|tbc|tbd|tba|included|completed|determined|confirmed|signed|dated|contact|provided|named)',
            r'(?i)^(?:as|per|in|on|at|by|for|from|with|under|pursuant|according|subject|refer|see)\s+',
            r'(?i)(?:applicable|provisions|conditions|disclaimers?|requirements?)',
            r'(?i)as\s+(?:defined|specified|described|detailed|mentioned|listed|noted|set\s+out|indicated)',
            
            # Legal/document phrases
            r'(?i)pursuant\s+to|according\s+to|with\s+respect\s+to|in\s+accordance\s+with|in\s+relation\s+to',
            
            # Form response phrases  
            r'(?i)(?:not|to\s+be)\s+applicable|not\s+available|see\s+(?:above|below|section|page|par|paragraph)',
            
            # Section references that might be confused with bank names
            r'(?i)section\s+\d+|paragraph\s+\d+|page\s+\d+|clause\s+\d+|annex\s+\d+',
            
            # Common numeric expressions that aren't bank names
            r'(?i)\d+(?:\.\d+)?\s*(?:%|per\s*cent|percent|basis\s*points?|bps|EUR|USD|GBP|€|\$|£)',
            
            # Additional indicators of non-bank text
            r'(?i)dated\s+(?:as\s+of)?\s+\d',
            r'(?i)table\s+of\s+contents?',
            r'(?i)page\s+\d+\s+of\s+\d+',
            r'(?i)^\s*\d+\s*$',  # Just a number
            r'(?i)none\s+of\s+the\s+(?:above|dealers|managers)',
            r'(?i)please\s+(?:see|refer)',
            r'(?i)for\s+further\s+information',
            r'(?i)for\s+the\s+purposes?\s+of',
            r'(?i)may\s+be\s+(?:amended|modified|supplemented)',
            r'(?i)head\s+office',
            r'(?i)registered\s+office',
            r'(?i)principal\s+office',
            r'(?i)business\s+address',
            r'(?i)contact\s+(?:details|information)',
            r'(?i)terms\s+and\s+conditions',
            r'(?i)www\.|http:\/\/|https:\/\/',  # URLs
            
            # Additional invalid phrases
            r'(?i)^(?:the|a|an)\s+(?:issuer|guarantor|obligor|borrower|lender|creditor|debtor)',
            r'(?i)^(?:legal|general|central|national|federal|regional|corporate|retail|commercial|private|public)',
            r'(?i)^(?:terms|conditions|provisions|requirements|regulations|criteria|standards|guidelines)',
            r'(?i)^(?:first|second|third|fourth|fifth|primary|secondary|tertiary|final|initial|additional)',
            r'(?i)^(?:following|preceding|subsequent|prior|next|previous|current|former|latter)',
            r'(?i)^(?:description|summary|overview|introduction|conclusion|background|context)',
            r'(?i)^(?:minimum|maximum|average|total|aggregate|partial|full|entire|complete)',
            r'(?i)^(?:including|excluding|other\s+than|except\s+for|apart\s+from|besides)',
            r'(?i)authorized|regulated|supervised|incorporated|established|domiciled|headquartered',
            r'(?i)responsible|liable|accountable|obligated|bound|required|expected',
            r'(?i)the\s+(?:following|aforementioned|undersigned|above\-named|below\-named)',
            r'(?i)both|either|neither|each|every|all|any|some|most|many|few|several',
            r'(?i)(?:all|each|any|some|none)\s+of\s+(?:the|these|those|such)',
            r'(?i)(?:before|after|during|throughout|within|outside)\s+(?:the|such|this|that|these|those)',
            r'(?i)subject\s+to|contingent\s+upon|dependent\s+on|reliant\s+on|based\s+on',
            r'(?i)reference\s+to|attention\s+to|respect\s+to|regard\s+to|relation\s+to',
            r'(?i)regulated\s+by|authorized\s+by|supervised\s+by|governed\s+by|controlled\s+by',
            r'(?i)authorised\s+and\s+regulated|incorporated\s+and\s+registered',
            r'(?i)acting\s+through\s+its|operating\s+through\s+its|represented\s+by\s+its',
            r'(?i)under\s+the\s+laws\s+of|in\s+accordance\s+with\s+the\s+laws\s+of',
            r'(?i)incorporated\s+in|established\s+in|organized\s+in|formed\s+in|domiciled\s+in',
            r'(?i)effective\s+(?:as\s+of|from|on|until|through|during)',
            r'(?i)address|telephone|email|fax|website|contact',
            r'(?i)further\s+information|additional\s+details|more\s+details',
            r'(?i)prospective|potential|future|anticipated|expected|projected|forecasted',
            r'(?i)intended|designed|meant|aimed|purposed|planned|scheduled',
            r'(?i)similar\s+to|comparable\s+to|equivalent\s+to|equal\s+to',
            r'(?i)different\s+from|distinct\s+from|separate\s+from|apart\s+from',
            r'(?i)contrary\s+to|opposed\s+to|against|versus|vs\.',
            
            # TotalEnergies specific phrases
            r'(?i)final\s+terms',
            r'(?i)terms\s+used\s+herein',
            r'(?i)debt\s+issuance\s+programme',
            r'(?i)issuer\s+and\s+the\s+offer',
            r'(?i)deeply\s+subordinated',
            r'(?i)date\s+approval\s+for',
            r'(?i)permanent\s+global\s+note',
            r'(?i)fixed\s+rate\s+resettable',
            r'(?i)issuance\s+programme\s+prospectus',
            r'(?i)amounts\s+payable\s+under',
            r'(?i)national\s+numbering\s+agency',
            r'(?i)the\s+issuer\s+intends',
            r'(?i)subsidiary\s+of\s+the\s+issuer',
            r'(?i)s&p\s+(?:from|to)',
            r'(?i)repurchase\s+or\s+redemption',
            r'(?i)target\s+market',
            r'(?i)mifid\s+ii\s+product',
            r'(?i)professional\s+investors',
            r'(?i)on\s+\d+\s+\w+\s+20\d\d',  # Date patterns
            
            # Additional TotalEnergies specific formatting
            r'(?i)\*\*[^*]+\*\*',  # Markdown formatting
            r'(?i)euribor',
            r'(?i)libor',
            r'(?i)dealer\s+agreement',
            r'(?i)credit\s+rating',
            r'(?i)rating\s+agency',
            r'(?i)green\s+bond',
            r'(?i)sustainability',
            r'(?i)programme\s+agreement',
            r'(?i)fiscal\s+agency\s+agreement',
            r'(?i)terms\s+and\s+conditions\s+of',
            r'(?i)dated\s+\d+\s+\w+\s+20\d\d',
            r'(?i)dated\s+the\s+\d+\s+\w+\s+20\d\d',
            r'(?i)authority\s+to\s+issue',
            r'(?i)interest\s+basis',
            r'(?i)redemption\s+basis',
            r'(?i)listing\s+rules',
            r'(?i)regulation\s+s',
            r'(?i)regulation\s+d'
        ]
        
        for phrase in invalid_phrases:
            if re.search(phrase, bank):
                # Special exception for bank names that might contain filtered text
                if re.match(r'(?i)(?:bank of america|credit suisse|credit agricole)', bank):
                    continue
                return False
        
        # Known problematic entries from TotalEnergies PDFs
        problem_phrases = [
            'ESMA on', 'EU MiFID II', 'Terms used herein', 'Debt Issuance Programme',
            'Issuer and the offer', 'Deeply Subordinated Date', 'Fixed Rate Resettable',
            'Permanent Global Note', 'Save', 'Issuance Programme Prospectus',
            'Amounts payable under', 'EURIBOR which', 'National Numbering Agency',
            'Issuer intends', 'Subsidiary of the Issuer', 'S&P from time', 'S&P to the Issuer',
            'S&P and the Issuer', 'Issuer such repurchase', 'S&P would', 'European Economic',
            'Agency Agreement', 'Exchange Notice', 'Regulation S', 'Moody\'s', 'Fitch Ratings',
            'Prospectus Regulation', 'Approval by', 'Exchange Rate', 'Exchange Notice',
            'Paying Agent', 'Calculation Agent', 'Each Dealer', 'Each Manager'
        ]
        
        for phrase in problem_phrases:
            if phrase.lower() in bank_lower:
                return False
                
        # Remove legal entity suffixes for further checks
        test_name = re.sub(r'(?i)\s+(?:AG|S\.?A|N\.?V|plc|LLC|Ltd|Limited|Inc|Corporation|Corp|Group|GmbH)$', '', bank)
        
        # Check if the name is overly generic 
        if len(test_name) < 4:  # Too short after removing suffixes
            return False
            
        # ----------------
        # POSITIVE CHECKS - Specifically recognize valid banks including TotalEnergies PDF format
        # ----------------
            
        # Check common banks with specific handling for TotalEnergies format
        # TotalEnergies PDFs often have concatenated bank names
        if any(bank_name in bank_lower for bank_name in [
            "smbc bank eu ag", 
            "hsbc continental europe", 
            "bofa securities europe", 
            "natixissmbc", 
            "natixis continental",
            "jp morgan securities plc",
            "bofa securities france",
            "smbchsbc",
            "smbc nikko",
            "hsbc france",
            "credit agricole cib",
            "bofanp paribas"
        ]):
            return True
            
        # Handle specific concatenated bank names in TotalEnergies format
        # Split and check if parts match known banks
        parts = re.split(r'\s+(?=(?:[A-Z][a-z]+|[A-Z]{2,}))', bank)
        known_bank_parts = [
            'HSBC', 'BofA', 'Securities', 'Europe', 'SA', 'Continental', 
            'Natixis', 'SMBC', 'Bank', 'EU', 'AG', 'JP', 'Morgan', 'Nikko',
            'Credit', 'Agricole', 'CIB', 'BNP', 'Paribas', 'Société', 'Générale',
            'Crédit', 'Citi', 'Citibank', 'Deutsche', 'UBS', 'Nomura'
        ]
        
        # Special check for concatenated names in TotalEnergies PDFs
        concat_check = False
        for part in parts:
            if part in known_bank_parts:
                concat_check = True
                break
                
        if concat_check:
            # These patterns commonly appear in TotalEnergies PDFs
            bank_pairs = [
                ('natixis', 'smbc'),
                ('bofa', 'securities'),
                ('hsbc', 'continental'),
                ('jp', 'morgan'),
                ('credit', 'agricole'),
                ('citi', 'bank'),
                ('bnp', 'paribas'),
                ('societe', 'generale'),
                ('deutsche', 'bank'),
                ('nomura', 'international'),
                ('bofa', 'merrill'),
                ('smbc', 'nikko')
            ]
            
            for pair in bank_pairs:
                if pair[0] in bank_lower and pair[1] in bank_lower:
                    return True
            
        # Bank names typically have at least one capital letter
        # Skip for known abbreviations
        if bank.islower() and len(bank) > 5:  # Longer names should have capitals
            # Check for known lowercase bank abbreviations first
            if not any(abbr in bank_lower for abbr in ['sa', 'ag', 'nv', 'plc']):
                return False
            
        # Check if name is suspiciously short but not a known abbreviation (like "UBS", "ING", "RBC")
        known_short_banks = {
            "ubs", "ing", "rbc", "bnp", "kbc", "cba", "hsbc", "bbva", "icbc", "cib", 
            "dbs", "seb", "dnb", "boc", "ccb", "otp", "pbb", "snb", "eib", "ebrd",
            "sa", "ag", "eu", "nv" # Add common legal suffixes that might be part of a bank name
        }
        
        if len(test_name) <= 3 and test_name.lower() not in known_short_banks:
            return False
            
        # Check for markdown formatting specific to TotalEnergies PDFs
        # Sometimes valid bank names appear after markdown formatting
        if "**" in bank:
            # Extract the part after the last markdown
            markdown_parts = bank.split("**")
            if len(markdown_parts) > 1:
                potential_bank = markdown_parts[-1].strip()
                # If this part passes length and capitalization checks, it might be a bank
                if len(potential_bank) > 4 and not potential_bank.islower():
                    # Check if it contains known bank parts
                    for part in known_bank_parts:
                        if part.lower() in potential_bank.lower():
                            return True
        
        # Positively identify known banks - enhanced for TotalEnergies format
        known_bank_patterns = [
            r'(?i)barclays',
            r'(?i)goldman\s*sachs',
            r'(?i)morgan\s*stanley',
            r'(?i)credit\s*suisse',
            r'(?i)deutsche\s*bank',
            r'(?i)jp\s*morgan|jpmorgan',
            r'(?i)hsbc',
            r'(?i)bnp\s*paribas',
            r'(?i)citi(?:group|bank)?',
            r'(?i)soci[eé]t[eé]\s*g[eé]n[eé]rale',
            r'(?i)ubs',
            r'(?i)nomura',
            r'(?i)mizuho',
            r'(?i)mufg',
            r'(?i)bofa\s*securities|bank\s*of\s*america',
            r'(?i)santander',
            r'(?i)unicredit',
            r'(?i)wells\s*fargo',
            r'(?i)rbc|royal\s*bank\s*of\s*canada',
            r'(?i)td\s*securities',
            r'(?i)ing',
            r'(?i)cr[eé]dit\s*agricole',
            r'(?i)natixis',
            r'(?i)commerzbank',
            r'(?i)bbva',
            r'(?i)intesa\s*sanpaolo',
            r'(?i)dbs',
            r'(?i)standard\s*chartered',
            r'(?i)nordea',
            r'(?i)danske',
            r'(?i)abn\s*amro',
            r'(?i)kbc',
            r'(?i)rabobank',
            r'(?i)dnb',
            r'(?i)seb',
            r'(?i)citibank',
            r'(?i)smbc',
            r'(?i)nikko',
            r'(?i)itau',
            r'(?i)scotia',
            r'(?i)mitsubishi',
            r'(?i)sumitomo',
            r'(?i)caixabank',
            r'(?i)erste',
            r'(?i)lloyds',
            r'(?i)nationwide',
            r'(?i)natwest',
            r'(?i)morgan\s*chase',
            r'(?i)merrill\s*lynch',
            r'(?i)rothschild',
            # French banks commonly in TotalEnergies docs
            r'(?i)caisse\s*d[e\']\s*[eé]pargne',
            r'(?i)la\s*banque\s*postale',
            r'(?i)bpce',
            r'(?i)exane',
            r'(?i)oddo',
            r'(?i)palatine',
            r'(?i)helaba',
            r'(?i)investec',
            r'(?i)mediobanca',
            r'(?i)bayernlb'
        ]
        
        for pattern in known_bank_patterns:
            if re.search(pattern, bank):
                return True
                
        # Final check - if the name looks like a proper noun (starts with capital) and isn't too generic
        # This is more permissive, but having passed all the negative checks above, it's more likely valid
        if re.match(r'^[A-Z][a-z]', bank) and len(bank) > 6:
            # Check if it also has bank-like words
            bank_indicators = [
                'bank', 'capital', 'securities', 'markets', 'investment', 'asset', 
                'financial', 'credit', 'finance', 'partners', 'advisors', 'holdings',
                'banking', 'global', 'international', 'continental', 'trust', 'lending',
                'grupo', 'banque', 'banca', 'banc', 'caisse', 'caja'
            ]
            
            for indicator in bank_indicators:
                if indicator.lower() in bank_lower:
                    return True
                    
            # One last check - if it's a proper noun with sufficient length, not rejected by earlier rules
            # it's more likely a valid entity than not
            if len(bank) > 10 and ' ' in bank and not any(c.isdigit() for c in bank):
                return True
                
        # Check for typical bank legal entity suffixes
        bank_suffixes = [
            r'(?i)\s+AG$', 
            r'(?i)\s+S\.?A\.?$', 
            r'(?i)\s+N\.?V\.?$', 
            r'(?i)\s+plc$', 
            r'(?i)\s+Limited$', 
            r'(?i)\s+Ltd\.?$',
            r'(?i)\s+Inc\.?$', 
            r'(?i)\s+LLC$', 
            r'(?i)\s+LLP$', 
            r'(?i)\s+Corp\.?$', 
            r'(?i)\s+Corporation$',
            r'(?i)\s+Group$', 
            r'(?i)\s+Holdings$', 
            r'(?i)\s+GmbH$',
            r'(?i)\s+Co\.?$', 
            r'(?i)\s+Cie$'
        ]
        
        for suffix in bank_suffixes:
            if re.search(suffix, bank):
                # If it has a proper legal suffix and passed all negative checks, likely valid
                if len(bank) > 6 and not bank.islower():
                    return True
        
        # Looks too suspicious, reject
        return False
    
    def _extract_banks_and_roles(self, text: str) -> Dict:
        """
        Extract bank names and their roles from the document text.
        Uses multiple extraction strategies and confidence levels.
        
        Returns a dictionary containing:
        - extracted_banks: List of dictionaries with bank info (raw_name, role, standard_name, confidence)
        - bank_sections: Sections of text where banks were found
        """
        try:
            result = {
                "extracted_banks": [],
                "bank_sections": {}
            }
            
            # ---- Step 1: Find relevant sections ----
            relevant_sections = {}
            
            # Distribution/Underwriting section - expanded options
            distribution_markers = [
                "Distribution",
                "Plan of Distribution",
                "Subscription and Sale",
                "Placement of the Notes",
                "Placement and Underwriting",
                "Underwriting",
                "Underwriting Arrangement",
                "Syndicate",
                "Selling Arrangements",
                "Offer Structure",
                "Offering and Placement",
                "Distribution Structure",
                "Offering Information",
                # Additional distribution markers
                "Distribution of Notes",
                "Method of Distribution",
                "Offering and Sale",
                "Terms of the Offering",
                "Purchase and Sale",
                "Dealers and Arrangements",
                "Purchase Agreement",
                "Offer and Listing Details",
                "Marketing and Placement",
                "Conditions of the Offer",
                "Details of the Offer",
                "Method and Time Limits for Paying Up",
                "Offering Structure and Price",
                "Underwriting Commitment",
                "Offering Memorandum"
            ]
            
            for marker in distribution_markers:
                section = self.find_section(text, marker)
                if section:
                    relevant_sections["distribution"] = section
                    self.logger.info(f"Found distribution section with marker: {marker}")
                    break
            
            # Managers/Bookrunners section - expanded options
            manager_markers = [
                "Managers",
                "Joint Lead Managers",
                "Bookrunners",
                "Joint Bookrunners",
                "Names and Addresses of Managers",
                "Names of Managers",
                "Dealers",
                "Dealer Information",
                "Underwriters",
                "Syndicate Members",
                "Management Group",
                "Lead Managers",
                "Global Coordinators",
                "Co-Managers",
                "Placement Agents",
                "Management and Underwriting",
                # Additional manager markers
                "Manager Details",
                "Managers of the Issue",
                "List of Managers",
                "Dealer Agreement",
                "Lead Manager and Bookrunner",
                "Authorised Participants",
                "Arranger",
                "Joint Lead Arrangers",
                "Dealer Managers",
                "Managers of the Offering",
                "Bookrunner Information",
                "Names and Addresses of Initial Purchasers",
                "Names and Addresses of the Bookrunners",
                "Principal Dealers",
                "Coordinator and Bookrunner",
                "Primary Dealer",
                "Initial Purchasers",
                "Financial Intermediaries",
                "Sole Bookrunner",
                "Placing Agents",
                "Sole Global Coordinator",
                "Trading Participants"
            ]
            
            for marker in manager_markers:
                section = self.find_section(text, marker)
                if section:
                    relevant_sections["managers"] = section
                    self.logger.info(f"Found managers section with marker: {marker}")
                    break
            
            # Stabilisation Manager section - expanded options
            stabilisation_markers = [
                "Stabilisation Manager",
                "Stabilization Manager",
                "Stabilising Manager",
                "Stabilizing Manager",
                "Stabilisation",
                "Stabilization",
                "Market Stabilisation",
                "Price Stabilisation"
            ]
            
            for marker in stabilisation_markers:
                section = self.find_section(text, marker)
                if section:
                    relevant_sections["stabilisation"] = section
                    self.logger.info(f"Found stabilisation section with marker: {marker}")
                    break
            
            # Additional sections that might contain bank information
            additional_markers = {
                "participants": [
                    "Transaction Participants",
                    "Programme Participants",
                    "Parties to the Transaction",
                    "Parties to the Offer",
                    "Participating Entities"
                ],
                "summary": [
                    "Summary of the Terms",
                    "Principal Terms",
                    "Key Parties",
                    "Principal Parties",
                    "Summary of Participants"
                ],
                "contacts": [
                    "Contact Information",
                    "Contact Details",
                    "Addresses",
                    "Names and Addresses"
                ]
            }
            
            for section_type, markers in additional_markers.items():
                for marker in markers:
                    section = self.find_section(text, marker)
                    if section:
                        relevant_sections[section_type] = section
                        self.logger.info(f"Found {section_type} section with marker: {marker}")
                        break
            
            # Store found sections in result
            result["bank_sections"] = relevant_sections
            
            # ---- Step 2: Extract banks from each section ----
            banks_found = set()  # Track unique banks to avoid duplicates
            
            # Special handling for Total Energies and similar heavily formatted PDFs
            # These often use bold/markdown formatting and specific structures
            if "managers" in relevant_sections:
                managers_section = relevant_sections["managers"]
                
                # Check for special formatting patterns like **Global** **Coordinators**
                if "**" in managers_section:
                    self.logger.info("Detected markdown formatting in managers section, applying special extraction")
                    
                    # Extract role patterns (text between ** markers)
                    role_patterns = re.findall(r'\*\*([^*]+)\*\*', managers_section)
                    if role_patterns:
                        # Combine adjacent role patterns that might be split (like "Global" "Coordinators")
                        combined_role = " ".join(role_patterns)
                        self.logger.info(f"Extracted role from markdown: {combined_role}")
                        
                        # Now extract bank names that follow the role patterns
                        # Look for capitalized words after the last ** marker
                        bank_section = re.split(r'\*\*[^*]+\*\*', managers_section)[-1]
                        
                        # Potential bank names (look for capitalized entities)
                        bank_candidates = re.findall(r'([A-Z][A-Za-z]+(?:\s+[A-Za-z]+){0,5}(?:\s+(?:Bank|Group|Securities|Capital|Markets|Ireland|International|Europe|AG|PLC|S\.A\.|N\.V\.|Inc\.|Ltd\.)))', bank_section)
                        
                        for bank in bank_candidates:
                            cleaned_bank = self.clean_bank_name(bank)
                            if cleaned_bank and self.is_valid_bank_name(cleaned_bank) and cleaned_bank not in banks_found:
                                banks_found.add(cleaned_bank)
                                result["extracted_banks"].append({
                                    "raw_name": bank,
                                    "cleaned_name": cleaned_bank,
                                    "role": combined_role,
                                    "confidence": 0.9,
                                    "source": "managers_section_markdown"
                                })
                
                # Look for specific bank names in fixed formats (used in many PDFs)
                bank_patterns = [
                    # Common bank names with various entity types
                    r'((?:BNP\s+Paribas|Deutsche\s+Bank|Credit\s+Suisse|Morgan\s+Stanley|Goldman\s+Sachs|JP\s*Morgan|HSBC|Barclays|UBS|Citi(?:group)?|Nomura|Mizuho|MUFG|Santander|UniCredit|ING|Crédit\s+Agricole|Natixis|BBVA|Commerzbank)(?:\s+(?:Bank|Securities|Capital|Markets|AG|PLC|S\.A\.|N\.V\.|Inc\.|Ltd\.)?){0,2})',
                    
                    # Banks in a list format
                    r'(?:^|\n)[\s•\-]*([A-Z][A-Za-z\s]+(?:Bank|Securities|Capital|Markets|AG|PLC|S\.A\.|N\.V\.|Inc\.|Ltd\.)?)',
                    
                    # Banks with various entity types
                    r'([A-Z][A-Za-z]+(?:\s+[A-Za-z]+){0,5}(?:\s+(?:Bank|Securities|Capital|Markets|AG|PLC|S\.A\.|N\.V\.|Inc\.|Ltd\.)))'
                ]
                
                # Extract banks using the patterns
                for pattern in bank_patterns:
                    bank_matches = re.findall(pattern, managers_section)
                    for bank in bank_matches:
                        cleaned_bank = self.clean_bank_name(bank.strip())
                        if cleaned_bank and self.is_valid_bank_name(cleaned_bank) and cleaned_bank not in banks_found:
                            # Try to identify role from context
                            role_context = managers_section[:managers_section.find(bank)]
                            
                            # Check for role indicators
                            role = "Manager"  # Default role
                            if "**" in role_context:
                                # Extract the most recent role indicated by markdown
                                role_matches = re.findall(r'\*\*([^*]+)\*\*', role_context)
                                if role_matches:
                                    role = " ".join(role_matches)
                            elif re.search(r'(?:Joint\s+Lead|Global\s+Coordinators|Bookrunners|Dealers)', role_context, re.IGNORECASE):
                                role_match = re.search(r'((?:Joint\s+Lead|Global\s+Coordinators|Bookrunners|Dealers|Lead\s+Managers)[^:]*)', role_context, re.IGNORECASE)
                                if role_match:
                                    role = role_match.group(1)
                            
                            banks_found.add(cleaned_bank)
                            result["extracted_banks"].append({
                                "raw_name": bank,
                                "cleaned_name": cleaned_bank,
                                "role": role,
                                "confidence": 0.95,
                                "source": "managers_section_direct"
                            })
            
            # Define extraction patterns for different types of listing formats
            extraction_patterns = {
                # Format: "Role: Bank Name"
                "role_then_bank": [
                    # Simple role followed by bank name
                    r'(?P<role>(?:(?:Lead|Joint(?:\s+Lead)?|Sole|Co-Lead|Co-|Global)?\s*(?:Manager|Book(?:-)?Runner|Bookrunner|Dealer|Underwriter|Coordinator|Arranger)s?))[:\s]+(?P<bank>[A-Z][A-Za-z0-9\s\.,&\(\)\-\']{2,40})(?=\s*(?:and|,|;|\n|$))',
                    
                    # Multi-word role followed by bank name
                    r'(?P<role>(?:(?:Joint\s+Lead|Sole\s+Global|Lead|Principal|Global)?\s*(?:Book(?:-)?running\s+)?(?:Manager|Bookrunner|Dealer|Underwriter|Coordinator|Arranger)s?))[:\s]+(?P<bank>[A-Z][A-Za-z0-9\s\.,&\(\)\-\']{2,40})(?=\s*(?:and|,|;|\n|$))',
                    
                    # Stabilisation/settlement roles followed by bank name
                    r'(?P<role>(?:Stabili[zs]ation|Stabili[zs]ing|Settlement|Calculation|Paying|Fiscal|Principal\s+Paying|Transfer|Registrar)\s+(?:Agent|Manager)s?)[:\s]+(?P<bank>[A-Z][A-Za-z0-9\s\.,&\(\)\-\']{2,40})(?=\s*(?:and|,|;|\n|$))',
                    
                    # Role followed by bank name in table-like format
                    r'(?P<role>(?:(?:Lead|Joint(?:\s+Lead)?|Sole|Co-Lead|Co-|Global)?\s*(?:Manager|Book(?:-)?Runner|Bookrunner|Dealer|Underwriter|Coordinator|Arranger)s?))[\s:]+[\.\…\s]*(?P<bank>[A-Z][A-Za-z0-9\s\.,&\(\)\-\']{2,40})(?=\s*(?:and|,|;|\n|$))',
                    
                    # Additional role-bank patterns
                    r'(?P<role>(?:Initial|Principal|Lead|Senior|Global)\s+(?:Purchaser|Dealer|Coordinator|Structuring\s+Agent)s?)[:\s]+(?P<bank>[A-Z][A-Za-z0-9\s\.,&\(\)\-\']{2,40})(?=\s*(?:and|,|;|\n|$))',
                    
                    # Common format in final terms
                    r'(?P<role>(?:(?:Sole|Global|Joint|Lead)\s+)?(?:Book\-?runner|Manager|Coordinator|Structurer|Dealer|Arranger))(?:\(s\))?\s*[:：]\s*(?P<bank>[A-Z][A-Za-z0-9\s\.,&\(\)\-\']{2,40})(?=\s*(?:and|,|;|\n|$))',
                    
                    # Role with address pattern
                    r'(?P<role>(?:(?:Lead|Joint(?:\s+Lead)?|Sole|Co-Lead|Co-|Global)?\s*(?:Manager|Book(?:-)?Runner|Bookrunner|Dealer|Underwriter|Coordinator|Arranger)s?))[:\s]+(?P<bank>[A-Z][A-Za-z0-9\s\.,&\(\)\-\']{2,40}(?:\s*,\s*[A-Za-z0-9\s\.,&\(\)\-\']{2,40})?)(?=\s*(?:and|,|;|\n|$|Address:|Tel:|Email:))'
                ],
                
                # Format: "Bank Name (as Role)"
                "bank_then_role": [
                    # Bank as role
                    r'(?P<bank>[A-Z][A-Za-z0-9\s\.,&\(\)\-\']{2,40})\s+(?:as|in\s+its\s+capacity\s+as)\s+(?:(?:a|the|an)\s+)?(?P<role>(?:(?:Lead|Joint(?:\s+Lead)?|Sole|Co-Lead|Co-|Global)?\s*(?:Manager|Book(?:-)?Runner|Bookrunner|Dealer|Underwriter|Coordinator|Arranger)s?))',
                    
                    # Bank acting as role
                    r'(?P<bank>[A-Z][A-Za-z0-9\s\.,&\(\)\-\']{2,40})\s+(?:acts|acting|will\s+act|to\s+act|shall\s+act)\s+as\s+(?:(?:a|the|an)\s+)?(?P<role>(?:(?:Lead|Joint(?:\s+Lead)?|Sole|Co-Lead|Co-|Global)?\s*(?:Manager|Book(?:-)?Runner|Bookrunner|Dealer|Underwriter|Coordinator|Arranger)s?))',
                    
                    # Bank as specialized role
                    r'(?P<bank>[A-Z][A-Za-z0-9\s\.,&\(\)\-\']{2,40})\s+(?:as|in\s+its\s+capacity\s+as|acting\s+as)\s+(?:(?:a|the|an)\s+)?(?P<role>(?:Stabili[zs]ation|Stabili[zs]ing|Settlement|Calculation|Paying|Fiscal|Principal\s+Paying|Transfer|Registrar)\s+(?:Agent|Manager)s?)',
                    
                    # Additional bank-role patterns
                    r'(?P<bank>[A-Z][A-Za-z0-9\s\.,&\(\)\-\']{2,40})\s+(?:has|have)\s+been\s+appointed\s+(?:as|to\s+act\s+as)\s+(?:(?:a|the|an)\s+)?(?P<role>(?:(?:Lead|Joint(?:\s+Lead)?|Sole|Co-Lead|Co-|Global)?\s*(?:Manager|Book(?:-)?Runner|Bookrunner|Dealer|Underwriter|Coordinator|Arranger)s?))',
                    
                    # Bank will be role
                    r'(?P<bank>[A-Z][A-Za-z0-9\s\.,&\(\)\-\']{2,40})\s+(?:will|shall)\s+be\s+(?:(?:a|the|an)\s+)?(?P<role>(?:(?:Lead|Joint(?:\s+Lead)?|Sole|Co-Lead|Co-|Global)?\s*(?:Manager|Book(?:-)?Runner|Bookrunner|Dealer|Underwriter|Coordinator|Arranger)s?))'
                ],
                
                # Format: List of banks following a role introduction
                "list_after_role_intro": [
                    # Role followed by bullet-point list of banks
                    r'(?P<role>The\s+(?:(?:Lead|Joint(?:\s+Lead)?|Sole|Co-Lead|Co-|Global)?\s*(?:Manager|Book(?:-)?Runner|Bookrunner|Dealer|Underwriter|Coordinator|Arranger)s?)(?:\s+(?:are|is|shall\s+be|will\s+be|have\s+been\s+appointed\s+as))?:?)(?P<banks>(?:\s*[•\-–—]\s*[A-Z][A-Za-z0-9\s\.,&\(\)\-\']{2,40}(?:;|,|and|\n|$))+)',
                    
                    # Role followed by numbered list of banks
                    r'(?P<role>The\s+(?:(?:Lead|Joint(?:\s+Lead)?|Sole|Co-Lead|Co-|Global)?\s*(?:Manager|Book(?:-)?Runner|Bookrunner|Dealer|Underwriter|Coordinator|Arranger)s?)(?:\s+(?:are|is|shall\s+be|will\s+be|have\s+been\s+appointed\s+as))?:?)(?P<banks>(?:\s*\(?\d+\)?\s*\.?\s*[A-Z][A-Za-z0-9\s\.,&\(\)\-\']{2,40}(?:;|,|and|\n|$))+)',
                    
                    # Role followed by general list/paragraph of banks
                    r'(?P<role>The\s+(?:(?:Lead|Joint(?:\s+Lead)?|Sole|Co-Lead|Co-|Global)?\s*(?:Manager|Book(?:-)?Runner|Bookrunner|Dealer|Underwriter|Coordinator|Arranger)s?)(?:\s+(?:are|is|shall\s+be|will\s+be|have\s+been\s+appointed\s+as))?:?)(?P<banks>.{5,500}?)(?=\n\n|\n[A-Z]|\n\d|\n\s*\Z)',
                    
                    # Additional list patterns
                    r'(?P<role>(?:The\s+)?(?:following|undermentioned|below\-?named)\s+(?:(?:entity|entities|institution|financial\s+institution|bank|investment\s+bank|dealer|manager|underwriter|arranger)s?)\s+(?:have|has|are|is|will|shall)\s+(?:been\s+appointed|act)\s+as\s+(?:(?:Lead|Joint(?:\s+Lead)?|Sole|Co-Lead|Co-|Global)?\s*(?:Manager|Book(?:-)?Runner|Bookrunner|Dealer|Underwriter|Coordinator|Arranger)s?):?)(?P<banks>(?:.|\n){5,500}?)(?=\n\n|\n[A-Z]|\n\d|\n\s*\Z)',
                    
                    # Simple introduction to list without "the"
                    r'(?P<role>(?:(?:Lead|Joint(?:\s+Lead)?|Sole|Co-Lead|Co-|Global)?\s*(?:Manager|Book(?:-)?Runner|Bookrunner|Dealer|Underwriter|Coordinator|Arranger)s?)(?:\s+(?:are|is|shall\s+be|will\s+be|have\s+been\s+appointed\s+as))?:)(?P<banks>(?:.|\n){5,300}?)(?=\n\n|\n[A-Z]|\n\d|\n\s*\Z)'
                ],
                
                # Format: Banks in table-like format with roles
                "table_format": [
                    # Table-like format with bank and role in same line
                    r'(?P<bank>[A-Z][A-Za-z0-9\s\.,&\(\)\-\']{2,40})[:\s]+(?:(?:as|acting\s+as)\s+)?(?P<role>(?:(?:Lead|Joint(?:\s+Lead)?|Sole|Co-Lead|Co-|Global)?\s*(?:Manager|Book(?:-)?Runner|Bookrunner|Dealer|Underwriter|Coordinator|Arranger)s?))(?:\s*;|,|\n|$)',
                    
                    # Bank name at start of line with role after (possible table row)
                    r'^[\s•\-]*(?P<bank>[A-Z][A-Za-z0-9\s\.,&\(\)\-\']{2,40})[\s-]+(?P<role>(?:(?:Lead|Joint(?:\s+Lead)?|Sole|Co-Lead|Co-|Global)?\s*(?:Manager|Book(?:-)?Runner|Bookrunner|Dealer|Underwriter|Coordinator|Arranger)s?))(?:\s*;|,|\n|$)',
                    
                    # Bank with parenthetical role
                    r'(?P<bank>[A-Z][A-Za-z0-9\s\.,&\(\)\-\']{2,40})\s*\((?P<role>(?:(?:Lead|Joint(?:\s+Lead)?|Sole|Co-Lead|Co-|Global)?\s*(?:Manager|Book(?:-)?Runner|Bookrunner|Dealer|Underwriter|Coordinator|Arranger)s?))\)',
                    
                    # Bank with address in column followed by role
                    r'(?P<bank>[A-Z][A-Za-z0-9\s\.,&\(\)\-\']{2,40}(?:\s*,\s*[A-Za-z0-9\s\.,&\(\)\-\']{2,40})?)\s{2,}(?P<role>(?:(?:Lead|Joint(?:\s+Lead)?|Sole|Co-Lead|Co-|Global)?\s*(?:Manager|Book(?:-)?Runner|Bookrunner|Dealer|Underwriter|Coordinator|Arranger)s?))'
                ]
            }
            
            # Process each section with specific extraction strategies
            for section_name, section_text in relevant_sections.items():
                self.logger.debug(f"Processing {section_name} section for bank extraction")
                
                # First, look for well-known major banks directly in the section text
                # This helps catch banks even when the structural patterns fail
                major_bank_patterns = [
                    # Major European banks (with common variants)
                    r'\b(?:Deutsche\s*Bank|DB\s+AG)\b',
                    r'\b(?:Credit\s*Suisse|CS\s+Securities)\b',
                    r'\b(?:BNP\s*Paribas|BNPP)\b',
                    r'\b(?:Socie[tée]\s*G[eé]n[eé]rale|SocGen|SG)\b',
                    r'\b(?:HSBC)\b',
                    r'\b(?:Barclays(?:\s+Capital)?)\b',
                    r'\b(?:ING(?:\s+Bank)?)\b',
                    r'\b(?:UniCredit|HVB)\b',
                    r'\b(?:Santander)\b',
                    r'\b(?:Cr[eé]dit\s*Agricole|CA\s*CIB)\b',
                    r'\b(?:Commerzbank)\b',
                    r'\b(?:UBS)\b',
                    r'\b(?:Natixis)\b',
                    r'\b(?:Intesa\s+Sanpaolo)\b',
                    r'\b(?:BBVA)\b',
                    
                    # Major US banks
                    r'\b(?:Morgan\s*Stanley|MS)\b',
                    r'\b(?:Goldman\s*Sachs|GS)\b',
                    r'\b(?:J\.?P\.?\s*Morgan|JPM)\b',
                    r'\b(?:Citi(?:group)?|Citibank)\b',
                    r'\b(?:Bank\s*of\s*America|BofA(?:\s+Securities)?|Merrill\s*Lynch)\b',
                    r'\b(?:Wells\s*Fargo)\b',
                    
                    # Major Asian banks
                    r'\b(?:Nomura)\b',
                    r'\b(?:Mizuho)\b',
                    r'\b(?:MUFG|Mitsubishi\s+UFJ)\b',
                    r'\b(?:SMBC|Sumitomo\s+Mitsui)\b',
                    r'\b(?:DBS)\b',
                    r'\b(?:Standard\s*Chartered)\b'
                ]
                
                # Extract direct mentions of major banks
                for pattern in major_bank_patterns:
                    matches = re.finditer(pattern, section_text, re.IGNORECASE)
                    for match in matches:
                        bank = match.group(0).strip()
                        cleaned_bank = self.clean_bank_name(bank)
                        
                        # Determine role from context if possible
                        context_before = section_text[max(0, match.start() - 50):match.start()].lower()
                        context_after = section_text[match.end():min(len(section_text), match.end() + 50)].lower()
                        
                        role = "Unknown"
                        # Check for role keywords
                        role_keywords = {
                            "lead manager": "Lead Manager",
                            "joint lead manager": "Joint Lead Manager", 
                            "manager": "Manager",
                            "bookrunner": "Bookrunner", 
                            "joint bookrunner": "Joint Bookrunner",
                            "underwriter": "Underwriter",
                            "dealer": "Dealer",
                            "global coordinator": "Global Coordinator"
                        }
                        
                        full_context = context_before + " " + context_after
                        for keyword, role_text in role_keywords.items():
                            if keyword in full_context:
                                role = role_text
                                break
                                
                        # If specific role not found, use section name as role indicator
                        if role == "Unknown":
                            if section_name == "managers" or section_name == "management":
                                role = "Manager"
                            elif section_name == "distribution":
                                role = "Dealer"
                            elif section_name == "stabilisation":
                                role = "Stabilisation Manager"
                        
                        if cleaned_bank and self.is_valid_bank_name(cleaned_bank) and cleaned_bank not in banks_found:
                            banks_found.add(cleaned_bank)
                            result["extracted_banks"].append({
                                "raw_name": bank,
                                "cleaned_name": cleaned_bank,
                                "role": role,
                                "confidence": 0.9,  # High confidence for direct major bank matches
                                "source": f"{section_name}_section_direct_match"
                            })
                
                # Apply each pattern type to the section
                for pattern_type, patterns in extraction_patterns.items():
                    for pattern in patterns:
                        # For list patterns, we need special handling
                        if pattern_type == "list_after_role_intro":
                            matches = re.search(pattern, section_text, re.MULTILINE | re.IGNORECASE)
                            if matches:
                                role = matches.group('role').strip()
                                banks_text = matches.group('banks').strip()
                                
                                # Identify individual banks in the list
                                # Look for bullet points, numbers, or simple newlines
                                bank_items = re.split(r'\n\s*[•\-–—]\s*|\n\s*\d+\.?\s*|\n\s*|\s*[,;]\s*|\s+and\s+', banks_text)
                                for bank_item in bank_items:
                                    bank = bank_item.strip()
                                    if bank and len(bank) > 3:
                                        cleaned_bank = self.clean_bank_name(bank)
                                        if cleaned_bank and self.is_valid_bank_name(cleaned_bank) and cleaned_bank not in banks_found:
                                            banks_found.add(cleaned_bank)
                                            result["extracted_banks"].append({
                                                "raw_name": bank,
                                                "cleaned_name": cleaned_bank,
                                                "role": role,
                                                "confidence": 0.9,  # High confidence for structured lists
                                                "source": f"{section_name}_section"
                                            })
                        else:
                            # Standard regex extraction
                            matches = re.finditer(pattern, section_text, re.MULTILINE)
                            for match in matches:
                                if pattern_type == "role_then_bank":
                                    role = match.group('role').strip()
                                    bank = match.group('bank').strip()
                                elif pattern_type == "bank_then_role" or pattern_type == "table_format":
                                    bank = match.group('bank').strip()
                                    role = match.group('role').strip()
                                
                                # Clean up extracted bank name
                                cleaned_bank = self.clean_bank_name(bank)
                                if cleaned_bank and self.is_valid_bank_name(cleaned_bank) and cleaned_bank not in banks_found:
                                    banks_found.add(cleaned_bank)
                                    result["extracted_banks"].append({
                                        "raw_name": bank,
                                        "cleaned_name": cleaned_bank,
                                        "role": role,
                                        "confidence": 0.95,  # Very high confidence for clear role-bank associations
                                        "source": f"{section_name}_section"
                                    })
            
            # Look for the Paying Agent specifically - often contains bank information
            if "contacts" in relevant_sections:
                contacts_section = relevant_sections["contacts"]
                paying_agent_match = re.search(r'(?:Initial\s+)?Paying\s+Agent(?:\(s\))?[:\s]+([^,\n]+)(?:,|\n|$)', contacts_section, re.IGNORECASE)
                if paying_agent_match:
                    bank = paying_agent_match.group(1).strip()
                    cleaned_bank = self.clean_bank_name(bank)
                    if cleaned_bank and self.is_valid_bank_name(cleaned_bank) and cleaned_bank not in banks_found:
                        banks_found.add(cleaned_bank)
                        result["extracted_banks"].append({
                            "raw_name": bank,
                            "cleaned_name": cleaned_bank,
                            "role": "Paying Agent",
                            "confidence": 0.9,
                            "source": "contacts_section"
                        })
                        
                # Look for Citibank specifically (common paying agent in many PDFs)
                citibank_match = re.search(r'(Citibank[^,\n]+)(?:,|\n|$)', contacts_section)
                if citibank_match:
                    bank = citibank_match.group(1).strip()
                    cleaned_bank = self.clean_bank_name(bank)
                    if cleaned_bank and self.is_valid_bank_name(cleaned_bank) and cleaned_bank not in banks_found:
                        banks_found.add(cleaned_bank)
                        result["extracted_banks"].append({
                            "raw_name": bank,
                            "cleaned_name": cleaned_bank,
                            "role": "Paying Agent",
                            "confidence": 0.85,
                            "source": "contacts_section"
                        })
            
            # ---- Step 3: Fallback approach - look for potential banks near role keywords ----
            if not result["extracted_banks"]:
                self.logger.info("No banks found in specific sections, trying fallback approach...")
                
                # Identify paragraphs that likely discuss banks/managers
                potential_paragraphs = []
                
                # Look for paragraphs containing banking role indicators
                role_indicators = [
                    r'(?i)(?:joint\s+lead|lead|sole|co-lead|global)?\s*(?:manager|book(?:-)?runner|dealer|underwriter|arranger)',
                    r'(?i)stabili[sz]ation\s+manager',
                    r'(?i)(?:has|have)\s+been\s+appointed',
                    r'(?i)in\s+its\s+capacity\s+as',
                    r'(?i)(?:will|shall)\s+act\s+as',
                    r'(?i)(?:the|a)\s+manager',
                    r'(?i)(?:the|a)\s+dealer',
                    r'(?i)(?:the|a)\s+book(?:-)?runner',
                    r'(?i)(?:the|a)\s+underwriter',
                    r'(?i)management\s+(?:of|and|team)'
                ]
                
                # Extract paragraphs (by splitting on double newlines)
                paragraphs = re.split(r'\n\s*\n', text)
                
                for paragraph in paragraphs:
                    if len(paragraph.strip()) > 30:  # Skip very short paragraphs
                        for indicator in role_indicators:
                            if re.search(indicator, paragraph):
                                potential_paragraphs.append(paragraph)
                                break
                
                # Extract banks from potential paragraphs
                if potential_paragraphs:
                    self.logger.info(f"Found {len(potential_paragraphs)} paragraphs with potential bank information")
                    
                    # Define patterns for bank extraction from paragraphs
                    bank_extraction_patterns = [
                        # Common banks
                        r'(?:\W|^)(?:BNP\s+Paribas|Deutsche\s+Bank|Credit\s+Suisse|Morgan\s+Stanley|Goldman\s+Sachs|JP\s*Morgan|HSBC|Barclays|UBS|Citi(?:group)?|Nomura|Mizuho|MUFG|Santander|UniCredit|ING|Crédit\s+Agricole|Natixis|BBVA|Commerzbank)(?:\s+(?:Bank|Securities|Capital|Markets|AG|PLC|S\.A\.|N\.V\.|Inc\.|Ltd\.)?)?',
                        
                        # Banks with role context - avoid look-behind
                        r'(?:\W|^)([A-Z][A-Za-z\s&\.]{2,40})\s+(?:as|is|are|has been|have been|acting|serves|will act|shall act)',
                        
                        # Capital words near Manager/Dealer keywords - avoid look-behind
                        r'(?:\W|^)([A-Z][A-Za-z\s&\.]{2,40})(?:\s+(?:\([^)]+\))?\s+)(?:Manager|Book(?:-)?Runner|Dealer|Underwriter|Arranger)'
                    ]
                    
                    for paragraph in potential_paragraphs:
                        for pattern in bank_extraction_patterns:
                            matches = re.finditer(pattern, paragraph)
                            for match in matches:
                                if isinstance(match.groups(), tuple) and match.groups():
                                    bank = match.group(1).strip()
                                else:
                                    bank = match.group(0).strip()
                                
                                cleaned_bank = self.clean_bank_name(bank)
                                if cleaned_bank and self.is_valid_bank_name(cleaned_bank) and cleaned_bank not in banks_found:
                                    # Determine the role by looking at nearby context
                                    context_around = paragraph[max(0, paragraph.find(bank) - 30):min(len(paragraph), paragraph.find(bank) + len(bank) + 50)]
                                    
                                    role = "Unknown"
                                    confidence = 0.7  # Default for fallback
                                    
                                    # Role detection logic
                                    role_patterns = {
                                        "Lead Manager": r'(?:as|is|are)\s+(?:the|a|an)\s+(?:lead|joint\s+lead)\s+manager',
                                        "Joint Lead Manager": r'(?:as|is|are)\s+(?:the|a|an)\s+joint\s+lead\s+manager',
                                        "Global Coordinator": r'(?:as|is|are)\s+(?:the|a|an)\s+global\s+coordinator',
                                        "Bookrunner": r'(?:as|is|are)\s+(?:the|a|an)\s+(?:sole|joint|principal)?\s*book(?:-)?runner',
                                        "Dealer": r'(?:as|is|are)\s+(?:the|a|an)\s+dealer',
                                        "Underwriter": r'(?:as|is|are)\s+(?:the|a|an)\s+underwriter',
                                        "Arranger": r'(?:as|is|are)\s+(?:the|a|an)\s+arranger',
                                        "Manager": r'(?:as|is|are)\s+(?:the|a|an)\s+manager',
                                        "Stabilisation Manager": r'(?:as|is|are)\s+(?:the|a|an)\s+stabili[sz](ation|ing)\s+manager'
                                    }
                                    
                                    for role_name, role_pattern in role_patterns.items():
                                        if re.search(role_pattern, context_around, re.IGNORECASE):
                                            role = role_name
                                            confidence = 0.8  # Higher confidence with specific role
                                            break
                                    
                                    # Add to results
                                    banks_found.add(cleaned_bank)
                                    result["extracted_banks"].append({
                                        "raw_name": bank,
                                        "cleaned_name": cleaned_bank,
                                        "role": role,
                                        "confidence": confidence,
                                        "source": "paragraph_context"
                                    })
                                    
                    # Store a sample of paragraphs as context
                    if potential_paragraphs:
                        result["bank_sections"]["potential_paragraphs"] = "\n\n".join(potential_paragraphs[:3])  # Store first 3 for reference
            
            # ---- Step 4: Last resort - search for known bank names in entire text if still no results ----
            if not result["extracted_banks"]:
                self.logger.info("No banks found in paragraphs, searching for known banks in full text...")
                
                # Search for common bank names in entire text
                common_banks = [
                    # Major European banks
                    r'(?P<bank>(?:BNP\s+Paribas|Deutsche\s+Bank|Credit\s+Suisse|Société\s+Générale|HSBC|Barclays|UBS|Santander|UniCredit|ING|Crédit\s+Agricole|Natixis|BBVA|Commerzbank|CaixaBank|Intesa\s+Sanpaolo|ABN\s+AMRO|Rabobank|DNB|KBC|Nordea|SEB|Danske\s+Bank))',
                    
                    # Major US banks
                    r'(?P<bank>(?:Morgan\s+Stanley|Goldman\s+Sachs|JP\s*Morgan|Citigroup|BofA\s+Securities|Wells\s+Fargo|RBC|Scotiabank|TD\s+Securities))',
                    
                    # Major Asian banks
                    r'(?P<bank>(?:Nomura|Mizuho|MUFG|SMBC|DBS|Standard\s+Chartered|ICBC|Bank\s+of\s+China|China\s+Construction\s+Bank))',
                    
                    # More general patterns for banks
                    r'(?P<bank>(?:[\w\s]+?)(?:Bank|Capital|Markets|Securities|Investment|Finance)(?:\s+(?:AG|SA|NV|plc|LLC|Ltd|Limited|Inc|Corporation|Corp|Group|GmbH|&\s*Co|KG|KGaA))?)'
                ]
                
                for pattern in common_banks:
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        bank = match.group('bank').strip()
                        cleaned_bank = self.clean_bank_name(bank)
                        if cleaned_bank and self.is_valid_bank_name(cleaned_bank) and cleaned_bank not in banks_found:
                            # Try to find role context nearby
                            context_before = text[max(0, match.start() - 50):match.start()].lower()
                            context_after = text[match.end():min(len(text), match.end() + 50)].lower()
                            
                            role = "Unknown"
                            confidence = 0.6  # Lower confidence for broader search
                            
                            # Check for role keywords in context
                            role_keywords = {
                                "lead manager": "Lead Manager",
                                "joint lead manager": "Joint Lead Manager", 
                                "manager": "Manager",
                                "bookrunner": "Bookrunner", 
                                "book runner": "Bookrunner",
                                "book-runner": "Bookrunner",
                                "joint bookrunner": "Joint Bookrunner",
                                "underwriter": "Underwriter",
                                "dealer": "Dealer",
                                "coordinator": "Coordinator", 
                                "arranger": "Arranger",
                                "global coordinator": "Global Coordinator",
                                "stabilisation manager": "Stabilisation Manager",
                                "stabilization manager": "Stabilisation Manager"
                            }
                            
                            full_context = context_before + " " + context_after
                            for keyword, role_text in role_keywords.items():
                                if keyword in full_context:
                                    role = role_text
                                    confidence = 0.65  # Slightly higher with role context
                                    break
                                    
                            banks_found.add(cleaned_bank)
                            result["extracted_banks"].append({
                                "raw_name": bank,
                                "cleaned_name": cleaned_bank,
                                "role": role,
                                "confidence": confidence,
                                "source": "full_text_search"
                            })
            
            # ---- Step 5: Deduplicate and standardize results ----
            # Group by cleaned name to avoid duplicates with different roles
            banks_by_name = {}
            for bank_info in result["extracted_banks"]:
                bank_name = bank_info["cleaned_name"]
                if bank_name in banks_by_name:
                    # If we already have this bank, keep the one with higher confidence
                    # or more specific role
                    existing_info = banks_by_name[bank_name]
                    if (bank_info["confidence"] > existing_info["confidence"] or
                            (bank_info["confidence"] == existing_info["confidence"] and 
                             existing_info["role"] == "Unknown")):
                        banks_by_name[bank_name] = bank_info
                else:
                    banks_by_name[bank_name] = bank_info
            
            # Replace the extracted banks with the deduplicated list
            result["extracted_banks"] = list(banks_by_name.values())
            
            # Sort by confidence (highest first)
            result["extracted_banks"] = sorted(
                result["extracted_banks"], 
                key=lambda x: x["confidence"], 
                reverse=True
            )
            
            return result

        except Exception as e:
            self.logger.error(f"Error extracting bank information: {str(e)}", exc_info=True)
            return {
                "extracted_banks": [],
                "bank_sections": {}
            }
    
    def extract_bank_info(self, text: str) -> Dict:
        """
        Legacy method for backward compatibility.
        Calls _extract_banks_and_roles and reformats the results.
        """
        detailed_results = self._extract_banks_and_roles(text)
        
        # Transform to the old format for compatibility
        legacy_result = {
            "banks": [],
            "roles": {},
            "distribution_banks": [],
            "other_banks": []
        }
        
        # Process banks and their roles
        for bank_info in detailed_results["extracted_banks"]:
            bank_name = bank_info["cleaned_name"]
            role = bank_info["role"].lower()
            source = bank_info["source"]
            
            # Add to overall banks list
            if bank_name not in legacy_result["banks"]:
                legacy_result["banks"].append(bank_name)
            
            # Add to specific section based on source
            if "distribution" in source:
                if bank_name not in legacy_result["distribution_banks"]:
                    legacy_result["distribution_banks"].append(bank_name)
            else:
                if bank_name not in legacy_result["other_banks"]:
                    legacy_result["other_banks"].append(bank_name)
            
            # Group by role
            role_key = re.sub(r'\s+', '_', role.lower())
            if role_key not in legacy_result["roles"]:
                legacy_result["roles"][role_key] = []
            
            if bank_name not in legacy_result["roles"][role_key]:
                legacy_result["roles"][role_key].append(bank_name)
        
        # Add the detailed results as a new field for new code that might use it
        legacy_result["detailed_bank_info"] = detailed_results["extracted_banks"]
        
        return legacy_result
    
    def process_pdfs(self) -> List[Dict]:
        """Process multiple PDFs in parallel, searching recursively."""
        pdf_files = []
        pdf_dir_path = Path(self.pdf_dir)
        if not pdf_dir_path.is_dir():
            self.logger.error(f"PDF directory not found: {self.pdf_dir}")
            return []

        self.logger.info(f"Recursively searching for PDF files in {pdf_dir_path}...")
        for path in pdf_dir_path.rglob('*.pdf'):
            if path.is_file():
                pdf_files.append(str(path.resolve())) # Use absolute path
        
        self.logger.info(f"Found {len(pdf_files)} PDF files to process.")
        if not pdf_files:
            return []
            
        results = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit tasks with absolute paths
            future_to_pdf = {
                executor.submit(self.process_single_pdf, pdf_path): pdf_path
                for pdf_path in pdf_files
            }
            
            for future in concurrent.futures.as_completed(future_to_pdf):
                pdf_path = future_to_pdf[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    # Log error with relative path for brevity if possible
                    try:
                         relative_path = Path(pdf_path).relative_to(pdf_dir_path)
                    except ValueError:
                         relative_path = pdf_path # Keep absolute if not relative
                    self.logger.error(f"Error processing {relative_path}: {str(e)}", exc_info=True)
                    
        self.logger.info(f"Finished processing {len(pdf_files)} files. Extracted data for {len(results)} files.")
        return results
        
    def process_single_pdf(self, pdf_path: str) -> Optional[Dict]:
        """
        Process a single PDF file to extract bank information and other metadata.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary containing:
                - filename: Name of the PDF file
                - metadata: General metadata (dates, ISIN, etc.)
                - sections: Extracted document sections
                - extracted_banks: List of banks and their roles
                - bank_sections: Text of sections where banks were found
                - validation_flags: List of any validation concerns
        """
        try:
            # Extract text
            text = self.extract_text(pdf_path)
            if not text:
                return {
                    'filename': os.path.basename(pdf_path),
                    'validation_flags': ['text_extraction_failed']
                }
                
            # Extract general metadata
            metadata = self._extract_metadata(text)
            
            # Extract document sections
            sections = self._extract_sections(text)
            
            # Extract bank information using the new detailed method
            bank_info = self._extract_banks_and_roles(text)
            
            # For backward compatibility, also get the legacy format
            legacy_bank_info = self.extract_bank_info(text)
            
            # Perform validation
            validation_flags = self._validate_extraction_results(
                bank_info, metadata, sections, pdf_path
            )
            
            # Construct the result dictionary with all extracted information
            result = {
                'filename': os.path.basename(pdf_path),
                'file_path': pdf_path,
                'metadata': metadata,
                'sections': sections,
                'extracted_banks': bank_info['extracted_banks'],
                'bank_sections': bank_info['bank_sections'],
                'bank_info': legacy_bank_info,  # Keep this for backward compatibility
                'validation_flags': validation_flags
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing {pdf_path}: {str(e)}")
            return {
                'filename': os.path.basename(pdf_path),
                'file_path': pdf_path,
                'validation_flags': [f'processing_error: {str(e)}']
            }
            
    def _validate_extraction_results(self, bank_info, metadata, sections, pdf_path):
        """
        Validate the extraction results to flag potential issues.
        
        Args:
            bank_info: Dictionary containing extracted bank information
            metadata: Dictionary containing extracted metadata
            sections: Dictionary containing extracted sections
            pdf_path: Path to the PDF file
            
        Returns:
            List of validation flags (empty if no issues found)
        """
        validation_flags = []
        
        # Check if any banks were found
        if not bank_info['extracted_banks']:
            validation_flags.append('no_banks_found')
            
        # Check for low confidence banks
        low_confidence_banks = [
            bank for bank in bank_info['extracted_banks'] 
            if bank.get('confidence', 0) < 0.7
        ]
        if low_confidence_banks:
            validation_flags.append('low_confidence_banks')
            
        # Check if any bank sections were found
        if not bank_info['bank_sections']:
            validation_flags.append('no_bank_sections_found')
            
        # Check metadata
        if not metadata.get('date'):
            validation_flags.append('no_date_found')
        
        # Check if this is empty or suspiciously small extraction
        if len(bank_info['extracted_banks']) < 1 and len(sections) < 2:
            validation_flags.append('minimal_extraction')
            
        # If this is a final terms doc, we expect more structure
        if 'final_terms' in pdf_path.lower() and not bank_info['bank_sections']:
            validation_flags.append('final_terms_missing_expected_sections')
            
        return validation_flags
    
    def _extract_metadata(self, text: str) -> Dict:
        """
        Extracts various metadata fields from the document text.
        """
        metadata = {}
        
        # Extract Size and Currency
        size_currency_info = self._extract_issue_size_currency(text)
        metadata.update(size_currency_info)

        # Extract Dates
        date_info = self._extract_dates(text)
        metadata.update(date_info)

        # Extract Coupon
        coupon_info = self._extract_coupon(text)
        metadata.update(coupon_info)
        
        # Extract ISIN (Example of existing or other extraction logic)
        # isin_pattern = r'\\b([A-Z]{2}[A-Z0-9]{9}\\d)\\b'
        # isins = re.findall(isin_pattern, text)
        # metadata['isins'] = list(set(isins)) # Store unique ISINs
        
        # self.logger.debug(f"Extracted metadata: {metadata}")
        return metadata

    def _extract_issue_size_currency(self, text: str) -> Dict[str, Any]:
        """Extracts Issue Size and Currency."""
        size_info = {'issue_size': None, 'currency': None}
        
        # Enhanced patterns for issue size and currency
        patterns = [
            # Standard patterns
            r'(?:aggregate\s+nominal\s+amount|principal\s+amount|issue\s+size|total\s+amount)\s*[:\-]?\s*([A-Z]{3}|[€$£¥])?\s*([\d,]+(?:\.\d+)?)',
            # Amount followed by currency
            r'([\d,]+(?:\.\d+)?)\s*([A-Z]{3}|[€$£¥])',
            # Currency followed by amount
            r'([A-Z]{3}|[€$£¥])\s*([\d,]+(?:\.\d+)?)',
            # Amount with currency symbol
            r'([€$£¥])\s*([\d,]+(?:\.\d+)?)',
            # Amount with currency code
            r'([\d,]+(?:\.\d+)?)\s*(?:in\s+)?([A-Z]{3})'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                # Determine which group is currency and which is amount
                if len(match.groups()) == 2:
                    # If first group is currency code/symbol
                    if match.group(1) in ['EUR', 'USD', 'GBP', 'JPY', '€', '$', '£', '¥']:
                        currency = match.group(1)
                        amount_str = match.group(2)
                    # If second group is currency code/symbol
                    elif match.group(2) in ['EUR', 'USD', 'GBP', 'JPY', '€', '$', '£', '¥']:
                        currency = match.group(2)
                        amount_str = match.group(1)
                    else:
                        # Try to determine currency from context
                        currency = None
                        amount_str = match.group(1) if match.group(1).replace(',', '').replace('.', '').isdigit() else match.group(2)
                        
                    # Map currency symbols to codes
                    if currency:
                        if currency == '€':
                            currency = 'EUR'
                        elif currency == '$':
                            currency = 'USD'
                        elif currency == '£':
                            currency = 'GBP'
                        elif currency == '¥':
                            currency = 'JPY'
                            
                        size_info['currency'] = currency
                        
                    # Clean and convert amount
                    try:
                        amount = float(amount_str.replace(',', ''))
                        size_info['issue_size'] = amount
                        self.logger.debug(f"Found Issue Size/Currency: {size_info}")
                        return size_info
                    except ValueError:
                        self.logger.warning(f"Could not parse amount: {amount_str}")
                        continue
                        
        self.logger.debug("Could not find Issue Size/Currency using any pattern.")
        return size_info

    def _extract_dates(self, text: str) -> Dict[str, Optional[str]]:
        """Extracts Issue Date and Maturity Date."""
        date_info = {'issue_date': None, 'maturity_date': None}
        
        # Enhanced date patterns
        date_patterns = [
            # Standard date formats
            r'(?:issue\s+date|date\s+of\s+issue|issuance\s+date)\s*[:\-]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            r'(?:maturity\s+date|final\s+maturity|redemption\s+date)\s*[:\-]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            # Written month formats
            r'(?:issue\s+date|date\s+of\s+issue|issuance\s+date)\s*[:\-]?\s*(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})',
            r'(?:maturity\s+date|final\s+maturity|redemption\s+date)\s*[:\-]?\s*(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})',
            # ISO format
            r'(?:issue\s+date|date\s+of\s+issue|issuance\s+date)\s*[:\-]?\s*(\d{4}[-/]\d{2}[-/]\d{2})',
            r'(?:maturity\s+date|final\s+maturity|redemption\s+date)\s*[:\-]?\s*(\d{4}[-/]\d{2}[-/]\d{2})'
        ]
        
        # Try to find dates in the text
        for pattern in date_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                date_str = match.group(1)
                try:
                    # Try to parse the date
                    if '/' in date_str or '-' in date_str:
                        # Handle numeric dates
                        parts = re.split(r'[-/]', date_str)
                        if len(parts) == 3:
                            if len(parts[2]) == 2:  # Two-digit year
                                parts[2] = '20' + parts[2]
                            date = datetime.strptime(f"{parts[0]}/{parts[1]}/{parts[2]}", "%d/%m/%Y")
                    else:
                        # Handle written month dates
                        date = datetime.strptime(date_str, "%d %B %Y")
                    
                    # Determine if this is an issue date or maturity date
                    if 'issue' in match.group(0).lower() or 'issuance' in match.group(0).lower():
                        date_info['issue_date'] = date.strftime("%Y-%m-%d")
                    elif 'maturity' in match.group(0).lower() or 'redemption' in match.group(0).lower():
                        date_info['maturity_date'] = date.strftime("%Y-%m-%d")
                        
                    self.logger.debug(f"Found date: {date.strftime('%Y-%m-%d')}")
                except ValueError as e:
                    self.logger.warning(f"Could not parse date: {date_str} - {str(e)}")
                    continue
                    
        # If we found both dates, return them
        if date_info['issue_date'] and date_info['maturity_date']:
            return date_info
            
        # If we only found one date, try to find the other one
        if date_info['issue_date'] and not date_info['maturity_date']:
            # Look for maturity date relative to issue date
            issue_date = datetime.strptime(date_info['issue_date'], "%Y-%m-%d")
            # Common maturity periods: 1, 2, 3, 5, 7, 10, 15, 20, 30 years
            for years in [1, 2, 3, 5, 7, 10, 15, 20, 30]:
                maturity_date = issue_date + timedelta(days=years*365)
                maturity_str = maturity_date.strftime("%Y-%m-%d")
                if maturity_str in text:
                    date_info['maturity_date'] = maturity_str
                    break
                    
        self.logger.debug(f"Date extraction results: {date_info}")
        return date_info

    def _extract_coupon(self, text: str) -> Dict[str, Any]:
        """Extracts Coupon Rate information."""
        coupon_info = {'coupon_rate': None, 'coupon_type': None}
        
        # Patterns for Coupon Rate - look for percentages following keywords
        # Handles "X.XX%", "X%", might need adjustments for "per annum" etc.
        coupon_pattern = re.compile(
            r'(?:coupon|interest\s+rate|fixed\s+rate)\s*[:\-]?\s*([\d\.]+)\s*%', 
            re.IGNORECASE
        )
        
        match = coupon_pattern.search(text)
        if match:
            rate_str = match.group(1)
            try:
                rate = float(rate_str)
                coupon_info['coupon_rate'] = rate
                # Basic type detection - could be expanded
                if 'fixed rate' in match.group(0).lower():
                    coupon_info['coupon_type'] = 'Fixed'
                elif 'floating rate' in text.lower(): # Look nearby for floating rate clues
                    coupon_info['coupon_type'] = 'Floating'
                else:
                    coupon_info['coupon_type'] = 'Unknown' # Default if specific type isn't obvious
                self.logger.debug(f"Found Coupon: {coupon_info}")
                return coupon_info
            except ValueError:
                 self.logger.warning(f"Could not parse coupon rate: {rate_str}")

        # Add handling for "Floating Rate" / "Zero Coupon" if no % value found?
        if 'floating rate' in text.lower():
             coupon_info['coupon_type'] = 'Floating'
             self.logger.debug("Found indication of Floating Rate coupon")
        elif 'zero coupon' in text.lower():
             coupon_info['coupon_type'] = 'Zero Coupon'
             coupon_info['coupon_rate'] = 0.0
             self.logger.debug("Found indication of Zero Coupon")
             
        return coupon_info

    def _extract_sections(self, text: str) -> Dict[str, str]:
        """Extract document sections"""
        sections = {}
        
        # Common section headers
        section_headers = {
            'risk_factors': r'Risk\s+Factors',
            'business_overview': r'Business\s+Overview',
            'financial_information': r'Financial\s+Information',
            'management': r'Management',
            'shareholders': r'Shareholders',
            'governance': r'Corporate\s+Governance',
            'climate_related': r'Climate\s+Related\s+Disclosures?'
        }
        
        for section_name, pattern in section_headers.items():
            section_text = self.find_section(text, pattern)
            if section_text:
                sections[section_name] = section_text
                
        return sections

def main():
    extractor = PDFExtractor()
    results = extractor.process_pdfs()
    
    # Save results to JSON
    import json
    with open("bank_info.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\nResults saved to bank_info.json")

if __name__ == "__main__":
    main() 