import os
import logging
import requests
from pathlib import Path
from typing import Dict, List, Optional
import PyPDF2
import pdfplumber
from tqdm import tqdm
import time
from urllib.parse import urlparse
import re
import json

class PDFProcessor:
    def __init__(self, download_dir: Path):
        self.download_dir = download_dir
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        })

    def download_pdf(self, url: str, filename: Optional[str] = None) -> Optional[Path]:
        """Download PDF from URL with retry mechanism"""
        if not filename:
            filename = os.path.basename(urlparse(url).path)
            if not filename.endswith('.pdf'):
                filename += '.pdf'

        filepath = self.download_dir / filename
        max_retries = 3
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                response = self.session.get(url, stream=True)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                block_size = 8192
                
                with open(filepath, 'wb') as f, tqdm(
                    desc=filename,
                    total=total_size,
                    unit='iB',
                    unit_scale=True,
                    unit_divisor=1024,
                ) as pbar:
                    for data in response.iter_content(block_size):
                        size = f.write(data)
                        pbar.update(size)
                
                return filepath
                
            except Exception as e:
                logging.error(f"Attempt {attempt + 1} failed to download {url}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    logging.error(f"Failed to download {url} after {max_retries} attempts")
                    return None

    def extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extract text from PDF using PyPDF2"""
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except Exception as e:
            logging.error(f"Error extracting text from {pdf_path}: {str(e)}")
            return ""

    def extract_tables_from_pdf(self, pdf_path: Path) -> List[List[List[str]]]:
        """Extract tables from PDF using pdfplumber"""
        try:
            tables = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)
            return tables
        except Exception as e:
            logging.error(f"Error extracting tables from {pdf_path}: {str(e)}")
            return []

    def find_underwriter_section(self, text: str) -> Optional[str]:
        """Find the underwriter section in the text"""
        # Common underwriter section headers
        underwriter_headers = [
            "underwriter",
            "underwriters",
            "lead underwriter",
            "lead underwriters",
            "syndicate",
            "bookrunner",
            "bookrunners",
            "joint bookrunner",
            "joint bookrunners",
            "managing underwriter",
            "managing underwriters"
        ]
        
        # Split text into sections
        sections = text.split('\n\n')
        
        for section in sections:
            section_lower = section.lower()
            if any(header in section_lower for header in underwriter_headers):
                return section
        
        return None

    def extract_underwriter_info(self, text):
        """
        Extract underwriter information and financial details from the text.
        Returns:
        - list of underwriters (including all banks involved)
        - list of bookrunners
        - dictionary of financial details
        """
        underwriters = []
        bookrunners = []
        financial_details = {
            'coupon': None,
            'tranche': None,
            'issue_size': None,
            'maturity_date': None,
            'issue_date': None,
            'currency': None,
            'rating': None,
            'listing': None,
            'stabilisation_manager': None
        }

        # Extract distribution section
        distribution_pattern = r'6\s*DISTRIBUTION[\s\S]*?(?=7\s*USE AND ESTIMATED NET AMOUNT)'
        distribution_match = re.search(distribution_pattern, text)
        if distribution_match:
            distribution_text = distribution_match.group(0)
            
            # Extract Global Coordinators and Active Bookrunners
            gc_pattern = r'Global Coordinators\s*and\s*Active Bookrunners\s*([\s\S]*?)(?=Joint Active Bookrunners|$)'
            gc_match = re.search(gc_pattern, distribution_text)
            if gc_match:
                gc_text = gc_match.group(1)
                gc_lines = [line.strip() for line in gc_text.split('\n') if line.strip()]
                # Skip header line if present
                if gc_lines and ('Global Coordinators' in gc_lines[0] or 'Active Bookrunners' in gc_lines[0]):
                    gc_lines = gc_lines[1:]
                underwriters.extend(gc_lines)
                bookrunners.extend(gc_lines)

            # Extract Joint Active Bookrunners
            jab_pattern = r'Joint Active Bookrunners\s*([\s\S]*?)(?=\(iv\)|Stabilisation Manager|$)'
            jab_match = re.search(jab_pattern, distribution_text)
            if jab_match:
                jab_text = jab_match.group(1)
                jab_lines = [line.strip() for line in jab_text.split('\n') if line.strip()]
                # Skip header line if present
                if jab_lines and 'Joint Active Bookrunners' in jab_lines[0]:
                    jab_lines = jab_lines[1:]
                underwriters.extend(jab_lines)
                bookrunners.extend(jab_lines)

            # Extract Stabilisation Manager
            stab_pattern = r'Stabilisation Manager[:\s]*([^\n]+)'
            stab_match = re.search(stab_pattern, distribution_text)
            if stab_match:
                financial_details['stabilisation_manager'] = stab_match.group(1).strip()

        # Extract financial details
        # Currency
        currency_match = re.search(r'Specified Currency or Currencies:\s*([^\n]+)', text)
        if currency_match:
            financial_details['currency'] = currency_match.group(1).strip()

        # Issue size
        issue_size_match = re.search(r'Aggregate Nominal Amount:[\s\S]*?Series:\s*([^\n]+)', text)
        if issue_size_match:
            financial_details['issue_size'] = issue_size_match.group(1).strip()

        # Issue date
        issue_date_match = re.search(r'Issue Date:\s*([^\n]+)', text)
        if issue_date_match:
            financial_details['issue_date'] = issue_date_match.group(1).strip()

        # Maturity date
        maturity_match = re.search(r'Maturity Date:\s*([^\n]+)', text)
        if maturity_match:
            financial_details['maturity_date'] = maturity_match.group(1).strip()

        # Coupon/Interest rate
        interest_match = re.search(r'Interest Basis:\s*([^\n]+)', text)
        if interest_match:
            financial_details['coupon'] = interest_match.group(1).strip()

        # Tranche number
        tranche_match = re.search(r'Tranche Number:\s*([^\n]+)', text)
        if tranche_match:
            financial_details['tranche'] = tranche_match.group(1).strip()

        # Listing
        listing_pattern = r'Listing and Admission to trading:\s*([^\n]+?)(?=\n|$)'
        listing_match = re.search(listing_pattern, text)
        if listing_match:
            listing_text = listing_match.group(1).strip()
            if 'Application has been made' in listing_text:
                listing_text = 'Euronext Paris'
            financial_details['listing'] = listing_text

        # Rating
        rating_pattern = r'Ratings:[\s\S]*?S&P:\s*([^\n]+)[\s\S]*?Moody\'s:\s*([^\n]+)'
        rating_match = re.search(rating_pattern, text)
        if rating_match:
            sp_rating = rating_match.group(1).strip()
            moodys_rating = rating_match.group(2).strip()
            financial_details['rating'] = f"S&P: {sp_rating}, Moody's: {moodys_rating}"

        # Clean up lists
        underwriters = [u for u in underwriters if u and not u.isspace() and not u.isdigit()]
        bookrunners = [b for b in bookrunners if b and not b.isspace() and not b.isdigit()]
        
        # Fix any split bank names
        fixed_underwriters = []
        i = 0
        while i < len(underwriters):
            current = underwriters[i]
            if i + 1 < len(underwriters) and any(suffix in underwriters[i + 1] for suffix in ['SE', 'SA', 'AG', 'PLC']):
                fixed_underwriters.append(f"{current} {underwriters[i + 1]}")
                i += 2
            else:
                fixed_underwriters.append(current)
                i += 1

        # Fix any joined bank names
        final_underwriters = []
        for underwriter in fixed_underwriters:
            if 'SMBC Bank EU AG' in underwriter and 'Natixis' in underwriter:
                final_underwriters.extend(['Natixis', 'SMBC Bank EU AG'])
            else:
                final_underwriters.append(underwriter)

        return final_underwriters, bookrunners, financial_details

    def extract_text_and_tables(self, pdf_path: Path) -> tuple[str, List[List[List[str]]]]:
        """Extract text and tables from a PDF file."""
        try:
            # Extract text from PDF
            raw_text = self.extract_text_from_pdf(pdf_path)
            
            # Extract tables from PDF
            tables = self.extract_tables_from_pdf(pdf_path)
            
            if raw_text:
                # Extract underwriter information
                underwriters, bookrunners, financial_details = self.extract_underwriter_info(raw_text)
                
                # Create results dictionary
                results = {
                    "pdf_path": str(pdf_path),
                    "underwriter_section": raw_text[:500],  # First 500 characters for preview
                    "underwriters": underwriters,
                    "bookrunners": bookrunners,
                    "tables": tables,
                    "raw_text": raw_text,
                    "financial_details": financial_details
                }
                
                # Save results to JSON file
                output_file = pdf_path.with_suffix('.json')
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                
                return raw_text, tables
            
            return "", []
        
        except Exception as e:
            print(f"Error in extract_text_and_tables: {str(e)}")
            return "", []

    def process_pdf_url(self, url: str) -> Optional[Dict]:
        """Process a PDF URL and extract relevant information"""
        try:
            # Download PDF
            pdf_path = self.download_pdf(url)
            if not pdf_path:
                return None

            # Extract text and tables
            text = self.extract_text_from_pdf(pdf_path)
            tables = self.extract_tables_from_pdf(pdf_path)

            # Find underwriter section
            underwriter_section = self.find_underwriter_section(text)

            # Extract underwriter info and financial details
            underwriters, bookrunners, financial_details = self.extract_underwriter_info(text)

            # Create results dictionary
            results = {
                "pdf_path": str(pdf_path),
                "underwriter_section": underwriter_section,
                "tables": tables,
                "raw_text": text,
                "financial_details": financial_details,
                "underwriters": underwriters,
                "bookrunners": bookrunners
            }

            return results

        except Exception as e:
            logging.error(f"Error processing {url}: {str(e)}")
            return None 