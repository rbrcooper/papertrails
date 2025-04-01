import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from config.settings import (
    MAX_RETRIES,
    RETRY_DELAY,
    PAGE_LOAD_TIMEOUT,
    ELEMENT_TIMEOUT,
    COMPANIES,
    PDF_DIR,
    FINANCIAL_DATA_DIR,
    ESMA_BASE_URL,
    ESMA_SEARCH_URL,
    ESMA_DOC_URL
)
from database.db_manager import DatabaseManager
from utils.helpers import (
    setup_logging,
    save_json,
    load_json,
    save_excel,
    parse_date,
    clean_text,
    validate_required_fields,
    is_valid_pdf
)
from database.models import Bond, Document

class ESMAWorkflow:
    def __init__(self):
        """Initialize the workflow"""
        try:
            self.logger = setup_logging(__name__)
            self.logger.info("Initializing ESMA workflow")
            
            # Set up Chrome options
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-infobars')
            chrome_options.add_argument('--disable-notifications')
            chrome_options.add_argument('--disable-popup-blocking')
            chrome_options.add_argument('--start-maximized')
            
            # Initialize Chrome WebDriver with specific version
            self.logger.info("Initializing Chrome WebDriver")
            service = Service("chromedriver.exe")  # Use local chromedriver
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Set page load timeout
            self.driver.set_page_load_timeout(30)
            
            # Initialize database manager
            self.db = DatabaseManager()
            self.db.init_db()
            
            # Initialize workflow status
            self.workflow_status = {
                "start_time": None,
                "end_time": None,
                "current_company": None,
                "current_bond": None,
                "status": "initialized",
                "errors": []
            }
            
            self.logger.info("Workflow initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing workflow: {str(e)}")
            raise
            
    def initialize(self):
        """Initialize the workflow"""
        try:
            self.logger.info("Initializing ESMA workflow")
            self.workflow_status["start_time"] = datetime.utcnow().isoformat()
            self.workflow_status["status"] = "running"
            
            # Initialize WebDriver
            self.initialize_driver()
            
            # Create necessary directories
            self.setup_directories()
            
            self.logger.info("Workflow initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Workflow initialization failed: {str(e)}")
            self.workflow_status["errors"].append({
                "stage": "initialization",
                "error": str(e)
            })
            raise
            
    def initialize_driver(self):
        """Initialize the Chrome WebDriver"""
        try:
            self.logger.info("Initializing Chrome WebDriver")
            
            # Set up Chrome options
            chrome_options = Options()
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-notifications')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            
            # Initialize Chrome driver using Selenium Manager
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
            
            self.logger.info("Chrome WebDriver initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Chrome WebDriver: {str(e)}")
            raise
            
    def setup_directories(self):
        """Create necessary directories"""
        directories = [
            PDF_DIR,
            FINANCIAL_DATA_DIR,
            PDF_DIR / "temp"  # For temporary downloads
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            
    def process_company(self, company_name: str, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single company"""
        try:
            self.logger.info(f"Processing company: {company_name}")
            self.workflow_status["current_company"] = company_name
            
            # Get or create issuer in database
            issuer_id = self.db.get_or_create_issuer({
                "name": company_name,
                "lei": company_data["lei"],
                "country": company_data["country"],
                "industry": company_data.get("industry", "")
            })
            
            # Search for bonds
            bonds = self.search_bonds(company_data["lei"])
            
            # Process each bond
            for bond in bonds:
                try:
                    self.process_bond(bond, issuer_id)
                except Exception as e:
                    self.logger.error(f"Error processing bond {bond.get('isin', 'Unknown')}: {str(e)}")
                    continue
            
            # Generate company report
            self.generate_company_report(company_name)
            
            return {"success": True, "bond_count": len(bonds)}
            
        except Exception as e:
            self.logger.error(f"Error processing company {company_name}: {str(e)}")
            return {"success": False, "error": str(e)}
            
    def search_bonds(self, lei: str) -> List[Dict[str, Any]]:
        """Search for bonds using LEI"""
        try:
            self.logger.info(f"Searching bonds for LEI: {lei}")
            
            # Navigate to search page
            self.driver.get(ESMA_SEARCH_URL)
            
            # Wait for page to load
            wait = WebDriverWait(self.driver, 20)  # Increased timeout
            
            try:
                # Wait for and find search form
                search_form = wait.until(
                    EC.presence_of_element_located((By.ID, "searchRegisterForm"))
                )
                self.logger.info("Found search form")
                
                # Find search input and submit button within the form
                search_input = search_form.find_element(By.CSS_SELECTOR, "input[type='text']")
                submit_button = search_form.find_element(By.CSS_SELECTOR, "button[type='submit']")
                
                if not search_input or not submit_button:
                    raise NoSuchElementException("Could not find search input or submit button")
                    
                # Enter search query and submit
                search_query = f'lei:"{lei}" AND docType:FT'
                self.logger.info(f"Entering search query: {search_query}")
                search_input.clear()
                search_input.send_keys(search_query)
                
                # Click submit button
                self.logger.info("Clicking submit button")
                submit_button.click()
                
                # Wait for results or no results message
                try:
                    wait.until(lambda driver: 
                        len(driver.find_elements(By.CLASS_NAME, "ui-datatable")) > 0 or
                        len(driver.find_elements(By.CLASS_NAME, "ui-datatable-empty-message")) > 0
                    )
                except TimeoutException:
                    self.logger.warning("Timeout waiting for search results")
                    return []
                    
                # Check for no results
                if len(self.driver.find_elements(By.CLASS_NAME, "ui-datatable-empty-message")) > 0:
                    self.logger.info("No bonds found")
                    return []
                    
                # Get results table
                results = []
                table = self.driver.find_element(By.CLASS_NAME, "ui-datatable")
                rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
                
                for row in rows:
                    try:
                        # Extract bond data from row
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) < 7:  # Ensure we have enough cells
                            continue
                            
                        # Get document link
                        doc_link = cells[0].find_element(By.TAG_NAME, "a")
                        doc_url = doc_link.get_attribute("href")
                        doc_name = doc_link.text.strip()
                        
                        # Extract bond details
                        bond_data = {
                            "isin": cells[1].text.strip(),
                            "name": cells[2].text.strip(),
                            "issue_date": cells[3].text.strip(),
                            "maturity_date": cells[4].text.strip(),
                            "currency": cells[5].text.strip(),
                            "nominal_amount": cells[6].text.strip(),
                            "coupon_rate": cells[7].text.strip() if len(cells) > 7 else None,
                            "doc_url": doc_url,
                            "doc_name": doc_name
                        }
                        
                        self.logger.info(f"Found bond: {bond_data['isin']}")
                        results.append(bond_data)
                        
                    except (NoSuchElementException, IndexError) as e:
                        self.logger.warning(f"Error extracting bond data from row: {str(e)}")
                        continue
                        
                return results
                
            except NoSuchElementException as e:
                self.logger.error(f"Could not find element: {str(e)}")
                raise
                
            except TimeoutException as e:
                self.logger.error(f"Timeout waiting for element: {str(e)}")
                raise
                
        except Exception as e:
            self.logger.error(f"Error searching bonds: {str(e)}")
            raise
            
    def process_bond(self, bond_data: Dict[str, Any], issuer_id: int) -> None:
        """Process a bond and its documents"""
        try:
            self.logger.info(f"Processing bond: {bond_data['isin']}")
            
            # Create or get bond
            session = self.db.get_session()
            bond = self.db.get_or_create_bond(
                session,
                isin=bond_data['isin'],
                name=bond_data['name'],
                issue_date=bond_data['issue_date'],
                maturity_date=bond_data['maturity_date'],
                amount=bond_data['nominal_amount'],
                currency=bond_data['currency'],
                coupon_rate=bond_data['coupon_rate'],
                issuer_id=issuer_id
            )
            
            # Create document
            doc = self.db.get_or_create_document(
                session,
                name=bond_data['doc_name'],
                type='FT',  # Final Terms
                url=bond_data['doc_url'],
                bond_id=bond.id
            )
            
            # Process documents
            self.process_bond_documents(bond.id, bond_data['isin'])
            
        except Exception as e:
            self.logger.error(f"Error processing bond {bond_data['isin']}: {str(e)}")
            raise
            
    def process_bond_documents(self, bond_id: int, isin: str) -> None:
        """Process documents for a bond"""
        try:
            self.logger.info(f"Processing documents for ISIN: {isin}")
            
            # Create directory for bond documents
            bond_dir = PDF_DIR / isin
            bond_dir.mkdir(parents=True, exist_ok=True)
            
            # Get bond data from database
            session = self.db.get_session()
            bond = session.query(Bond).get(bond_id)
            
            if not bond:
                raise ValueError(f"Bond not found: {isin}")
            
            # Download and process documents
            for doc in bond.documents:
                try:
                    if not doc.local_path or not Path(doc.local_path).exists():
                        # Download document
                        self.logger.info(f"Downloading document: {doc.name}")
                        local_path = self.download_document(doc.url, bond_dir, doc.name)
                        
                        if local_path and is_valid_pdf(local_path):
                            doc.local_path = str(local_path)
                            doc.processed_at = datetime.utcnow()
                            session.commit()
                            self.logger.info(f"Document downloaded and processed: {doc.name}")
                        else:
                            self.logger.warning(f"Failed to download or invalid PDF: {doc.name}")
                            
                except Exception as e:
                    self.logger.error(f"Error processing document {doc.name}: {str(e)}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error processing bond documents: {str(e)}")
            raise
            
    def download_document(self, url: str, save_dir: Path, doc_name: str) -> Optional[Path]:
        """Download a document and return its local path"""
        try:
            self.logger.info(f"Downloading document from: {url}")
            
            # Navigate to document URL
            self.driver.get(url)
            
            # Wait for download to complete
            time.sleep(2)  # Basic wait, could be improved with actual download status check
            
            # Generate filename
            filename = f"{clean_text(doc_name)}.pdf"
            filepath = save_dir / filename
            
            # Verify file exists and is valid
            if filepath.exists() and is_valid_pdf(filepath):
                return filepath
            else:
                self.logger.warning(f"Downloaded file not found or invalid: {filepath}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error downloading document: {str(e)}")
            return None
            
    def generate_company_report(self, company_name: str) -> None:
        """Generate report for a company"""
        try:
            self.logger.info(f"Generating report for company: {company_name}")
            
            # TODO: Implement report generation logic
            # This is a placeholder
            pass
            
        except Exception as e:
            self.logger.error(f"Error generating company report: {str(e)}")
            raise
            
    def generate_reports(self) -> None:
        """Generate final reports"""
        try:
            self.logger.info("Generating final reports")
            
            # TODO: Implement final report generation logic
            # This is a placeholder
            pass
            
        except Exception as e:
            self.logger.error(f"Error generating final reports: {str(e)}")
            raise

def is_valid_pdf(filepath: Path) -> bool:
    """Check if a file is a valid PDF"""
    try:
        if not filepath.exists():
            return False
            
        # Check file size
        if filepath.stat().st_size < 100:  # Minimum size for a valid PDF
            return False
            
        # Check file extension
        if filepath.suffix.lower() != '.pdf':
            return False
            
        # Basic header check
        with open(filepath, 'rb') as f:
            header = f.read(5)
            if header != b'%PDF-':
                return False
                
        return True
        
    except Exception:
        return False
        
def clean_text(text: str) -> str:
    """Clean text for use in filenames"""
    # Replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        text = text.replace(char, '_')
        
    # Remove or replace other problematic characters
    text = text.replace('\n', ' ').replace('\r', ' ')
    
    # Limit length and remove trailing spaces/dots
    text = text[:100].strip('. ')
    
    return text if text else 'unnamed'

def main():
    workflow = ESMAWorkflow()
    workflow.run()

if __name__ == "__main__":
    main() 