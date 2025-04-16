"""
File Organizer Utility
---------------------
This utility organizes downloaded PDF files from the ESMA website into a consistent structure.

Features:
- Moves loose PDFs into appropriate company folders
- Implements consistent naming scheme: {company_name}/{document_type}_{date}_{hash}.pdf
- Avoids duplicate files by checking content hash
- Logs all file operations for auditing
- Supports dry-run mode for testing
"""

import os
import re
import shutil
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional
import fitz  # PyMuPDF
import concurrent.futures
from ..company_list_handler import CompanyListHandler

class FileOrganizer:
    """Organizes PDF files in the downloads directory according to a consistent structure"""
    
    def __init__(self, 
                 downloads_dir: str = "data/downloads", 
                 log_file: str = "logs/file_organizer.log",
                 dry_run: bool = False,
                 max_workers: int = 4):
        """Initialize the file organizer
        
        Args:
            downloads_dir: Path to the downloads directory
            log_file: Path to the log file
            dry_run: If True, only print operations without executing them
            max_workers: Maximum number of concurrent workers
        """
        self.downloads_dir = Path(downloads_dir)
        self.log_file = Path(log_file)
        self.dry_run = dry_run
        self.max_workers = max_workers
        self.company_handler = CompanyListHandler()
        self.processed_files = set()
        self.setup_logging()
        
    def setup_logging(self):
        """Set up logging to file and console"""
        # Create log directory if it doesn't exist
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Log initialization
        mode = "DRY RUN" if self.dry_run else "EXECUTE"
        self.logger.info(f"File Organizer initialized in {mode} mode")
        self.logger.info(f"Downloads directory: {self.downloads_dir}")
        
    def get_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file content
        
        Args:
            file_path: Path to the file
            
        Returns:
            str: Hexadecimal hash of file content
        """
        try:
            hash_obj = hashlib.sha256()
            with open(file_path, 'rb') as f:
                # Read in chunks to handle large files
                for chunk in iter(lambda: f.read(4096), b''):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except Exception as e:
            self.logger.error(f"Error calculating hash for {file_path}: {str(e)}")
            return ""
            
    def detect_document_type(self, file_path: Path) -> str:
        """Attempt to detect document type from PDF content
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            str: Detected document type or "unknown"
        """
        try:
            # Common document type indicators
            type_indicators = {
                "base_prospectus": [
                    "base prospectus", "base programme", "debt issuance programme", 
                    "euro medium term note programme"
                ],
                "final_terms": [
                    "final terms", "final term sheet", "pricing supplement"
                ],
                "supplement": [
                    "supplement to the base prospectus", "supplemental prospectus",
                    "supplement no.", "supplemental"
                ],
                "annual_report": [
                    "annual report", "annual financial report", "yearly report"
                ],
                "quarterly_report": [
                    "quarterly report", "quarterly financial report", "q1", "q2", "q3", "q4"
                ]
            }
            
            # Open PDF and extract first few pages
            doc = fitz.open(file_path)
            text = ""
            # Extract text from first 5 pages or all pages if less than 5
            for i in range(min(5, doc.page_count)):
                page = doc[i]
                text += page.get_text()
            text = text.lower()
            
            # Check for document type indicators
            for doc_type, indicators in type_indicators.items():
                for indicator in indicators:
                    if indicator.lower() in text:
                        return doc_type
            
            # Check filename for indicators
            filename = file_path.name.lower()
            for doc_type, indicators in type_indicators.items():
                for indicator in indicators:
                    if indicator.lower() in filename:
                        return doc_type
            
            return "unknown"
        except Exception as e:
            self.logger.error(f"Error detecting document type for {file_path}: {str(e)}")
            return "unknown"
            
    def extract_date(self, file_path: Path) -> str:
        """Attempt to extract date from PDF content or filename
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            str: Extracted date in YYYYMMDD format or "00000000" if not found
        """
        try:
            # First try to extract from filename
            filename = file_path.name
            date_patterns = [
                r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})',  # YYYY-MM-DD or YYYYMMDD
                r'(\d{2})[-_]?(\d{2})[-_]?(\d{4})',  # DD-MM-YYYY or DDMMYYYY
                r'(\d{2})[-_]?([A-Za-z]{3})[-_]?(\d{4})'  # DD-MMM-YYYY
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, filename)
                if match:
                    # Handle different date formats
                    if len(match.group(2)) == 3:  # Month is in text format
                        month_dict = {
                            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                            'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
                            'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
                        }
                        month = month_dict.get(match.group(2).lower(), '00')
                        day = match.group(1)
                        year = match.group(3)
                        return f"{year}{month}{day}"
                    elif len(match.group(1)) == 4:  # YYYY-MM-DD
                        return f"{match.group(1)}{match.group(2)}{match.group(3)}"
                    else:  # DD-MM-YYYY
                        return f"{match.group(3)}{match.group(2)}{match.group(1)}"
            
            # If no date in filename, try extracting from content
            doc = fitz.open(file_path)
            text = ""
            # Extract text from first 3 pages
            for i in range(min(3, doc.page_count)):
                page = doc[i]
                text += page.get_text()
            
            # Look for dates in the text
            date_patterns = [
                r'(?:dated|date[d]?:?|as of)\s+(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(\d{4})',
                r'(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(\d{4})',
                r'(\d{1,2})[-./](\d{1,2})[-./](\d{4})',
                r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})'
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    if match.group(2).isalpha():  # Date with month name
                        month_dict = {
                            'january': '01', 'february': '02', 'march': '03', 'april': '04',
                            'may': '05', 'june': '06', 'july': '07', 'august': '08',
                            'september': '09', 'october': '10', 'november': '11', 'december': '12'
                        }
                        month = month_dict.get(match.group(2).lower(), '00')
                        day = match.group(1).zfill(2)
                        year = match.group(3)
                        return f"{year}{month}{day}"
                    elif len(match.group(1)) == 4:  # YYYY-MM-DD
                        year = match.group(1)
                        month = match.group(2).zfill(2)
                        day = match.group(3).zfill(2)
                        return f"{year}{month}{day}"
                    else:  # DD-MM-YYYY
                        day = match.group(1).zfill(2)
                        month = match.group(2).zfill(2)
                        year = match.group(3)
                        return f"{year}{month}{day}"
            
            # Use current date if no date found
            today = datetime.now()
            return f"{today.year}{today.month:02d}{today.day:02d}"
            
        except Exception as e:
            self.logger.error(f"Error extracting date for {file_path}: {str(e)}")
            return "00000000"  # Default date if extraction fails
            
    def identify_company(self, file_path: Path) -> Optional[str]:
        """Identify the company that the PDF belongs to
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Optional[str]: Company name or None if not identified
        """
        try:
            # Get all company names
            companies = self.company_handler.get_all_companies()
            company_names = [company['name'] for company in companies]
            
            # First check if the file is already in a company folder
            parent_dir = file_path.parent.name
            if parent_dir in company_names:
                return parent_dir
                
            # Check if company name is in filename
            filename = file_path.stem
            for company in company_names:
                # Try exact match first
                if company.lower() in filename.lower():
                    return company
            
            # Try content-based identification
            doc = fitz.open(file_path)
            text = ""
            # Extract text from first 5 pages
            for i in range(min(5, doc.page_count)):
                page = doc[i]
                text += page.get_text()
            
            # Look for company names in the text
            best_match = None
            max_score = 0
            for company in company_names:
                score = 0
                if company.lower() in text.lower():
                    # Count occurrences
                    score = text.lower().count(company.lower()) * 10
                    if score > max_score:
                        max_score = score
                        best_match = company
            
            return best_match

        except Exception as e:
            self.logger.error(f"Error identifying company for {file_path}: {str(e)}")
            return None
            
    def organize_file(self, file_path: Path) -> Tuple[bool, Optional[Path]]:
        """Organize a single PDF file
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Tuple[bool, Optional[Path]]: (Success flag, New file path if moved)
        """
        try:
            # Skip if not a PDF
            if file_path.suffix.lower() != '.pdf':
                self.logger.warning(f"Skipping non-PDF file: {file_path}")
                return False, None
                
            # Calculate file hash for deduplication
            file_hash = self.get_file_hash(file_path)
            if not file_hash:
                self.logger.error(f"Failed to calculate hash for: {file_path}")
                return False, None
                
            # Check if already processed (deduplication)
            if file_hash in self.processed_files:
                self.logger.info(f"Skipping duplicate file: {file_path}")
                return False, None
            self.processed_files.add(file_hash)
            
            # Identify company
            company_name = self.identify_company(file_path)
            if not company_name:
                self.logger.warning(f"Unable to identify company for: {file_path}")
                company_name = "Unidentified"
                
            # Detect document type
            doc_type = self.detect_document_type(file_path)
            
            # Extract date
            date = self.extract_date(file_path)
            
            # Create target directory
            clean_company_name = re.sub(r'[<>:"/\\|?*]', '_', company_name)
            # Replace spaces with underscores for consistency
            clean_company_name = clean_company_name.replace(' ', '_')
            company_dir = self.downloads_dir / clean_company_name
            
            # Create new filename
            new_filename = f"{doc_type}_{date}_{file_hash[:8]}.pdf"
            target_path = company_dir / new_filename
            
            # Create company directory if it doesn't exist
            if not self.dry_run:
                company_dir.mkdir(parents=True, exist_ok=True)
            
            # Check if target already exists (deduplication)
            if target_path.exists():
                target_hash = self.get_file_hash(target_path)
                if file_hash == target_hash:
                    self.logger.info(f"File already exists at target location: {target_path}")
                    if str(file_path) != str(target_path):  # Not the same file
                        self.logger.info(f"Will remove duplicate: {file_path}")
                        if not self.dry_run:
                            os.remove(file_path)
                    return True, target_path
            
            # Move the file
            self.logger.info(f"Moving: {file_path} -> {target_path}")
            if not self.dry_run:
                shutil.move(file_path, target_path)
            
            return True, target_path
            
        except Exception as e:
            self.logger.error(f"Error organizing file {file_path}: {str(e)}")
            return False, None
            
    def scan_downloads(self) -> List[Path]:
        """Scan the downloads directory for PDF files
        
        Returns:
            List[Path]: List of PDF files
        """
        pdf_files = []
        self.logger.info(f"Scanning {self.downloads_dir} for PDF files")
        
        # Find all PDF files in the downloads directory
        for item in self.downloads_dir.glob("**/*.pdf"):
            if item.is_file():
                pdf_files.append(item)
                
        self.logger.info(f"Found {len(pdf_files)} PDF files")
        return pdf_files
        
    def organize_files(self) -> Dict:
        """Organize all PDF files in the downloads directory
        
        Returns:
            Dict: Statistics about the organization process
        """
        stats = {
            "total_files": 0,
            "organized_files": 0,
            "skipped_files": 0,
            "error_files": 0
        }
        
        # Scan downloads directory
        pdf_files = self.scan_downloads()
        stats["total_files"] = len(pdf_files)
        
        self.logger.info(f"Starting organization of {len(pdf_files)} files")
        self.logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'EXECUTE'}")
        
        # Process files using parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {executor.submit(self.organize_file, pdf_file): pdf_file for pdf_file in pdf_files}
            
            for future in concurrent.futures.as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    success, new_path = future.result()
                    if success:
                        stats["organized_files"] += 1
                    else:
                        stats["skipped_files"] += 1
                except Exception as e:
                    self.logger.error(f"Error processing {file_path}: {str(e)}")
                    stats["error_files"] += 1
        
        # Log statistics
        self.logger.info(f"Organization complete. Stats: {stats}")
        return stats
        
    def dry_run_organize(self) -> Dict:
        """Perform a dry run of the organization process
        
        Returns:
            Dict: Statistics about the organization process
        """
        # Set dry run mode and run organization
        old_dry_run = self.dry_run
        self.dry_run = True
        stats = self.organize_files()
        self.dry_run = old_dry_run
        return stats

def main():
    """Main function to run the file organizer"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Organize PDF files in the downloads directory")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (don't actually move files)")
    parser.add_argument("--downloads-dir", default="data/downloads", help="Path to downloads directory")
    parser.add_argument("--log-file", default="logs/file_organizer.log", help="Path to log file")
    parser.add_argument("--max-workers", type=int, default=4, help="Maximum number of concurrent workers")
    args = parser.parse_args()
    
    organizer = FileOrganizer(
        downloads_dir=args.downloads_dir,
        log_file=args.log_file,
        dry_run=args.dry_run,
        max_workers=args.max_workers
    )
    
    if args.dry_run:
        print("Running in DRY RUN mode (no files will be moved)")
    
    # Run the organization process
    stats = organizer.organize_files()
    
    print(f"Organization complete. Summary:")
    print(f"Total files: {stats['total_files']}")
    print(f"Organized files: {stats['organized_files']}")
    print(f"Skipped files: {stats['skipped_files']}")
    print(f"Error files: {stats['error_files']}")

if __name__ == "__main__":
    main() 