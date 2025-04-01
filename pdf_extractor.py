import PyPDF2
import pdfplumber
import os
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import logging

class PDFExtractor:
    def __init__(self, pdf_dir: str = "downloads"):
        self.pdf_dir = pdf_dir
        self.setup_logging()
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def extract_text(self, pdf_path: str) -> str:
        """Extract text from a PDF file"""
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
        return text
    
    def extract_tables(self, pdf_path: str) -> List[List[List[str]]]:
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
            print(f"Error extracting tables from {pdf_path}: {str(e)}")
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
    
    def extract_bank_info(self, text: str) -> Dict:
        """Extract bank information from final terms"""
        data = {
            "banks": [],
            "roles": {},
            "contact_info": {}
        }
        
        # Common bank role patterns
        role_patterns = {
            "global_coordinator": r"Global Coordinator[s]?:\s*([^\n]+)",
            "bookrunner": r"Bookrunner[s]?:\s*([^\n]+)",
            "lead_manager": r"Lead Manager[s]?:\s*([^\n]+)",
            "co_lead_manager": r"Co-Lead Manager[s]?:\s*([^\n]+)",
            "manager": r"Manager[s]?:\s*([^\n]+)",
            "co_manager": r"Co-Manager[s]?:\s*([^\n]+)",
            "underwriter": r"Underwriter[s]?:\s*([^\n]+)",
            "agent": r"Agent[s]?:\s*([^\n]+)",
            "trustee": r"Trustee[s]?:\s*([^\n]+)",
            "paying_agent": r"Paying Agent[s]?:\s*([^\n]+)",
            "calculation_agent": r"Calculation Agent[s]?:\s*([^\n]+)",
            "registrar": r"Registrar[s]?:\s*([^\n]+)"
        }
        
        # Extract banks for each role
        for role, pattern in role_patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                bank_text = match.group(1).strip()
                # Split multiple banks if separated by commas or semicolons
                banks = [b.strip() for b in re.split(r'[,;]', bank_text)]
                for bank in banks:
                    if bank and bank not in data["banks"]:
                        data["banks"].append(bank)
                        if bank not in data["roles"]:
                            data["roles"][bank] = []
                        data["roles"][bank].append(role)
        
        # Extract contact information for banks
        contact_pattern = r"([^,\n]+(?:\s+[^,\n]+)*?)\s*\(([^)]+)\)"
        contact_matches = re.finditer(contact_pattern, text)
        for match in contact_matches:
            bank_name = match.group(1).strip()
            contact_details = match.group(2).strip()
            if bank_name in data["banks"]:
                data["contact_info"][bank_name] = contact_details
        
        return data
    
    def extract_underwriting_data(self, text: str, tables: List[List[List[str]]] = None) -> Dict:
        """Extract underwriting data from text and tables"""
        data = {
            "underwriters": [],
            "bookrunners": [],
            "issue_size": None,
            "issue_size_currency": None,
            "issue_date": None,
            "maturity_date": None,
            "coupon_rate": None,
            "currency": None,
            "rating": None,
            "listing": None,
            "stabilisation_manager": None,
            "tranche": None
        }
        
        # First extract bank information
        bank_data = self.extract_bank_info(text)
        data.update(bank_data)
        
        # Find and process underwriter section
        underwriter_section = self.find_underwriter_section(text)
        if underwriter_section:
            # Extract Global Coordinators and Active Bookrunners
            gc_pattern = r'Global Coordinators\s*and\s*Active Bookrunners\s*([\s\S]*?)(?=Joint Active Bookrunners|$)'
            gc_match = re.search(gc_pattern, underwriter_section)
            if gc_match:
                gc_text = gc_match.group(1)
                gc_lines = [line.strip() for line in gc_text.split('\n') if line.strip()]
                # Skip header line if present
                if gc_lines and ('Global Coordinators' in gc_lines[0] or 'Active Bookrunners' in gc_lines[0]):
                    gc_lines = gc_lines[1:]
                data["underwriters"].extend(gc_lines)
                data["bookrunners"].extend(gc_lines)

            # Extract Joint Active Bookrunners
            jab_pattern = r'Joint Active Bookrunners\s*([\s\S]*?)(?=\(iv\)|Stabilisation Manager|$)'
            jab_match = re.search(jab_pattern, underwriter_section)
            if jab_match:
                jab_text = jab_match.group(1)
                jab_lines = [line.strip() for line in jab_text.split('\n') if line.strip()]
                # Skip header line if present
                if jab_lines and 'Joint Active Bookrunners' in jab_lines[0]:
                    jab_lines = jab_lines[1:]
                data["underwriters"].extend(jab_lines)
                data["bookrunners"].extend(jab_lines)

            # Extract Stabilisation Manager
            stab_pattern = r'Stabilisation Manager[:\s]*([^\n]+)'
            stab_match = re.search(stab_pattern, underwriter_section)
            if stab_match:
                data["stabilisation_manager"] = stab_match.group(1).strip()
        
        # Extract financial details
        # Currency
        currency_match = re.search(r'Specified Currency or Currencies:\s*([^\n]+)', text)
        if currency_match:
            data["currency"] = currency_match.group(1).strip()
            data["issue_size_currency"] = data["currency"]

        # Issue size
        issue_size_match = re.search(r'Aggregate Nominal Amount:[\s\S]*?Series:\s*([^\n]+)', text)
        if issue_size_match:
            size_str = issue_size_match.group(1).strip()
            # Try to extract number and currency
            size_parts = re.search(r'([\d,]+\.?\d*)\s*([A-Z]{3})', size_str)
            if size_parts:
                data["issue_size"] = float(size_parts.group(1).replace(",", ""))
                data["issue_size_currency"] = size_parts.group(2)
                data["currency"] = size_parts.group(2)

        # Issue date
        issue_date_match = re.search(r'Issue Date:\s*([^\n]+)', text)
        if issue_date_match:
            try:
                date_str = issue_date_match.group(1).strip()
                data["issue_date"] = datetime.strptime(date_str, "%d %B %Y").isoformat()
            except ValueError:
                pass

        # Maturity date
        maturity_match = re.search(r'Maturity Date:\s*([^\n]+)', text)
        if maturity_match:
            try:
                date_str = maturity_match.group(1).strip()
                data["maturity_date"] = datetime.strptime(date_str, "%d %B %Y").isoformat()
            except ValueError:
                pass

        # Coupon/Interest rate
        interest_match = re.search(r'Interest Basis:\s*([^\n]+)', text)
        if interest_match:
            interest_str = interest_match.group(1).strip()
            # Try to extract percentage
            rate_match = re.search(r'([\d.]+)%', interest_str)
            if rate_match:
                data["coupon_rate"] = float(rate_match.group(1))

        # Tranche number
        tranche_match = re.search(r'Tranche Number:\s*([^\n]+)', text)
        if tranche_match:
            data["tranche"] = tranche_match.group(1).strip()

        # Listing
        listing_pattern = r'Listing and Admission to trading:\s*([^\n]+?)(?=\n|$)'
        listing_match = re.search(listing_pattern, text)
        if listing_match:
            listing_text = listing_match.group(1).strip()
            if 'Application has been made' in listing_text:
                listing_text = 'Euronext Paris'
            data["listing"] = listing_text

        # Rating
        rating_pattern = r'Ratings:[\s\S]*?S&P:\s*([^\n]+)[\s\S]*?Moody\'s:\s*([^\n]+)'
        rating_match = re.search(rating_pattern, text)
        if rating_match:
            sp_rating = rating_match.group(1).strip()
            moodys_rating = rating_match.group(2).strip()
            data["rating"] = f"S&P: {sp_rating}, Moody's: {moodys_rating}"
            
        return data
    
    def process_pdfs(self) -> List[Dict]:
        """Process all PDFs in the download directory"""
        results = []
        for filename in os.listdir(self.pdf_dir):
            if filename.endswith('.pdf'):
                pdf_path = os.path.join(self.pdf_dir, filename)
                try:
                    # Extract text and tables
                    text = self.extract_text(pdf_path)
                    tables = self.extract_tables(pdf_path)
                    
                    # Extract data
                    data = self.extract_underwriting_data(text, tables)
                    data["filename"] = filename
                    data["processed_at"] = datetime.utcnow().isoformat()
                    
                    # Add table data if available
                    if tables:
                        data["tables"] = tables
                    
                    results.append(data)
                except Exception as e:
                    print(f"Error processing {filename}: {str(e)}")
        return results

def main():
    extractor = PDFExtractor()
    results = extractor.process_pdfs()
    
    # Print results
    for result in results:
        print(f"\nFile: {result['filename']}")
        print(f"Underwriters: {', '.join(result['underwriters'])}")
        print(f"Bookrunners: {', '.join(result['bookrunners'])}")
        print(f"Issue Size: {result['issue_size']} {result['issue_size_currency']}")
        print(f"Issue Date: {result['issue_date']}")
        print(f"Maturity Date: {result['maturity_date']}")
        print(f"Coupon Rate: {result['coupon_rate']}%")
        print(f"Rating: {result['rating']}")
        print(f"Listing: {result['listing']}")
        print(f"Stabilisation Manager: {result['stabilisation_manager']}")
        print(f"Tranche: {result['tranche']}")

if __name__ == "__main__":
    main() 