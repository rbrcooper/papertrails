import fitz  # PyMuPDF
import os
import re
from typing import Dict, List, Optional
from datetime import datetime
import logging
import pymupdf4llm

class PDFExtractor:
    def __init__(self, pdf_dir: str = "downloads"):
        self.pdf_dir = pdf_dir
        self.setup_logging()
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def find_section(self, text: str, start_marker: str, end_marker: str = None) -> Optional[str]:
        """Find a section between start and end markers"""
        try:
            start_idx = text.lower().find(start_marker.lower())
            if start_idx == -1:
                return None
                
            if end_marker:
                end_idx = text.lower().find(end_marker.lower(), start_idx)
                if end_idx == -1:
                    end_idx = len(text)
            else:
                end_idx = len(text)
                
            return text[start_idx:end_idx].strip()
        except Exception as e:
            self.logger.error(f"Error finding section: {str(e)}")
            return None
    
    def extract_text(self, pdf_path: str) -> str:
        """Extract text from a PDF file using pymupdf4llm"""
        try:
            self.logger.info(f"Processing {pdf_path}")
            
            # Use pymupdf4llm to convert PDF to markdown
            text = pymupdf4llm.to_markdown(pdf_path)
            
            if not text:
                self.logger.warning(f"No text extracted from {pdf_path}")
                return ""
            
            self.logger.info(f"Successfully extracted {len(text)} characters")
            self.logger.debug(f"First 1000 characters of extracted text:\n{text[:1000]}")
            return text
            
        except Exception as e:
            self.logger.error(f"Error processing PDF {pdf_path}: {str(e)}", exc_info=True)
            return ""
    
    def is_final_terms(self, filename: str) -> bool:
        """Check if a file is a final terms document"""
        return 'Final_terms' in filename or 'Final terms' in filename
    
    def clean_bank_name(self, bank: str) -> str:
        """Clean up bank name"""
        # Remove common prefixes/suffixes
        bank = re.sub(r'^(?:The\s+|M[rs]\.\s+|Messrs\.\s+)', '', bank, flags=re.IGNORECASE)
        # Remove any HTML or markdown
        bank = re.sub(r'<[^>]+>|\*\*|\[|\]', '', bank)
        # Remove parenthetical text
        bank = re.sub(r'\([^)]*\)', '', bank)
        # Clean up whitespace
        bank = re.sub(r'\s+', ' ', bank).strip()
        # Remove common suffixes
        bank = re.sub(r'(?i)\s*(?:as\s+(?:global\s+coordinator|bookrunner|stabilisation\s+manager|calculation\s+agent|paying\s+agent|trustee|registrar))\s*$', '', bank)
        return bank
    
    def is_valid_bank_name(self, bank: str) -> bool:
        """Check if a string is a valid bank name"""
        # Common invalid banks, words and phrases
        invalid_banks = {
            'not applicable', 'n/a', 'none', 'any', 'the', 'and', 'or', 'if', 
            'quotation', 'applicable', 'see', 'above', 'below', 'following',
            'means', 'shall', 'will', 'may', 'can', 'must', 'should', 'would',
            'could', 'might', 'unless', 'until', 'after', 'before', 'during',
            'while', 'when', 'where', 'why', 'how', 'what', 'which', 'who',
            'whose', 'whom', 'whether', 'within', 'without', 'through', 'throughout',
            'therefore', 'however', 'moreover', 'furthermore', 'nevertheless',
            'notwithstanding', 'accordingly', 'consequently', 'hence', 'thus',
            'reference', 'dealer', 'partial', 'redemption', 'definitive', 'notes',
            'bonds', 'securities', 'shares', 'stock', 'equity', 'debt', 'loan',
            'business day', 'calculation', 'paying', 'agent', 'trustee', 'registrar',
            'noteholders', 'issuers', 'conditions', 'terms', 'rate', 'amount',
            'interest', 'payment', 'office', 'city', 'market', 'currency', 'cheque',
            'drawn', 'specified', 'independent', 'replacement', 'reference'
        }
        
        # Check length (most bank names are between 4 and 100 characters)
        if not bank or len(bank) < 4 or len(bank) > 100:
            return False
            
        # Check for invalid names (exact match only)
        if bank.lower() in invalid_banks:
            return False
            
        # Check for invalid starts
        if bank.startswith((':', '.', '-', '/', '*', '(', ')', '[', ']', '{', '}', '"', '"', "'", "'")):
            return False
            
        # Check for invalid patterns
        invalid_patterns = [
            r'^(?:the|a|an)\s+', # Articles at start
            r'\b(?:page|section|part|see|note|refer|please|pursuant|according)\b',  # Common document words
            r'^[0-9.]+$',  # Just numbers
            r'^[^a-zA-Z]*$',  # No letters at all
            r'[<>{}[\]|]',  # HTML/markdown characters
            r'^\s*[^A-Za-z0-9]+\s*$',  # Only special characters
            r'(?i)existing\s+code',  # Code comments
            r'(?i)shall\s+|will\s+|may\s+|can\s+|must\s+|should\s+',  # Modal verbs
            r'(?i)if\s+|unless\s+|until\s+|while\s+|when\s+',  # Conditional words
            r'(?i)means\s+|refers\s+to\s+|defined\s+as\s+',  # Definition phrases
            r'(?i)pursuant\s+to\s+|according\s+to\s+|with\s+respect\s+to\s+',  # Legal phrases
            r'(?i)applicable|not\s+applicable',  # Common form phrases
            r'(?i)reference\s+dealers?',  # Reference dealers
            r'(?i)partial\s+redemption',  # Redemption terms
            r'(?i):\s*[^A-Z]',  # Colon followed by non-uppercase (likely a form field)
            r'(?i)agent\s*:',  # Agent field labels
            r'(?i)(?:calculation|paying|fiscal|transfer|quotation)\s+agents?',  # Agent types
            r'(?i)(?:trustee|registrar|manager|coordinator|bookrunner)s?',  # Other role types
            r'(?i)definitive\s+notes?',  # Definitive notes
            r'(?i)bonds?|securities?|shares?|stock|equity|debt|loan',  # Financial instruments
            r'(?i)business\s+day',  # Business day references
            r'(?i)calculation|paying|agent|trustee|registrar',  # Role references
            r'(?i)noteholders?|issuers?|conditions?|terms?',  # Document references
            r'(?i)rate|amount|interest|payment',  # Financial terms
            r'(?i)office|city|market|currency',  # Location/market terms
            r'(?i)cheque|drawn|specified|independent',  # Other common terms
            r'(?i)replacement|reference'  # Technical terms
        ]
        
        for pattern in invalid_patterns:
            if re.search(pattern, bank):
                return False
                
        # Must contain at least 2 letters
        if len(re.findall(r'[a-zA-Z]', bank)) < 2:
            return False
            
        # Check for balanced parentheses/brackets
        if bank.count('(') != bank.count(')') or bank.count('[') != bank.count(']'):
            return False
            
        # Must contain at least one word with capital letter (proper noun)
        if not re.search(r'\b[A-Z][a-z]+\b', bank):
            return False
            
        # Shouldn't be just a role description
        role_words = {'agent', 'trustee', 'registrar', 'manager', 'coordinator', 'bookrunner'}
        bank_words = bank.lower().split()
        if all(word in role_words for word in bank_words):
            return False
            
        return True
    
    def extract_bank_info(self, text: str) -> Dict:
        """Extract bank information from text."""
        result = {
            "banks": [],
            "roles": {},
            "contact_info": {},
            "distribution_method": None
        }
        
        try:
            # Bank name validation pattern - must contain common bank identifiers
            bank_identifiers = r'(?:Bank|AG|PLC|N\.V\.|S\.A\.|Ltd\.?|Limited|Corp\.?|Corporation|Inc\.?|Incorporated|Capital|Securities|Partners|Group|Holdings|Finance|Credit|Trust)'
            
            # Common words that should not be considered bank names
            excluded_phrases = [
                'credit assigned', 'credit rating', 'bank rate', 'hybrid capital',
                'equity credit', 'principal amount', 'third party', 'greater than',
                'outstanding', 'paragraph', 'agency', 'general', 'purposes',
                'acquisition', 'agreement', 'partnership', 'share capital'
            ]
            
            # Role patterns with more precise matching
            role_patterns = {
                'global_coordinator': r'(?:The\s+)?(?:Joint\s+)?Global\s+Coordinators?\s*(?:and\s*(?:Joint\s+)?Active\s*Bookrunners?)?\s*(?:is|are|:)\s*([^.]*?)(?=(?:Joint\s+Active\s+Bookrunners?|Stabilisation|$))',
                'bookrunner': r'(?:The\s+)?Joint\s+Active\s+Bookrunners?\s*(?:is|are|:)\s*([^.]*?)(?=(?:Stabilisation|$))',
                'stabilisation_manager': r'(?:The\s+)?Stabilisation\s+Managers?\s*(?:is|are|:)\s*([^.]*?)(?=(?:Calculation|Paying|Trustee|$))',
                'calculation_agent': r'(?:The\s+)?Calculation\s+Agents?\s*(?:is|are|:)\s*([^.]*?)(?=(?:Paying|Trustee|$))',
                'paying_agent': r'(?:The\s+)?(?:Principal\s+)?Paying\s+Agents?\s*(?:is|are|:)\s*([^.]*?)(?=(?:Trustee|$))',
                'trustee': r'(?:The\s+)?Trustees?\s*(?:is|are|:)\s*([^.]*?)(?=(?:Registrar|$))',
                'registrar': r'(?:The\s+)?Registrars?\s*(?:is|are|:)\s*([^.]*?)(?=(?:Dealer|$))',
                'dealer': r'(?:The\s+)?(?:Permanent\s+)?Dealers?\s*(?:is|are|:)\s*([^.]*?)(?=(?:Manager|$))',
                'manager': r'(?:The\s+)?(?:Joint\s+Lead\s+)?Managers?\s*(?:is|are|:)\s*([^.]*?)(?=(?:Co-Lead|$))',
                'co_lead_manager': r'(?:The\s+)?Co-Lead\s+Managers?\s*(?:is|are|:)\s*([^.]*?)(?=(?:$))'
            }

            def is_valid_bank_name(name):
                """Validate a potential bank name."""
                # Must contain a bank identifier
                if not re.search(bank_identifiers, name, re.IGNORECASE):
                    return False
                    
                # Must be reasonable length
                if not (4 < len(name) < 100):
                    return False
                    
                # Must not start with common words
                if re.match(r'^(?:the|and|or|[^a-zA-Z])', name.lower()):
                    return False
                    
                # Must not contain excluded phrases
                if any(phrase.lower() in name.lower() for phrase in excluded_phrases):
                    return False
                    
                # Must contain at least one capital letter (most bank names are proper nouns)
                if not re.search(r'[A-Z]', name):
                    return False
                    
                # Must not be mostly lowercase (most bank names are in Title Case or UPPER CASE)
                lowercase_ratio = len(re.findall(r'[a-z]', name)) / float(len(name))
                if lowercase_ratio > 0.7:  # If more than 70% lowercase, probably not a bank name
                    return False
                    
                # Must not end with an asterisk (often indicates a section title)
                if name.strip().endswith('*'):
                    return False
                    
                # Must not be all uppercase (often indicates a section title)
                uppercase_ratio = len(re.findall(r'[A-Z]', name)) / float(len(name))
                if uppercase_ratio > 0.8:  # If more than 80% uppercase, probably a section title
                    return False
                    
                return True

            # Process each role pattern
            for role, pattern in role_patterns.items():
                matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    banks_text = match.group(1).strip()
                    # Split on common separators and clean each bank name
                    potential_banks = re.split(r'\s*(?:,|\sand\s|\n)\s*', banks_text)
                    
                    for bank in potential_banks:
                        bank = bank.strip()
                        # Validate bank name using enhanced validation
                        if is_valid_bank_name(bank):
                            if bank not in result["roles"]:
                                result["roles"][bank] = []
                            if role not in result["roles"][bank]:
                                result["roles"][bank].append(role)
                            if bank not in result["banks"]:
                                result["banks"].append(bank)

            # Look for additional banks in bullet points or numbered lists
            bullet_pattern = r'(?:^|\n)(?:[•\-\*]|\d+\.)\s*([^:\n]+)(?:\n|$)'
            matches = re.finditer(bullet_pattern, text)
            for match in matches:
                bank = match.group(1).strip()
                # Validate potential bank names using enhanced validation
                if is_valid_bank_name(bank):
                    if bank not in result["banks"]:
                        result["banks"].append(bank)

            # Log the number of banks found
            self.logger.info(f"\nFound {len(result['banks'])} banks:")
            for bank in result["banks"]:
                self.logger.info(f"\nBank: {bank}")
                if bank in result["roles"]:
                    self.logger.info(f"Roles: {', '.join(result['roles'][bank])}")

            return result

        except Exception as e:
            self.logger.error(f"Error extracting bank information: {str(e)}")
            return {
                "banks": [],
                "roles": {},
                "contact_info": {},
                "distribution_method": None
            }
    
    def process_pdfs(self) -> List[Dict]:
        """Process all PDFs in the download directory"""
        results = []
        
        # Get all PDF files
        pdf_files = [f for f in os.listdir(self.pdf_dir) if f.endswith('.pdf')]
        self.logger.info(f"Found {len(pdf_files)} PDF files in total")
        
        # Filter for final terms documents
        final_terms = [f for f in pdf_files if self.is_final_terms(f)]
        self.logger.info(f"Found {len(final_terms)} final terms documents")
        
        for filename in final_terms:
            self.logger.info(f"\nProcessing {filename}")
            pdf_path = os.path.join(self.pdf_dir, filename)
            try:
                # Extract text
                text = self.extract_text(pdf_path)
                if not text:
                    continue
                
                # Extract bank information
                data = self.extract_bank_info(text)
                data["filename"] = filename
                data["processed_at"] = datetime.utcnow().isoformat()
                
                results.append(data)
                
                # Print results
                self.logger.info(f"\nResults for {filename}:")
                self.logger.info(f"Found {len(data['banks'])} banks:")
                for bank in data["banks"]:
                    self.logger.info(f"- {bank}: {', '.join(data['roles'][bank])}")
                
            except Exception as e:
                self.logger.error(f"Error processing {filename}: {str(e)}", exc_info=True)
        
        return results

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