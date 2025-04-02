from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
import time
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional
import urllib.parse
import requests

class ESMAScraper:
    def __init__(self, download_dir="downloads"):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
        self.setup_logging()
        self.setup_driver()
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def setup_driver(self):
        """Setup Chrome driver with appropriate options"""
        options = Options()
        # options.add_argument("--headless")  # Temporarily disable headless mode for debugging
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        
        # Set download preferences
        options.add_experimental_option("prefs", {
            "download.default_directory": os.path.abspath(self.download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        })
        
        # Create driver with extended timeout
        self.driver = webdriver.Chrome(options=options)
        self.driver.set_page_load_timeout(30)
        self.wait = WebDriverWait(self.driver, 20)  # 20 second timeout for element waits
        
        # Handle cookie consent if present
        try:
            cookie_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'OK')]"))
            )
            cookie_button.click()
            self.logger.info("Accepted cookies")
        except:
            self.logger.info("No cookie consent found")
        
    def search_and_download(self, company_name: str) -> List[Dict]:
        """Search for a company's bonds and download prospectuses"""
        results = []
        try:
            # Navigate directly to the PRIIPs Register search
            encoded_name = urllib.parse.quote(company_name)
            search_url = f"https://registers.esma.europa.eu/publication/searchRegister?core=esma_registers_priii_documents&keyword={encoded_name}&search=Search"
            self.driver.get(search_url)
            self.logger.info(f"Navigating to search URL: {search_url}")
            
            # Wait for page load and log page title
            time.sleep(5)
            self.logger.info(f"Page title: {self.driver.title}")
            
            # Check if we need to handle any popups or overlays
            try:
                # Look for common popup elements
                popup_elements = self.driver.find_elements(By.CSS_SELECTOR, ".modal, .popup, .overlay")
                if popup_elements:
                    self.logger.info(f"Found {len(popup_elements)} potential popup elements")
                    for element in popup_elements:
                        self.logger.info(f"Popup text: {element.text[:100]}...")
            except Exception as e:
                self.logger.info(f"No popups found: {str(e)}")
            
            # Wait for results page
            time.sleep(8)
            
            # Log the current URL and page source for debugging
            self.logger.info(f"Current URL: {self.driver.current_url}")
            self.logger.info("Page source preview: " + self.driver.page_source[:1000])
            
            try:
                # Wait for results table
                table = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
                )
                self.logger.info("Found results table")
                
                # Get all document rows
                document_rows = table.find_elements(By.TAG_NAME, "tr")[1:]  # Skip header row
                self.logger.info(f"Found {len(document_rows)} document rows")
                
                if not document_rows:
                    self.logger.warning(f"No documents found for {company_name}")
                    # Take screenshot for debugging
                    self.driver.save_screenshot("no_results.png")
                    self.logger.info("Saved no results screenshot")
                    return results
                
                for row in document_rows:
                    try:
                        # Extract document info
                        doc_info = self.extract_document_info(row)
                        if doc_info:
                            results.append(doc_info)
                            self.logger.info(f"Found document: {doc_info['name']}")
                            
                            # Download if it's a PDF
                            if doc_info["type"].lower() == "pdf":
                                self.download_document(row)
                                
                    except Exception as e:
                        self.logger.error(f"Error processing document row: {str(e)}")
                        continue
                        
            except TimeoutException:
                self.logger.warning("No results table found")
                # Take screenshot for debugging
                self.driver.save_screenshot("no_table.png")
                self.logger.info("Saved no table screenshot")
                
        except Exception as e:
            self.logger.error(f"Error processing {company_name}: {str(e)}")
            
        return results
    
    def extract_document_info(self, row) -> Optional[Dict]:
        """Extract information from a document row"""
        try:
            # Get all cells in the row
            cells = row.find_elements(By.TAG_NAME, "td")
            self.logger.info(f"Found {len(cells)} cells in row")
            
            if len(cells) >= 10:  # We need at least 10 cells (0-9)
                # Get issuer name first (fourth cell) to filter
                issuer = cells[4].text.strip()  # Issuer is in cell 4
                
                # Only process if issuer contains TotalEnergies
                if "TotalEnergies" not in issuer:
                    return None
                
                # Get document type (first cell)
                doc_type = cells[1].text.strip()  # Document type is in cell 1
                
                # Get document name (second cell)
                doc_name = cells[2].text.strip()  # Document name is in cell 2
                
                # Get document date (third cell)
                doc_date = cells[3].text.strip()  # Date is in cell 3
                
                # Get document link (ninth cell - PDF)
                pdf_cell = cells[9]
                try:
                    pdf_link = pdf_cell.find_element(By.TAG_NAME, "a")
                    doc_link = pdf_link.get_attribute("href")
                    
                    if doc_link:
                        # Clean up the date format for filename
                        clean_date = doc_date.replace('/', '-')
                        return {
                            "type": doc_type,
                            "name": doc_name,
                            "date": doc_date,
                            "clean_date": clean_date,  # Add clean date for filenames
                            "issuer": issuer,
                            "url": doc_link,
                            "processed_at": datetime.utcnow().isoformat()
                        }
                except NoSuchElementException:
                    self.logger.warning("No PDF link found in cell 9")
                    return None
            else:
                self.logger.warning(f"Row does not have enough cells (found {len(cells)})")
                return None
            
        except NoSuchElementException as e:
            self.logger.warning(f"Could not extract document info: {str(e)}")
            return None
            
    def download_document(self, row):
        """Download a document from a row"""
        try:
            # Find and click download link in the last cell
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 4:
                download_link = cells[3].find_element(By.TAG_NAME, "a")
                if download_link.get_attribute("href").lower().endswith(".pdf"):
                    download_link.click()
                    self.logger.info("Clicked download link")
                    # Wait for download to start
                    time.sleep(2)
                else:
                    self.logger.warning("Link is not a PDF")
            else:
                self.logger.warning("Row does not have enough cells for download")
            
        except NoSuchElementException:
            self.logger.warning("No PDF download link found")
        except Exception as e:
            self.logger.error(f"Error downloading document: {str(e)}")
            
    def close(self):
        """Close the browser"""
        self.driver.quit()

def main():
    # Example usage
    scraper = ESMAScraper()
    company = "TotalEnergies"
    
    try:
        print(f"\nProcessing {company}...")
        results = scraper.search_and_download(company)
        print(f"\nFound {len(results)} documents:")
        for doc in results:
            print(f"\nDocument:")
            print(f"  Type: {doc['type']}")
            print(f"  Name: {doc['name']}")
            print(f"  Date: {doc['date']}")
            print(f"  Issuer: {doc['issuer']}")
            print(f"  URL: {doc['url']}")
            
            # Try to download the document
            try:
                print("  Downloading PDF...")
                response = requests.get(doc['url'])
                if response.status_code == 200:
                    # Use clean date format for filename
                    filename = f"{company}_{doc['clean_date']}_{doc['type'].replace(' ', '_')}.pdf"
                    with open(os.path.join(scraper.download_dir, filename), 'wb') as f:
                        f.write(response.content)
                    print(f"  Downloaded: {filename}")
                else:
                    print(f"  Failed to download: HTTP {response.status_code}")
            except Exception as e:
                print(f"  Error downloading: {str(e)}")
    finally:
        scraper.close()

if __name__ == "__main__":
    main() 