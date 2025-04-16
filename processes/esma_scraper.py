"""
ESMA Web Scraper
---------------
A web scraper for extracting prospectus documents from the ESMA (European Securities and Markets Authority) website.

**ONLY EVER USE THIS WEBSITE**: https://registers.esma.europa.eu/publication/searchRegister?core=esma_registers_priii_documents

Key Features:
- Automated navigation of ESMA's document registry
- Document type filtering (e.g., Final Terms, Base Prospectus)
- Configurable results per page
- Document metadata extraction
- PDF document downloading
- Integrated file organization and deduplication
- Robust error handling and retry mechanisms
- Fuzzy company name matching
- Multi-document type support

Dependencies:
- selenium: Web automation and scraping
- chromedriver: Chrome WebDriver for Selenium
- pandas: Data handling and Excel file operations
- requests: HTTP requests for document downloads
- beautifulsoup4: HTML parsing
- logging: Logging functionality
- fuzzywuzzy: Fuzzy string matching
- python-Levenshtein: Fast Levenshtein distance calculation

Usage:
    from processes.esma_scraper import ESMAScraper
    
    scraper = ESMAScraper()
    scraper.search_and_process("COMPANY_NAME")
    scraper.close()

Configuration:
- Document types can be configured via set_document_type_filter()
- Results per page can be set via set_results_per_page()
- Download paths and other settings are configurable in __init__
"""

import os
import sys
import time
import json
import logging
import requests
import random
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException, ElementNotInteractableException
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from fuzzywuzzy import fuzz
from .company_list_handler import CompanyListHandler
from functools import wraps
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
import re
import shutil
from urllib.parse import urlparse

class ESMAScraper:
    def __init__(self, download_dir=None, debug_mode=True):
        """Initialize the ESMA scraper"""
        self.logger = logging.getLogger(__name__)
        
        # Set base directory for downloads
        self.base_dir = "data/downloads"
        
        # Set download directory
        if download_dir:
            self.download_dir = Path(download_dir)
        else:
            self.download_dir = Path(self.base_dir)
            
        # Create download directory if it doesn't exist
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # Set debug mode
        self.debug_mode = debug_mode
        
        # Setup debug directories
        self.screenshots_dir = Path("logs/screenshots")
        self.page_sources_dir = Path("logs/page_sources")
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.page_sources_dir.mkdir(parents=True, exist_ok=True)
        
        # Base configuration
        self.base_url = "https://registers.esma.europa.eu/publication/searchRegister?core=esma_registers_priii_documents"
        self.headless = True
        self.fuzzy_match_threshold = 80
        self.min_similarity = 80
        self.company_list_handler = CompanyListHandler()
        
        # Session configuration
        self.session_start_time = time.time()
        self.requests_count = 0
        self.max_session_duration = 3600  # 1 hour
        self.max_requests_per_session = 100
        self.min_delay = 1
        self.max_delay = 3
        self.timeout = 10
        self.download_wait_time = 30 # Increased default wait time
        
        # Initialize driver
        self.driver = None
        self.setup_driver()
        
        # Processed files hash tracker for deduplication
        self.processed_files = set()

    def setup_driver(self):
        """Set up the Chrome driver with retries."""
        max_retries = 3
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                # Set up Chrome options
                options = uc.ChromeOptions()
                if self.headless:
                    options.add_argument('--headless')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-gpu')
                options.add_argument('--disable-extensions')
                options.add_argument('--disable-infobars')
                options.add_argument('--disable-notifications')
                options.add_argument('--disable-popup-blocking')
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_argument('--start-maximized')
                
                # Set up download preferences
                prefs = {
                    "download.default_directory": str(self.download_dir.absolute()),
                    "download.prompt_for_download": False,
                    "download.directory_upgrade": True,
                    "safebrowsing.enabled": True
                }
                options.add_experimental_option("prefs", prefs)
                
                # Initialize the undetected Chrome driver
                self.driver = uc.Chrome(options=options)
                self.driver.set_page_load_timeout(30)
                self.wait = WebDriverWait(self.driver, 10)
                self.logger.info("Chrome driver initialized successfully")
                return True
                
            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1} failed to initialize Chrome driver: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    self.logger.error("All attempts to initialize Chrome driver failed")
                    raise

    def close(self):
        """Close the browser and clean up resources."""
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                self.logger.error(f"Error closing browser: {e}")
            finally:
                self.driver = None

    def __del__(self):
        """Ensure browser is closed when object is destroyed."""
        self.close()

    def random_delay(self, min_seconds=1, max_seconds=3):
        """Add a random delay to avoid detection"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)

    def check_session_health(self):
        """Check if we need to refresh the session"""
        current_time = time.time()
        session_duration = current_time - self.session_start_time
        
        if (session_duration > self.max_session_duration or 
            self.requests_count >= self.max_requests_per_session):
            self.logger.info("Session limits reached, refreshing...")
            self.refresh_session()
            return True
        return False

    def refresh_session(self):
        """Refresh the browser session"""
        try:
            if self.driver:
                self.driver.quit()
            self.setup_driver()
            self.session_start_time = time.time()
            self.requests_count = 0
            self.logger.info("Session refreshed successfully")
        except Exception as e:
            self.logger.error(f"Error refreshing session: {str(e)}")
            raise

    def retry_on_failure(max_retries=3, base_delay=5):
        """Enhanced retry decorator with exponential backoff"""
        def decorator(func):
            @wraps(func)
            def wrapper(self, *args, **kwargs):
                last_exception = None
                for attempt in range(max_retries):
                    try:
                        return func(self, *args, **kwargs)
                    except (TimeoutException, StaleElementReferenceException) as e:
                        last_exception = e
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)  # Exponential backoff
                            self.logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay} seconds...")
                            time.sleep(delay)
                            self.refresh_session()  # Refresh session on failure
                        else:
                            self.logger.error(f"All {max_retries} attempts failed: {str(e)}")
                            raise last_exception
                return None
            return wrapper
        return decorator

    @retry_on_failure(max_retries=3, base_delay=5)
    def wait_for_page_load(self, timeout=None):
        """Wait for the page to load completely with enhanced dynamic content detection"""
        if timeout is None:
            timeout = self.timeout
            
        try:
            # Wait for document ready state
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            
            # Wait for jQuery/AJAX requests to complete if jQuery is present
            try:
                WebDriverWait(self.driver, 5).until(
                    lambda driver: driver.execute_script('return jQuery.active == 0')
                )
            except:
                self.logger.debug("jQuery not detected or no active requests")
            
            # Wait for any dynamic content to load
            time.sleep(2)
            
            # Check for common page elements
            try:
                # Wait for either the search form or results table
                WebDriverWait(self.driver, 5).until(
                    lambda driver: (
                        len(driver.find_elements(By.CSS_SELECTOR, "form[name='searchRegisterForm']")) > 0 or
                        len(driver.find_elements(By.CSS_SELECTOR, "table.search-results")) > 0
                    )
                )
            except:
                self.logger.warning("Neither search form nor results table found after page load")
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error waiting for page load: {str(e)}")
            return False

    def take_screenshot(self, name):
        if self.debug_mode:
            try:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{name}_{timestamp}.png"
                self.driver.save_screenshot(str(self.screenshots_dir / filename))
                self.logger.debug(f"Saved screenshot: {filename}")
            except Exception as e:
                self.logger.error(f"Error taking screenshot: {str(e)}")
                
    def save_page_source(self, name):
        if self.debug_mode:
            try:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{name}_{timestamp}.html"
                with open(self.page_sources_dir / filename, 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                self.logger.debug(f"Saved page source: {filename}")
            except Exception as e:
                self.logger.error(f"Error saving page source: {str(e)}")
                
    def navigate_to_search(self):
        """Navigate to the ESMA search page"""
        try:
            self.logger.info(f"Navigating to {self.base_url}")
            self.driver.get(self.base_url)
            self.wait_for_page_load()
            return True
        except Exception as e:
            self.logger.error(f"Error navigating to search page: {str(e)}")
            return False

    def set_results_per_page(self, num_results=100):
        """Set results per page with verification"""
        try:
            # Find and set the dropdown
            dropdown = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.NAME, "pagination.itemsPerPage"))
            )
            
            current_value = dropdown.get_attribute('value')
            self.logger.info(f"Current results per page: {current_value}")
            
            # Set new value
            self.driver.execute_script(
                f"arguments[0].value = '{num_results}'; "
                "arguments[0].dispatchEvent(new Event('change'));"
                "arguments[0].dispatchEvent(new Event('input'));", 
                dropdown
            )
            
            # Wait for page to update
            time.sleep(2)
            self.wait_for_page_load()
            
            # Verify the setting was applied
            new_value = dropdown.get_attribute('value')
            if str(new_value) != str(num_results):
                raise Exception(f"Failed to set results per page. Expected {num_results}, got {new_value}")
            
            # Verify actual number of results
            results_table = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table.table"))
            )
            rows = results_table.find_elements(By.TAG_NAME, "tr")[1:]  # Skip header row
            actual_results = len(rows)
            
            if actual_results > num_results:
                self.logger.warning(f"More results than expected: {actual_results} > {num_results}")
            elif actual_results < num_results and actual_results > 0:
                self.logger.info(f"Less results than expected: {actual_results} < {num_results}")
            elif actual_results == 0:
                self.logger.warning("No results found after setting results per page")
            
            self.logger.info(f"Successfully set results per page to {num_results} (actual results: {actual_results})")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting results per page: {str(e)}")
            return False

    def set_document_type_filter(self, doc_type="Base prospectus with Final terms"):
        try:
            # Wait for page load and form to be present
            if not self.wait_for_page_load():
                raise Exception("Page did not load properly")
            
            # Try multiple selectors with explicit waits
            selectors = [
                "select[name='searchRegisterForm.documentType']",
                "#documentType",
                "select.document-type-select",
                "select[name='documentType']"  # Added another possible selector
            ]
            
            dropdown = None
            for selector in selectors:
                try:
                    # Wait for element to be both present and visible
                    dropdown = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if dropdown and dropdown.is_displayed():
                        self.logger.info(f"Found dropdown using selector: {selector}")
                        break
                except:
                    continue
                    
            if not dropdown or not dropdown.is_displayed():
                # Take debug screenshot if dropdown not found
                if self.debug_mode:
                    self.take_screenshot('dropdown_not_found')
                    self.save_page_source('dropdown_not_found')
                raise Exception("Could not find document type dropdown")
                
            # Wait a moment before interacting with the dropdown
            time.sleep(1)
            
            # Get all options
            options = dropdown.find_elements(By.TAG_NAME, "option")
            if not options:
                raise Exception("No options found in dropdown")
                
            self.logger.info(f"Found {len(options)} options in dropdown")
            
            # Look for the target option
            target_option = None
            for option in options:
                option_text = option.text.strip()
                self.logger.debug(f"Found option: {option_text}")
                if option_text == doc_type:
                    target_option = option
                    break
                    
            if not target_option:
                raise Exception(f"Could not find option for document type: {doc_type}")
                
            # Click the option
            try:
                target_option.click()
                self.logger.info(f"Selected document type: {doc_type}")
            except Exception as e:
                raise Exception(f"Failed to click option: {str(e)}")
            
            # Wait for any updates after selection
            time.sleep(2)
            self.wait_for_page_load()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting document type filter: {str(e)}")
            return False
            
    @retry_on_failure(max_retries=3, base_delay=5)
    def search_company(self, company_name: str):
        """Searches for a company on the ESMA website."""
        self.logger.info(f"Searching for {company_name}...")
        try:
            # Navigate to the search page if not already there (or refresh)
            # Check current URL to avoid unnecessary navigation
            if self.base_url not in self.driver.current_url:
                self.driver.get(self.base_url)
                WebDriverWait(self.driver, self.timeout).until(EC.presence_of_element_located((By.ID, "searchForm"))
                )
                self.logger.info("Navigated to search page.")
            else:
                # Potentially refresh or just ensure the form is ready
                WebDriverWait(self.driver, self.timeout).until(EC.presence_of_element_located((By.ID, "searchForm"))
                )
                self.logger.info("Already on search page.")

            # Accept cookies if present
            self.accept_cookies()

            # Find and interact with the search input
            search_input_selectors = [
                (By.ID, "keywordField"),
                (By.NAME, "free_text"),
            ]
            search_input = None
            for by, value in search_input_selectors:
                try:
                    search_input = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((by, value))
                    )
                    self.logger.info(f"Found search input with selector: {by}={value}")
                    break
                except TimeoutException:
                    self.logger.debug(f"Search input not found with {by}={value}")
                    continue

            if not search_input:
                self.logger.error("Could not find clickable search input field.")
                self.save_page_source(f"error_search_input_not_found_{company_name}")
                return False

            search_input.clear()
            search_input.send_keys(company_name)
            self.logger.info(f"Entered company name: {company_name}")
            search_input.send_keys(Keys.RETURN)
            self.logger.info("Pressed Enter to search")

            # --- Wait for search results panel to be potentially visible ---
            # This doesn't guarantee content, just that the container exists and might show up
            self.logger.info("Waiting for results panel container presence...")
            WebDriverWait(self.driver, self.timeout).until(
                 EC.presence_of_element_located((By.ID, "resultsPanel"))
            )
            self.logger.info("Results panel container is present in DOM.")

            # --- Wait for EITHER results data OR 'no data' message to be VISIBLE ---
            self.logger.info("Waiting for results table content OR 'no data' message visibility...")
            try:
                WebDriverWait(self.driver, self.timeout * 3).until( # Increased timeout
                    EC.any_of(
                        # Option 1: Actual data rows are visible in the table
                        EC.visibility_of_element_located((By.CSS_SELECTOR, "#resultsTable tbody tr")),
                        # Option 2: The 'No data found' message is visible
                        EC.visibility_of_element_located((By.CSS_SELECTOR, "#noData:not([style*='display: none']) MuiBox-root"))
                    )
                )
                self.logger.info("Results table check complete (found rows or 'no data' message).")
            except TimeoutException:
                self.logger.error(f"Timeout waiting for results table content OR 'no data' message for {company_name}. Saving source.")
                self.save_page_source(f"error_timeout_results_visibility_{company_name}")
                return False # Failed to determine search outcome

            # --- Check which condition was met ---
            no_data_found = False
            try:
                no_data_element = self.driver.find_element(By.CSS_SELECTOR, "#noData:not([style*='display: none'])")
                if no_data_element.is_displayed(): # Double-check visibility
                    no_data_found = True
                    self.logger.warning(f"'No data found' message is visible for {company_name}.")
            except NoSuchElementException:
                self.logger.info("No 'no data' message visible. Assuming results exist.")

            # --- Process if results are expected ---
            if not no_data_found:
                self.logger.info("Results found, proceeding to set results per page.")
                # Ensure the results panel itself is visible before interacting with dropdown
                try:
                    WebDriverWait(self.driver, self.timeout).until(
                        EC.visibility_of_element_located((By.ID, "resultsPanel"))
                    )
                except TimeoutException:
                    self.logger.error("Results panel container found but did not become visible.")
                    self.save_page_source(f"error_results_panel_not_visible_{company_name}")
                    return False
                # Set results per page to maximum
                try:
                    results_per_page_selector = (By.ID, "tablePageSize")
                    select_element = WebDriverWait(self.driver, self.timeout).until(
                        EC.element_to_be_clickable(results_per_page_selector)
                    )
                    select = Select(select_element)
                    if select.options:
                        max_option_value = select.options[-1].get_attribute("value")
                        # Only change if not already selected
                        if select.first_selected_option.get_attribute("value") != max_option_value:
                            select.select_by_value(max_option_value)
                            self.logger.info(f"Set results per page to {max_option_value}")
                            # Wait for table to potentially reload after changing results per page
                            self.logger.info("Waiting for table content update after changing results per page...")
                            # --- Find the table element BEFORE checking staleness ---
                            try:
                                results_table = WebDriverWait(self.driver, self.timeout).until(
                                    EC.presence_of_element_located((By.ID, "resultsTable"))
                                )
                            except TimeoutException:
                                self.logger.error("Could not find results table element before checking staleness.")
                                # Handle this error appropriately - maybe return False or raise exception
                                return False # Indicate failure
                            # --- Now wait for the found table element to become stale ---
                            WebDriverWait(self.driver, self.timeout * 2).until(
                                EC.staleness_of(results_table) # Wait for old table to go stale
                            )
                            WebDriverWait(self.driver, self.timeout * 2).until(
                                EC.visibility_of_element_located((By.CSS_SELECTOR, "#resultsTable tbody tr")) # Wait for new rows
                            )
                            self.logger.info("Table updated after changing results per page.")
                        else:
                            self.logger.info(f"Results per page already set to maximum ({max_option_value}).")
                    else:
                        self.logger.warning("Results per page dropdown has no options.")

                except TimeoutException:
                    self.logger.error("Timeout waiting for results per page dropdown.")
                    self.save_page_source(f"error_results_per_page_timeout_{company_name}")
                    # Don't necessarily fail the search here, maybe default results are ok?
                    # Consider if this should return False
                except (NoSuchElementException, ElementNotInteractableException) as e:
                    self.logger.error(f"Error interacting with results per page dropdown: {e}")
                    self.save_page_source(f"error_results_per_page_{company_name}")
                    # Don't necessarily fail the search here

            self.logger.info(f"Search sequence for {company_name} completed.")
            self.save_page_source(f"after_search_{company_name}") # Save source after successful search steps
            return True # Indicate search sequence finished

        except TimeoutException as e:
            self.logger.error(f"Timeout occurred during search steps for {company_name}: {e}")
            self.save_page_source(f"error_timeout_{company_name}")
            return False
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during search for {company_name}: {e}", exc_info=True)
            self.save_page_source(f"error_unexpected_{company_name}")
            return False

    def process_results(self, company_name: str) -> List[Dict]:
        """
        Processes the search results page for a given company.
        Finds document links, checks against downloaded list, and downloads new ones.

        Args:
            company_name: The name of the company whose results are being processed.

        Returns:
            List[Dict]: List of processed documents with their details
        """
        self.logger.info(f"Processing search results for {company_name}")
        processed_docs = []
        processed_docs_count = 0
        original_tab = self.driver.current_window_handle

        # --- Wait for the results table to be present and potentially populated ---
        # Reuse the logic from search_company to check for data or 'no data'
        results_table_selector = (By.ID, "resultsTable")
        try:
            self.logger.info("Verifying results table presence and content...")
            WebDriverWait(self.driver, self.timeout * 2).until(
                EC.any_of(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, "#resultsTable tbody tr")),
                    EC.visibility_of_element_located((By.CSS_SELECTOR, "#noData:not([style*='display: none']) MuiBox-root"))
                )
            )
            # Check again for the 'no data' message
            try:
                no_data_element = self.driver.find_element(By.CSS_SELECTOR, "#noData:not([style*='display: none'])")
                if no_data_element.is_displayed():
                    self.logger.warning(f"No search results data found for {company_name} (#noData visible in process_results).")
                    return processed_docs  # Empty list, no data to process
            except NoSuchElementException:
                self.logger.info("Results table seems to contain data (no 'no data' message visible). Proceeding.")

            # Ensure the table element itself is located
            results_table = self.driver.find_element(*results_table_selector)

        except TimeoutException:
            self.logger.error(f"Timeout waiting for results table content OR 'no data' message in process_results for {company_name}.")
            self.save_page_source(f"error_process_results_timeout_{company_name}")
            return processed_docs  # Empty list, couldn't find results
        except NoSuchElementException:
            # This shouldn't happen if the wait above passed, but handle defensively
            self.logger.error(f"Results table element not found even after waiting, selector: {results_table_selector}")
            self.save_page_source(f"error_process_results_no_table_{company_name}")
            return processed_docs  # Empty list, couldn't find table

        # --- Find document links --- 
        document_links_elements = []
        try:
             # Wait briefly for links within the visible table using the updated selector
             document_link_selector = (By.CSS_SELECTOR, "#resultsTable tbody tr td:nth-child(10) a[href*='downloadFile']") # Updated selector
             WebDriverWait(results_table, 5).until(
                 EC.presence_of_all_elements_located(document_link_selector)
             )
             document_links_elements = results_table.find_elements(*document_link_selector)
        except TimeoutException:
             self.logger.warning(f"No PDF links found within the results table for {company_name} using selector '{document_link_selector[1]}'.")
             # This might be okay if there are results but no PDFs
        except Exception as e:
            self.logger.error(f"Error finding document links: {e}", exc_info=True)
            # Continue if possible, or return False depending on severity

        if not document_links_elements:
            self.logger.warning(f"No PDF document links found to process for {company_name}.")
            return processed_docs  # Empty list, no links is not an error in processing itself

        self.logger.info(f"Found {len(document_links_elements)} potential PDF document links.")

        for link_index, link_element in enumerate(document_links_elements):
            doc_url = None
            doc_id = f"unknown_doc_{link_index}" # Default ID
            doc_type = "unknown"
            approval_date = None
            
            try:
                # --- Re-find element to avoid staleness --- 
                # Re-locate using the updated selector
                current_links = self.driver.find_elements(By.CSS_SELECTOR, "#resultsTable tbody tr td:nth-child(10) a[href*='downloadFile']") # Updated selector
                if link_index >= len(current_links):
                    self.logger.warning(f"Link element at index {link_index} became stale or disappeared. Skipping.")
                    continue
                link_element = current_links[link_index]

                # --- Get URL --- 
                doc_url = link_element.get_attribute('href')
                # Check if URL is valid (contains downloadFile)
                if not doc_url or 'downloadFile' not in doc_url:
                     self.logger.warning(f"Skipping invalid link element (index {link_index}): No valid download href found. URL: {doc_url}")
                     continue

                # --- Determine Document Type and Create ID --- 
                try:
                    row = link_element.find_element(By.XPATH, "./ancestor::tr")
                    # Adjust column index based on actual table structure (needs inspection)
                    # Example: Assuming document type is in the 2nd column (index 1)
                    doc_type_td = row.find_elements(By.TAG_NAME, "td")[1] # *** ADJUST INDEX IF NEEDED ***
                    doc_type = doc_type_td.text.strip() if doc_type_td else "unknown"
                    doc_type_cleaned = re.sub(r'\\W+', '_', doc_type).strip('_') # Clean for filename
                    approval_date_td = row.find_elements(By.TAG_NAME, "td")[7] # *** ADJUST INDEX IF NEEDED ***
                    approval_date = approval_date_td.text.strip().replace('/','-') if approval_date_td else None
                    url_filename_part = os.path.basename(urlparse(doc_url).path) # Extract filename from URL path

                    # --- !! Filter for Document Type !! ---
                    if "final terms" not in doc_type.lower():
                        self.logger.info(f"Skipping document (Type: '{doc_type}', URL: {doc_url}) as it is not 'Final Terms'.")
                        continue # Skip to the next link
                    else:
                        self.logger.info(f"Found Final Terms document: {doc_type}")
                        # Map to standardized document type
                        doc_type = "final_terms"
                    # --- End Filter --- 

                    # Improved Doc ID: Company_Type_Date_FilenamePart
                    doc_id = f"{company_name}_{doc_type_cleaned}_{approval_date}_{url_filename_part}"
                    doc_id = doc_id[:200] # Limit length

                except (IndexError, StaleElementReferenceException) as e:
                    self.logger.warning(f"Could not determine document type/date for {doc_url} from row structure: {e}. Using basic ID and skipping type filter.")
                    url_filename = doc_url.split('/')[-1]
                    doc_id = f"{company_name}_{url_filename[:50]}" # Fallback ID
                    # Cannot filter reliably if type extraction failed, proceed cautiously

                # Use the correct method to check if downloaded
                if self.company_list_handler.is_document_downloaded(doc_id):
                    self.logger.info(f"Document already tracked (ID: {doc_id}). Skipping download.")
                    continue

                # --- Attempt Download --- 
                self.logger.info(f"Attempting to download document: {doc_id}")
                download_successful = False
                target_path = None
                
                try:
                    # Wait for link to be clickable
                    clickable_link = WebDriverWait(self.driver, self.timeout).until(
                         EC.element_to_be_clickable(link_element)
                    )
                    clickable_link.click()
                    self.logger.info(f"Clicked download link for {doc_id}")

                    # Wait for download to likely finish/file to appear in GLOBAL download dir
                    time.sleep(2) # Initial short wait
                    # Note: _find_latest_downloaded_file looks in self.download_dir (global)
                    actual_filename = self._find_latest_downloaded_file(url_filename_part, timeout_secs=self.download_wait_time)

                    if actual_filename:
                        self.logger.info(f"Download likely successful. Found raw file: {actual_filename}")
                        # Path to the file in the global download directory
                        downloaded_path = self.download_dir / actual_filename
                        
                        # Use our new file organization functionality
                        if downloaded_path.exists():
                            success, organized_path = self.organize_file(
                                downloaded_path, 
                                company_name, 
                                doc_type, 
                                approval_date
                            )
                            if success:
                                target_path = organized_path
                                download_successful = True
                                self.logger.info(f"Successfully organized file to: {target_path}")
                            else:
                                self.logger.warning(f"File downloaded but organization failed. Raw file: {downloaded_path}")
                                # Still consider successful if file exists
                                if downloaded_path.exists():
                                    download_successful = True
                                    target_path = downloaded_path
                        else:
                            self.logger.error(f"Verified file {actual_filename} disappeared before organization from {downloaded_path}.")
                    else:
                        self.logger.warning(f"Download verification failed for {doc_id}. File not found in {self.download_dir} after wait.")

                    # Close extra tabs if opened
                    if len(self.driver.window_handles) > 1:
                        all_handles = self.driver.window_handles
                        for handle in all_handles:
                            if handle != original_tab:
                                try:
                                    self.driver.switch_to.window(handle)
                                    time.sleep(1) # Allow tab to process if needed
                                    self.driver.close()
                                    self.logger.info(f"Closed extra tab ({handle}) opened for {doc_id}")
                                except Exception as close_tab_e:
                                    self.logger.warning(f"Could not close extra tab {handle}: {close_tab_e}")
                        # Switch back definitively
                        self.driver.switch_to.window(original_tab)
                        self.logger.info("Switched back to original tab.")

                except ElementClickInterceptedException:
                    self.logger.warning(f"Direct click intercepted for {doc_id}. Trying JavaScript click.")
                    try:
                        self.driver.execute_script("arguments[0].click();", link_element)
                        self.logger.info(f"Clicked download link for {doc_id} using JavaScript.")
                        # Repeat download verification and organization
                        time.sleep(2)
                        actual_filename = self._find_latest_downloaded_file(url_filename_part, timeout_secs=self.download_wait_time)
                        if actual_filename:
                            downloaded_path = self.download_dir / actual_filename
                            if downloaded_path.exists():
                                success, organized_path = self.organize_file(
                                    downloaded_path, 
                                    company_name, 
                                    doc_type, 
                                    approval_date
                                )
                                if success:
                                    target_path = organized_path
                                    download_successful = True
                                    self.logger.info(f"Successfully organized file (JS click) to: {target_path}")
                                else:
                                    self.logger.warning(f"File downloaded (JS click) but organization failed. Raw file: {downloaded_path}")
                                    # Still consider successful if file exists
                                    if downloaded_path.exists():
                                        download_successful = True
                                        target_path = downloaded_path
                            else:
                                self.logger.error(f"Verified file {actual_filename} (JS click) disappeared before organization.")
                        else:
                            self.logger.warning(f"Download verification failed (JS click) for {doc_id}. File not found in {self.download_dir}")

                        # Tab handling as above...
                        if len(self.driver.window_handles) > 1:
                            # ... close extra tabs ...
                            self.driver.switch_to.window(original_tab)

                    except Exception as js_e:
                        self.logger.error(f"Error clicking link with JavaScript for {doc_id}: {js_e}")
                except (TimeoutException, StaleElementReferenceException, NoSuchElementException) as click_wait_e:
                    self.logger.error(f"Error finding/clicking link (index {link_index}) for {doc_id}: {click_wait_e}")
                except Exception as click_e:
                    self.logger.error(f"Unexpected error during click/download for {doc_id}: {click_e}", exc_info=True)

                # --- Update tracking if download was successful --- 
                if download_successful:
                    # Use the correct method to mark as downloaded
                    self.company_list_handler.mark_document_as_downloaded(doc_id)
                    processed_docs_count += 1
                    self.random_delay() # Add delay between downloads
                    
                    # Add the document to the processed docs list
                    processed_docs.append({
                        'id': doc_id,
                        'type': doc_type,
                        'date': approval_date,
                        'url': doc_url,
                        'path': str(target_path)
                    })
                else:
                    self.logger.warning(f"Download for doc ID {doc_id} could not be confirmed.")
                    # Optionally add to a retry list here

            except StaleElementReferenceException:
                self.logger.warning(f"Link element at index {link_index} became stale during processing loop. Skipping.")
                continue # Skip to the next link
            except Exception as e:
                self.logger.error(f"Unexpected error processing link {link_index}: {e}", exc_info=True)
                continue
                
        self.logger.info(f"Processed {processed_docs_count} new documents for {company_name}")
        return processed_docs

    def _find_latest_downloaded_file(self, expected_filename_part: str, timeout_secs: int = 10) -> str | None:
        """
        Attempts to find the most recently modified file in the download directory
        that is NOT a temporary download file. It prioritizes files containing
        the expected_filename_part but falls back to the absolute latest file.
        Args:
            expected_filename_part: A substring expected to be in the downloaded filename (used for prioritization).
            timeout_secs: How long to wait for a stable file to appear.

        Returns:
            The filename if found, otherwise None.
        """
        self.logger.debug(f"Checking for downloaded file (expecting '{expected_filename_part}') for {timeout_secs}s...")
        start_time = time.time()
        last_found_stable_file = None

        while time.time() - start_time < timeout_secs:
            potential_files = []
            try:
                for f in os.listdir(self.download_dir):
                    if not f.endswith(('.tmp', '.crdownload', '.part')):
                        try:
                             f_path = os.path.join(self.download_dir, f)
                             if os.path.isfile(f_path):
                                 mtime = os.path.getmtime(f_path)
                                 # Consider files modified around the time the download was likely initiated
                                 if mtime >= start_time - 5 : # Check files modified recently
                                     potential_files.append((f, mtime))
                        except FileNotFoundError:
                             continue
                        except Exception as list_e:
                             self.logger.warning(f"Error checking file {f}: {list_e}")
                             continue

                if not potential_files:
                    time.sleep(0.5)
                    continue

                # Sort by modification time, newest first
                potential_files.sort(key=lambda x: x[1], reverse=True)

                # Check the newest files for stability and optional matching
                newest_file_checked = None
                for filename, mtime in potential_files:
                     newest_file_checked = filename # Keep track of the absolute newest
                     try:
                        full_path = os.path.join(self.download_dir, filename)
                        size1 = os.path.getsize(full_path)
                        time.sleep(0.2) # Wait briefly to check for size changes
                        size2 = os.path.getsize(full_path)
                        if size1 == size2 and size1 > 0: # File exists and size is stable
                             self.logger.info(f"Found stable file: {filename}. Checking match.")
                             last_found_stable_file = filename # Update the latest stable file found
                             # Prioritize if it matches the expected part
                             if expected_filename_part.lower() in filename.lower():
                                 self.logger.info(f"Stable file '{filename}' matches expected part '{expected_filename_part}'. Returning.")
                                 return filename
                             else:
                                 self.logger.info(f"Stable file '{filename}' found, but doesn't match expected part '{expected_filename_part}'. Will return this if no better match found.")
                                 # Don't return immediately, keep checking others in case a matching one appears
                        else:
                             self.logger.debug(f"File {filename} size changed ({size1} -> {size2}) or is zero. Still downloading?")
                     except FileNotFoundError:
                        continue # File might have been deleted
                     except Exception as size_e:
                         self.logger.warning(f"Error checking size stability for {filename}: {size_e}")

                # If we found a stable file but it didn't match, return it after checking all potential files in this iteration
                if last_found_stable_file:
                     self.logger.info(f"Returning latest stable file found: {last_found_stable_file} (may not match expected part)." )
                     return last_found_stable_file

            except FileNotFoundError:
                 self.logger.warning(f"Download directory '{self.download_dir}' not found.")
                 return None
            except Exception as e:
                self.logger.error(f"Error scanning download directory: {e}", exc_info=True)

            time.sleep(0.5) # Wait before the next scan

        # Timeout reached
        if last_found_stable_file:
             self.logger.warning(f"Timeout reached. Returning last known stable file: {last_found_stable_file} (may not match expected part)." )
             return last_found_stable_file
        else:
             self.logger.warning(f"Timeout reached. Could not find any stable downloaded file within {timeout_secs}s.")
             return None

    def accept_cookies(self):
        # Implementation of accept_cookies method
        pass

    def _find_element_sequentially(self, selectors, element_name):
        # Implementation of _find_element_sequentially method
        pass

    def process_all_eu_companies(self):
        """Process all EU companies from the company list"""
        try:
            # Get unprocessed companies
            companies = self.company_handler.get_unprocessed_companies()
            self.logger.info(f"Found {len(companies)} unprocessed EU companies")
            
            for company_info in companies:
                company_name = company_info['name']
                self.logger.info(f"Processing company: {company_name}")
                
                try:
                    # Search and process documents for this company
                    self.search_and_process(company_name)
                    
                    # Mark company as processed
                    self.company_handler.mark_company_as_processed(company_name)
                    
                    # Save progress after each company
                    self.company_handler.save_progress(str(self.output_dir))
                    
                except Exception as e:
                    self.logger.error(f"Error processing company {company_name}: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error in process_all_eu_companies: {e}")
            raise

    def _setup_browser(self):
        """Initialize and configure the Chrome browser"""
        try:
            chrome_options = uc.ChromeOptions()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-popup-blocking')
            chrome_options.add_argument('--disable-notifications')
            chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
            chrome_options.add_argument('--ignore-certificate-errors')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-first-run')
            chrome_options.add_argument('--no-default-browser-check')
            chrome_options.add_argument('--disable-background-networking')
            
            # Performance improvements
            chrome_options.add_argument('--disable-features=IsolateOrigins,site-per-process')
            chrome_options.add_argument('--disk-cache-size=0')
            chrome_options.add_argument('--media-cache-size=0')
            chrome_options.add_argument('--disable-application-cache')
            
            # Initialize the Chrome driver with increased timeouts
            self.driver = uc.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(120)  # Increase to 120 seconds
            self.wait = WebDriverWait(self.driver, 60)  # Increase to 60 seconds
            self.logger.info("Chrome driver initialized successfully")
            
            # More natural delays with increased times
            self.min_delay = 8  # Increased from 5
            self.max_delay = 15  # Increased from 10
            
            # More natural company delays with increased times
            self.min_company_delay = 20  # Increased from 15
            self.max_company_delay = 40  # Increased from 30
            
            # Initialize request tracking
            self.request_timestamps = []
            
        except Exception as e:
            self.logger.error(f"Error setting up browser: {str(e)}")
            raise

    def process_company_documents(self, company_name: str, doc_type: str) -> List[Dict]:
        """Process documents for a company with enhanced error handling"""
        try:
            self.check_session_health()
            self.requests_count += 1
            
            # Navigate to search page
            if not self.navigate_to_search():
                self.logger.error("Failed to navigate to search page")
                return []
            
            # Set document type filter
            if not self.set_document_type_filter(doc_type):
                self.logger.error(f"Failed to set document type filter for {doc_type}")
                return []
            
            # Search for company
            search_results = self.search_company(company_name)
            if not search_results:
                self.logger.warning(f"No results found for {company_name}")
                return []
            
            # Process each document
            processed_docs = []
            for result in search_results:
                try:
                    # Add random delay between document processing
                    self.random_delay()
                    
                    # Get document details
                    doc_details = self.get_document_details(result)
                    if not doc_details:
                        continue
                    
                    # Download document
                    doc_path = self.download_document(doc_details['url'], company_name)
                    if doc_path:
                        doc_details['path'] = doc_path
                        processed_docs.append(doc_details)
                        
                except Exception as e:
                    self.logger.error(f"Error processing document: {str(e)}")
                    continue
            
            return processed_docs
            
        except Exception as e:
            self.logger.error(f"Error in process_company_documents: {str(e)}")
            return []

    def get_document_details(self, result_element) -> Optional[Dict]:
        """Extract document details with enhanced error handling"""
        try:
            # Wait for element to be clickable
            result_element = self.wait_for_clickable_with_retry(result_element)
            
            # Extract document metadata
            doc_type = self.safe_get_text(result_element, '.document-type')
            date = self.safe_get_text(result_element, '.document-date')
            issuer = self.safe_get_text(result_element, '.issuer')
            
            # Get document URL
            url = self._find_pdf_in_viewer()
            if not url:
                self.logger.warning("Could not find PDF URL")
                return None
            
            return {
                'type': doc_type,
                'date': date,
                'issuer': issuer,
                'url': url
            }
            
        except Exception as e:
            self.logger.error(f"Error getting document details: {str(e)}")
            return None

    def safe_get_text(self, element, selector: str) -> str:
        """Safely extract text from an element with retry"""
        try:
            sub_element = self.wait_for_element_with_retry(selector)
            return sub_element.text.strip()
        except Exception as e:
            self.logger.warning(f"Error extracting text from {selector}: {str(e)}")
            return ""

    def wait_for_dropdown_interaction(self, max_attempts=3):
        """Wait for and interact with document type dropdown"""
        attempt = 0
        while attempt < max_attempts:
            try:
                # First click the criteria selector dropdown
                criteria_dropdown = WebDriverWait(self.driver, self.timeout).until(
                    EC.element_to_be_clickable((By.ID, "ID005"))
                )
                criteria_dropdown.click()
                time.sleep(1)

                # Select Document Type option
                doc_type_option = WebDriverWait(self.driver, self.timeout).until(
                    EC.element_to_be_clickable((By.ID, "document_type"))
                )
                doc_type_option.click()
                time.sleep(1)

                # Now find and interact with the document type dropdown
                dropdown = WebDriverWait(self.driver, self.timeout).until(
                    EC.presence_of_element_located((By.NAME, "document_type"))
                )
                
                # Get all options and their values
                options = dropdown.find_elements(By.TAG_NAME, "option")
                if not options:
                    raise Exception("No options found in dropdown")
                
                # Find the option with value "STDA"
                target_option = None
                for option in options:
                    if option.get_attribute("value") == "STDA":
                        target_option = option
                        break
                
                if not target_option:
                    raise Exception("Could not find STDA option in dropdown")
                
                # Select the option
                target_option.click()
                time.sleep(1)
                
                return True

            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed to interact with dropdown: {str(e)}")
                attempt += 1
                time.sleep(2)

        self.logger.error("Failed to interact with dropdown after multiple attempts")
        return False

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
            
            # Try checking filename first for efficiency
            filename = file_path.name.lower()
            for doc_type, indicators in type_indicators.items():
                for indicator in indicators:
                    if indicator.lower() in filename:
                        return doc_type
            
            # If could not determine from filename, try first few lines of content
            # We'll look at a small portion of the file to avoid loading everything
            try:
                # Read first 2KB of the file for analysis
                with open(file_path, 'rb') as f:
                    content = f.read(2048).decode('utf-8', errors='ignore').lower()
                
                for doc_type, indicators in type_indicators.items():
                    for indicator in indicators:
                        if indicator.lower() in content:
                            return doc_type
            except Exception as content_e:
                self.logger.debug(f"Could not analyze file content: {content_e}")
            
            return "unknown"
            
        except Exception as e:
            self.logger.error(f"Error detecting document type for {file_path}: {str(e)}")
            return "unknown"
    
    def extract_date(self, file_path: Path, fallback_date: str = None) -> str:
        """Attempt to extract date from PDF content or filename
        
        Args:
            file_path: Path to the PDF file
            fallback_date: Fallback date string to use if extraction fails
            
        Returns:
            str: Extracted date in YYYYMMDD format or current date if not found
        """
        try:
            # First try to extract from filename
            filename = file_path.name
            date_patterns = [
                r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})',  # YYYY-MM-DD or YYYYMMDD
                r'(\d{2})[-_]?(\d{2})[-_]?(\d{4})',  # DD-MM-YYYY or DDMMYYYY
                r'(\d{2})[-_]?(\d{2})[-_]?(\d{4})'  # DD-MMM-YYYY
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, filename)
                if match:
                    # Handle different date formats
                    if len(match.groups()) == 3:
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
            
            # If we have a fallback date, use it
            if fallback_date:
                # Clean and format the fallback date
                clean_date = re.sub(r'[^0-9]', '', fallback_date)
                if len(clean_date) >= 8:
                    return clean_date[:8]  # Use first 8 digits (YYYYMMDD)
            
            # Use current date if no date found
            today = datetime.now()
            return f"{today.year}{today.month:02d}{today.day:02d}"
            
        except Exception as e:
            self.logger.error(f"Error extracting date for {file_path}: {str(e)}")
            # Use current date if extraction fails
            today = datetime.now()
            return f"{today.year}{today.month:02d}{today.day:02d}"
    
    def organize_file(self, file_path: Path, company_name: str, doc_type_hint: str = None, 
                     date_hint: str = None) -> Tuple[bool, Path]:
        """Organize a downloaded PDF file
        
        Args:
            file_path: Path to the PDF file
            company_name: Name of the company this document belongs to
            doc_type_hint: Optional hint about document type
            date_hint: Optional hint about document date
            
        Returns:
            Tuple[bool, Path]: (Success flag, New file path if moved)
        """
        try:
            # Skip if not a PDF
            if file_path.suffix.lower() != '.pdf':
                self.logger.warning(f"Skipping non-PDF file: {file_path}")
                return False, file_path
                
            # Calculate file hash for deduplication
            file_hash = self.get_file_hash(file_path)
            if not file_hash:
                self.logger.error(f"Failed to calculate hash for: {file_path}")
                return False, file_path
                
            # Check if already processed (deduplication)
            if file_hash in self.processed_files:
                self.logger.info(f"Skipping duplicate file: {file_path}")
                return False, file_path
            self.processed_files.add(file_hash)
            
            # Use hints if provided, otherwise detect from file
            if doc_type_hint:
                doc_type = doc_type_hint
            else:
                doc_type = self.detect_document_type(file_path)
            
            # Extract date
            if date_hint:
                date = date_hint
            else:
                date = self.extract_date(file_path)
            
            # Create target directory
            clean_company_name = re.sub(r'[<>:"/\\|?*]', '_', company_name)
            # Replace spaces with underscores for consistency
            clean_company_name = clean_company_name.replace(' ', '_')
            company_dir = self.download_dir / clean_company_name
            
            # Create new filename
            new_filename = f"{doc_type}_{date}_{file_hash[:8]}.pdf"
            target_path = company_dir / new_filename
            
            # Create company directory if it doesn't exist
            company_dir.mkdir(parents=True, exist_ok=True)
            
            # Check if target already exists (deduplication)
            if target_path.exists():
                target_hash = self.get_file_hash(target_path)
                if file_hash == target_hash:
                    self.logger.info(f"File already exists at target location: {target_path}")
                    if str(file_path) != str(target_path):  # Not the same file
                        self.logger.info(f"Will remove duplicate: {file_path}")
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            self.logger.warning(f"Failed to remove duplicate: {e}")
                    return True, target_path
            
            # Move the file
            self.logger.info(f"Moving: {file_path} -> {target_path}")
            try:
                shutil.move(file_path, target_path)
                
                # Record in company stats through company_list_handler
                try:
                    # Create document hash for tracking
                    doc_info = {
                        'issuer': company_name,
                        'document_type': doc_type,
                        'date': date
                    }
                    doc_hash = self.company_list_handler.get_document_hash(doc_info)
                    self.company_list_handler.add_downloaded_document(doc_hash, company_name, doc_type, date)
                except Exception as stats_e:
                    self.logger.warning(f"Failed to update document stats: {stats_e}")
                
                return True, target_path
            except Exception as move_e:
                self.logger.error(f"Failed to move file: {move_e}")
                return False, file_path
            
        except Exception as e:
            self.logger.error(f"Error organizing file {file_path}: {str(e)}")
            return False, file_path

    def download_document(self, url: str, company_name: str, doc_type: str = None, date: str = None) -> Optional[Path]:
        """Download a document and organize it
        
        Args:
            url: URL of the document to download
            company_name: Name of the company this document belongs to
            doc_type: Document type if known
            date: Document date if known
            
        Returns:
            Optional[Path]: Path to the organized document if successful, None otherwise
        """
        try:
            self.logger.info(f"Downloading document from {url} for {company_name}")
            
            # Clean company name for temporary folder
            clean_company_name = re.sub(r'[<>:"/\\|?*]', '_', company_name).strip()
            # Replace spaces with underscores for consistency
            clean_company_name = clean_company_name.replace(' ', '_')
            
            # Create temp download folder
            temp_download_dir = self.download_dir / "temp_downloads"
            temp_download_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate a temporary filename
            timestamp = int(time.time())
            url_filename = os.path.basename(urlparse(url).path)
            temp_filename = f"{clean_company_name}_{timestamp}_{url_filename}.pdf"
            temp_path = temp_download_dir / temp_filename
            
            # Download the file using requests
            try:
                response = requests.get(url, stream=True, timeout=30)
                response.raise_for_status()
                
                with open(temp_path, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
                
                self.logger.info(f"Successfully downloaded document to {temp_path}")
                
                # Now organize the file
                success, final_path = self.organize_file(temp_path, company_name, doc_type, date)
                
                if success:
                    self.logger.info(f"Successfully organized document to {final_path}")
                    return final_path
                else:
                    self.logger.warning(f"Failed to organize document, using temporary path: {temp_path}")
                    return temp_path
                    
            except requests.RequestException as e:
                self.logger.error(f"Request error downloading document: {e}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error downloading document: {e}")
            return None

    def search_and_process(self, company_name: str, company_info: Dict = None) -> List[Dict]:
        """Search for a company and process all documents
        
        This is the main method to call when searching for documents for a company.
        It combines the search, document processing, and file organization.
        
        Args:
            company_name: Name of the company to search for
            company_info: Optional additional company information
            
        Returns:
            List[Dict]: List of processed documents
        """
        results = []
        
        try:
            # Perform the search
            self.logger.info(f"Searching for documents for company: {company_name}")
            search_success = self.search_company(company_name)
            
            if not search_success:
                self.logger.warning(f"Search for {company_name} failed or no results found")
                return results
            
            # Process the results
            self.logger.info(f"Processing search results for {company_name}")
            results = self.process_results(company_name)
            
            if results:
                self.logger.info(f"Found and processed {len(results)} documents for {company_name}")
            else:
                self.logger.info(f"No documents processed for {company_name}")
            return results
            
        except Exception as e:
            self.logger.error(f"Error in search_and_process for {company_name}: {e}")
            return results