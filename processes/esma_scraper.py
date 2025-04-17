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

# Constants for selectors (Example - Adjust based on actual website inspection)
SEARCH_INPUT_ID = "keywordField" # Corrected ID based on inspection
SEARCH_BUTTON_ID = "searchSolrButton" # Corrected ID based on inspection
RESULTS_CONTAINER_ID = "resultsTable" # ID of the DIV containing the results table
RESULTS_TABLE_ID = "T01" # ID of the TABLE element itself (inside the container)
COOKIE_ACCEPT_BUTTON_SELECTOR = "//button[contains(text(), 'Accept') or contains(text(), 'Agree')]" # Example XPath
RESULTS_PER_PAGE_DROPDOWN_ID = "tablePageSize" # Corrected ID based on inspection

# --- Decorator Definition (Moved Outside Class) --- 
def retry_on_failure(max_retries=3, base_delay=5, 
                     retry_exceptions=(TimeoutException, StaleElementReferenceException, ElementNotInteractableException)):
    """Enhanced retry decorator with exponential backoff and specific exception handling."""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(self, *args, **kwargs)
                except retry_exceptions as e:
                    last_exception = e
                    func_name = func.__name__
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # Exponential backoff
                        delay += random.uniform(0, base_delay * 0.5) # Add jitter
                        # Access logger through self
                        self.logger.warning(f"Attempt {attempt + 1}/{max_retries} for '{func_name}' failed: {type(e).__name__}. Retrying in {delay:.2f} seconds...")
                        
                        # Debugging context on retry (Access debug_mode and helpers through self)
                        if self.debug_mode:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            screenshot_name = f"retry_{func_name}_attempt{attempt+1}_{timestamp}.png"
                            pagesource_name = f"retry_{func_name}_attempt{attempt+1}_{timestamp}.html"
                            try:
                                self.take_screenshot(screenshot_name)
                                self.save_page_source(pagesource_name)
                            except Exception as dbg_e:
                                self.logger.error(f"Failed to capture debug info during retry: {dbg_e}")

                        time.sleep(delay)
                        # Optional: Add recovery steps like refreshing the page or checking session
                        # self.driver.refresh() 
                        # self.check_session_health()
                    else:
                        self.logger.error(f"All {max_retries} attempts for '{func_name}' failed. Last error: {type(e).__name__} - {str(e)}", exc_info=False)
                        # Capture final failure state
                        if self.debug_mode:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            screenshot_name = f"final_fail_{func_name}_{timestamp}.png"
                            pagesource_name = f"final_fail_{func_name}_{timestamp}.html"
                            try:
                                self.take_screenshot(screenshot_name)
                                self.save_page_source(pagesource_name)
                            except Exception as dbg_e:
                                self.logger.error(f"Failed to capture debug info on final failure: {dbg_e}")
                        raise last_exception # Re-raise the last captured exception
                except Exception as e:
                    # Handle unexpected exceptions
                    func_name = func.__name__
                    self.logger.error(f"Unexpected error in '{func_name}': {type(e).__name__} - {str(e)}", exc_info=True)
                    # Capture state for unexpected errors
                    if self.debug_mode:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        screenshot_name = f"unexpected_fail_{func_name}_{timestamp}.png"
                        pagesource_name = f"unexpected_fail_{func_name}_{timestamp}.html"
                        try:
                            self.take_screenshot(screenshot_name)
                            self.save_page_source(pagesource_name)
                        except Exception as dbg_e:
                            self.logger.error(f"Failed to capture debug info on unexpected failure: {dbg_e}")
                    raise # Re-raise the unexpected exception
        return wrapper
    return decorator
# --- End Decorator Definition ---

class ESMAScraper:
    def __init__(self, download_dir=None, debug_mode=True, headless=True):
        """Initialize the ESMA scraper"""
        self.logger = logging.getLogger(__name__)
        
        # Set base directory for downloads
        self.base_dir = Path("data/downloads")
        
        # Set download directory
        if download_dir:
            self.download_dir = Path(download_dir)
        else:
            self.download_dir = self.base_dir
            
        # Create download directory if it doesn't exist
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize document hashes database
        self.document_hashes_file = Path("data/document_hashes.json")
        self.document_hashes_file.parent.mkdir(parents=True, exist_ok=True)
        self.document_hashes = self._load_document_hashes()
        
        # Initialize context for deduplication
        self.current_company = None
        # self.current_doc_type = None # Potentially unused
        
        # Set debug mode
        self.debug_mode = debug_mode
        
        # Setup debug directories
        self.screenshots_dir = Path("logs/screenshots")
        self.page_sources_dir = Path("logs/page_sources")
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.page_sources_dir.mkdir(parents=True, exist_ok=True)
        
        # Base configuration
        self.base_url = "https://registers.esma.europa.eu/publication/searchRegister?core=esma_registers_priii_documents"
        self.headless = headless
        self.fuzzy_match_threshold = 80
        # self.min_similarity = 80 # Potentially unused, replaced by fuzzy_match_threshold?
        self.company_list_handler = CompanyListHandler()
        
        # Session configuration
        self.session_start_time = time.time()
        self.requests_count = 0
        self.max_session_duration = 3600  # 1 hour
        self.max_requests_per_session = 100
        self.min_delay = 1
        self.max_delay = 3
        self.default_wait_timeout = 40 # Increased default wait timeout from 20
        self.download_wait_time = 60 # Increased default download wait time
        
        # Initialize driver
        self.driver = None
        self.wait = None # Initialize wait object here
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
                    # Check if running in a CI/headless environment
                    # if os.environ.get('CI') or not sys.stdout.isatty(): # Example check
                    self.logger.info("Running in headless mode.")
                    options.add_argument('--headless=new') # Use the new headless mode
                else:
                    self.logger.info("Running in non-headless (headed) mode.")

                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-gpu')
                options.add_argument('--disable-extensions')
                # options.add_argument('--disable-infobars') # Deprecated
                options.add_argument('--disable-notifications')
                options.add_argument('--disable-popup-blocking')
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_argument('--start-maximized') # May not work in headless
                options.add_argument('--window-size=1920,1080') # Set a default window size

                # User agent rotation (optional, example)
                # user_agents = [...] # List of user agents
                # options.add_argument(f"user-agent={random.choice(user_agents)}")
                
                # Set up download preferences
                prefs = {
                    "download.default_directory": str(self.download_dir.absolute()),
                    "download.prompt_for_download": False,
                    "download.directory_upgrade": True,
                    "safebrowsing.enabled": True,
                    "plugins.always_open_pdf_externally": True # Try to force download PDFs
                }
                options.add_experimental_option("prefs", prefs)
                
                # Initialize the undetected Chrome driver
                self.logger.info(f"Initializing Chrome driver (Attempt {attempt + 1}/{max_retries})...")
                # Use driver_executable_path if uc needs it explicitly
                # driver_executable_path = shutil.which('chromedriver') # Or provide path
                self.driver = uc.Chrome(options=options) #, driver_executable_path=driver_executable_path) 
                
                # Set timeouts
                self.driver.set_page_load_timeout(60) # Increased page load timeout
                self.driver.set_script_timeout(30)
                
                # Initialize WebDriverWait
                self.wait = WebDriverWait(self.driver, self.default_wait_timeout) 
                
                self.logger.info("Chrome driver initialized successfully")
                return True
                
            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1} failed to initialize Chrome driver: {str(e)}", exc_info=True)
                # Cleanup driver if partially initialized
                if self.driver:
                    try:
                        self.driver.quit()
                    except Exception: pass # Ignore errors during cleanup
                    self.driver = None
                    self.wait = None

                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    self.logger.error("All attempts to initialize Chrome driver failed.")
                    raise # Re-raise the last exception

    def close(self):
        """Close the browser and clean up resources."""
        if hasattr(self, 'driver') and self.driver:
            try:
                self.logger.info("Closing Chrome driver...")
                self.driver.quit()
                self.logger.info("Chrome driver closed.")
            except Exception as e:
                self.logger.error(f"Error closing browser: {e}", exc_info=True)
            finally:
                self.driver = None
                self.wait = None

    def __del__(self):
        """Ensure browser is closed when object is destroyed."""
        self.close()

    def _load_document_hashes(self):
        """Load the document hashes from the JSON file."""
        if not self.document_hashes_file.exists():
            self.logger.warning(f"Document hashes file not found: {self.document_hashes_file}")
            return {}
        try:
            with open(self.document_hashes_file, 'r') as f:
                data = json.load(f)
                self.logger.info(f"Loaded {len(data)} document hashes from {self.document_hashes_file}")
                return data
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding JSON from {self.document_hashes_file}: {e}")
            # Optionally, create a backup or handle the corrupted file
            return {}
        except Exception as e:
            self.logger.error(f"Error loading document hashes: {str(e)}", exc_info=True)
            return {}

    def _save_document_hashes(self):
        """Save the document hashes to the JSON file."""
        try:
            with open(self.document_hashes_file, 'w') as f:
                json.dump(self.document_hashes, f, indent=2)
            self.logger.debug(f"Saved {len(self.document_hashes)} document hashes to {self.document_hashes_file}")
        except Exception as e:
            self.logger.error(f"Error saving document hashes: {str(e)}", exc_info=True)

    def random_delay(self, min_seconds=None, max_seconds=None):
        """Add a random delay. Uses instance defaults if not provided."""
        min_s = min_seconds if min_seconds is not None else self.min_delay
        max_s = max_seconds if max_seconds is not None else self.max_delay
        delay = random.uniform(min_s, max_s)
        self.logger.debug(f"Applying random delay: {delay:.2f} seconds")
        time.sleep(delay)

    def check_session_health(self):
        """Check if we need to refresh the session"""
        current_time = time.time()
        session_duration = current_time - self.session_start_time
        
        if (session_duration > self.max_session_duration or 
            self.requests_count >= self.max_requests_per_session):
            self.logger.info(f"Session limits reached (Duration: {session_duration:.0f}s, Requests: {self.requests_count}). Refreshing...")
            self.refresh_session()
            return True # Indicate session was refreshed
        # Optional: Check if browser is still responsive
        try:
            _ = self.driver.current_url
        except Exception as e:
            self.logger.warning(f"Browser seems unresponsive ({e}). Refreshing session...")
            self.refresh_session()
            return True
        return False

    def refresh_session(self):
        """Refresh the browser session"""
        self.close() # Close existing driver first
        try:
            self.setup_driver() # Re-initialize driver and wait object
            self.session_start_time = time.time()
            self.requests_count = 0
            self.logger.info("Session refreshed successfully")
        except Exception as e:
            self.logger.error(f"Error refreshing session: {str(e)}", exc_info=True)
            # This is critical, re-raise to stop the process if session cannot be refreshed
            raise

    @retry_on_failure() # Apply retry decorator
    def navigate_to_search(self):
        """Navigate to the ESMA search page and wait for it to load."""
        self.logger.info(f"Navigating to ESMA search page: {self.base_url}")
        try:
            self.driver.get(self.base_url)
            self.requests_count += 1
            if not self.wait_for_page_load():
                raise TimeoutException("Page did not reach ready state after navigation.")
            self.logger.info("Successfully navigated to search page.")
            # Accept cookies immediately after navigation if the banner appears
            self.accept_cookies()
            return True
        except Exception as e:
            self.logger.error(f"Fatal error navigating to search page: {e}", exc_info=True)
            # Capture state on fatal navigation error
            if self.debug_mode:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.take_screenshot(f"fatal_nav_error_{timestamp}.png")
                self.save_page_source(f"fatal_nav_error_{timestamp}.html")
            raise # Re-raise after logging and capturing state

    @retry_on_failure() # Retry might be needed here too
    def set_results_per_page(self, num_results=100):
        """Set the number of results per page in the search."""
        self.logger.info(f"Attempting to set results per page to {num_results}...")
        dropdown_id = RESULTS_PER_PAGE_DROPDOWN_ID # Use constant
        option_value = str(num_results)
        
        try:
            # Wait for the dropdown to be present AND visible with a shorter timeout
            short_wait = WebDriverWait(self.driver, 10) # Use shorter timeout for non-critical element
            self.logger.debug(f"Waiting for dropdown with ID '{dropdown_id}' to be present and visible...")
            dropdown_element = short_wait.until(
                EC.visibility_of_element_located((By.ID, dropdown_id)), # Changed to visibility_of_element_located
                message=f"Dropdown element with ID '{dropdown_id}' not found or not visible."
            )
            self.logger.debug("Dropdown element found and visible.")
            
            # Scroll into view (optional but can help)
            try:
                self.driver.execute_script("arguments[0].scrollIntoView(true);", dropdown_element)
                self.logger.debug("Scrolled dropdown into view.")
                time.sleep(0.5) # Brief pause after scroll
            except Exception as scroll_err:
                self.logger.warning(f"Could not scroll dropdown into view: {scroll_err}")

            # Use Selenium's Select class for dropdown interaction
            select = Select(dropdown_element)
            
            # Check if the desired option is already selected
            current_value = select.first_selected_option.get_attribute("value")
            if current_value == option_value:
                self.logger.info(f"Results per page already set to {num_results}.")
                return True

            self.logger.debug(f"Selecting option with value '{option_value}'...")
            # Wait for the specific option to be present within the select element
            short_wait.until(
                lambda d: dropdown_element.find_element(By.CSS_SELECTOR, f"option[value='{option_value}']"),
                message=f"Option '{option_value}' not found within dropdown '{dropdown_id}'."
            )

            # Select the option
            select.select_by_value(option_value)
            self.logger.info(f"Selected '{option_value}' from dropdown '{dropdown_id}'.")

            # Add a brief pause AFTER interaction for JS/AJAX to potentially trigger
            self.random_delay(0.5, 1.0) 

            # Verification: Wait for results container to be present again and contain data
            self.logger.debug("Waiting for results table content to reload...")
            short_wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, f"#{RESULTS_CONTAINER_ID} tbody tr")),
                message=f"Results table content (first row) did not appear in {RESULTS_CONTAINER_ID} after setting page size."
            )
            self.logger.info(f"Successfully set results per page to {num_results}.")
            return True
            
        except (TimeoutException, NoSuchElementException, ElementNotInteractableException) as e:
            self.logger.warning(f"Could not set results per page to {num_results}: {type(e).__name__} - {str(e)}")
            if self.debug_mode:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.take_screenshot(f"warning_set_results_{num_results}_{timestamp}.png")
                self.save_page_source(f"warning_set_results_{num_results}_{timestamp}.html")
            self.logger.info("Continuing with default results per page.")
            return True  # Continue with default results per page
        except Exception as e:
            self.logger.error(f"Unexpected error setting results per page: {e}", exc_info=True)
            if self.debug_mode:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.take_screenshot(f"unexpected_error_set_results_{num_results}_{timestamp}.png")
                self.save_page_source(f"unexpected_error_set_results_{num_results}_{timestamp}.html")
            return True  # Continue with default results per page

    @retry_on_failure() # Apply the defined decorator
    def search_company(self, company_name: str):
        """Search for a specific company name on the ESMA website."""
        self.logger.info(f"Searching for company: '{company_name}'")
        # Check for session health before critical interaction
        if self.check_session_health():
            # Session was refreshed, ensure we are on the right page
            self.navigate_to_search() 
            # May need to re-apply settings like results per page if session was refreshed
            # self.set_results_per_page() 

        search_input_locator = (By.ID, SEARCH_INPUT_ID) # Example ID
        search_button_locator = (By.ID, SEARCH_BUTTON_ID) # Example ID
        results_table_locator = (By.CSS_SELECTOR, RESULTS_CONTAINER_ID) # Example ID

        try:
            # 1. Find and clear the search input field
            self.logger.debug(f"Waiting for search input field '{search_input_locator}'...")
            search_input = self.wait.until(
                EC.element_to_be_clickable(search_input_locator),
                message=f"Search input '{search_input_locator}' not clickable."
            )
            self.logger.debug("Search input found. Clearing and sending keys...")
            search_input.clear()
            search_input.send_keys(company_name)
            # Add Enter key press as an alternative/additional trigger
            # search_input.send_keys(Keys.RETURN)
            self.logger.debug(f"Entered '{company_name}' into search field.")
            
            # Brief random delay before clicking search
            self.random_delay(0.5, 1.5)

            # 2. Find and click the search button
            self.logger.debug(f"Waiting for search button '{search_button_locator}'...")
            search_button = self.wait.until(
                EC.element_to_be_clickable(search_button_locator),
                message=f"Search button '{search_button_locator}' not clickable."
            )
            self.logger.debug("Search button found. Clicking...")
            search_button.click()
            self.requests_count += 1 # Count actions that trigger server requests
            self.logger.info(f"Clicked search button for '{company_name}'.")

            # 3. Wait for search results to load (or indicate no results)
            self.logger.debug("Waiting for search results table content to load...")
            # Option A: Wait for the results table container (Original - timed out)
            # self.wait.until(
            #     EC.presence_of_element_located(results_table_locator),
            #     message="Results table did not appear after search."
            # )
            # Option B: Wait for the first row within the table body (More robust)
            results_first_row_locator = (By.CSS_SELECTOR, f"#{RESULTS_CONTAINER_ID} tbody tr")
            self.wait.until(
                EC.presence_of_element_located(results_first_row_locator),
                message=f"Results table content (first row) using selector '{results_first_row_locator}' did not appear after search."
            )
            self.logger.debug("Results table content (first row) detected.")

            # Option C: Wait for either results table OR a 'no results' message (More complex)
            # ... (keep commented out)
                
            self.logger.info(f"Search results loaded for '{company_name}'.")
            return True # Indicate search completed, results (or empty table) are present

        except (TimeoutException, NoSuchElementException, ElementClickInterceptedException, ElementNotInteractableException, StaleElementReferenceException) as e:
            self.logger.error(f"Error during search for '{company_name}': {type(e).__name__} - {str(e)}")
            if self.debug_mode:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.take_screenshot(f"error_search_{company_name[:20]}_{timestamp}.png")
                self.save_page_source(f"error_search_{company_name[:20]}_{timestamp}.html")
            # Consider if returning False or raising the exception is better here
            # Returning False might allow processing to continue with the next company
            return False # Indicate search failed
        except Exception as e:
            self.logger.error(f"Unexpected error during search for '{company_name}': {e}", exc_info=True)
            if self.debug_mode:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.take_screenshot(f"unexpected_error_search_{company_name[:20]}_{timestamp}.png")
                self.save_page_source(f"unexpected_error_search_{company_name[:20]}_{timestamp}.html")
            raise # Re-raise unexpected errors

    def process_results(self, company_name: str) -> List[Dict]:
        """Process search results, handling pagination and extracting document details."""
        self.logger.info(f"Processing results for company: {company_name}")
        all_documents = []
        page_num = 1
        processed_urls = set() # Track URLs processed in this run to avoid duplicates within pagination
        
        # More targeted selectors
        results_table_locator = (By.ID, RESULTS_TABLE_ID) # Use the actual table ID
        results_container_locator = (By.ID, RESULTS_CONTAINER_ID) # Container ID
        result_row_selector = "tbody tr" # Example CSS selector for result rows
        next_page_link_text = "Next" # Example link text for pagination

        while True:
            self.logger.info(f"Processing page {page_num} for '{company_name}'...")
            self.random_delay(1, 2) # Delay between page loads

            try:
                # First check if the container exists
                self.logger.debug("Checking for results container...")
                results_container = self.wait.until(
                    EC.presence_of_element_located(results_container_locator),
                    message=f"Results container not found on page {page_num}."
                )
                
                # Then check if the table exists within the container
                self.logger.debug("Looking for results table within container...")
                try:
                    # Using a shorter timeout to quickly check for the table
                    short_wait = WebDriverWait(self.driver, 5)
                    results_table = short_wait.until(
                        EC.presence_of_element_located(results_table_locator),
                        message=f"Results table not found within container on page {page_num}."
                    )
                    self.logger.debug("Results table found.")
                except TimeoutException:
                    # If the table element isn't found, check for any rows directly in the container
                    self.logger.debug("Table element not found. Looking for rows directly in container...")
                    results_table = results_container
                    
                # Try to find rows either in the results table or container
                # Use find_elements to avoid error if no rows exist
                result_rows = results_table.find_elements(By.CSS_SELECTOR, result_row_selector)
                
                if not result_rows:
                    self.logger.info(f"No result rows found on page {page_num}. Assuming end of results or no matching results.")
                    # Try to check for an explicit "No results" message
                    try:
                        no_results_selector = (By.CSS_SELECTOR, ".no-results, .empty-results")
                        no_results_element = short_wait.until(
                            EC.presence_of_element_located(no_results_selector),
                            message="No 'No results' message found."
                        )
                        self.logger.info(f"Found 'No results' message: {no_results_element.text}")
                    except TimeoutException:
                        self.logger.debug("No explicit 'No results' message found.")
                    
                    break # Exit pagination loop if no rows found
                
                # Capture the state of the table before processing rows
                table_html_before = results_table.get_attribute('outerHTML')
                self.logger.info(f"Found {len(result_rows)} result rows on page {page_num}.")

                # --- Processing Rows --- 
                for index, row in enumerate(result_rows):
                    row_data = None
                    try:
                        # Extract details from the row
                        row_data = self.get_document_details(row)
                        if row_data and row_data.get('url'):
                            doc_url = row_data['url']
                            if doc_url not in processed_urls:
                                processed_urls.add(doc_url)
                                all_documents.append(row_data)
                                self.logger.debug(f"Processed result {index+1} on page {page_num}: {row_data.get('issuer_name', '?')} - {row_data.get('doc_type', '?')}")
                            else:
                                self.logger.debug(f"Skipping duplicate URL on page {page_num}: {doc_url}")
                        else:
                            self.logger.warning(f"Row {index+1} on page {page_num} yielded no valid document data.")
                    except StaleElementReferenceException:
                        self.logger.warning(f"Row {index+1} on page {page_num} became stale during processing. Re-finding table and retrying page.")
                        # Re-find the table and break inner loop to retry the page processing
                        self.wait.until(EC.presence_of_element_located(results_table_locator), "Results table disappeared after stale element.")
                        break # Break the inner row processing loop
                    except (NoSuchElementException, TimeoutException) as e:
                        self.logger.error(f"Error processing row {index+1} on page {page_num}: {type(e).__name__} - {str(e)}")
                        if self.debug_mode:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            # Try capturing screenshot relative to the row if possible, else full page
                            try: row.screenshot(str(self.screenshots_dir / f"error_proc_row_{page_num}_{index+1}_{timestamp}.png"))
                            except Exception: self.take_screenshot(f"error_proc_row_{page_num}_{index+1}_{timestamp}.png")
                            # Saving page source might be more useful here
                            self.save_page_source(f"error_proc_row_{page_num}_{index+1}_{timestamp}.html")
                        continue # Skip to the next row
                    except Exception as e:
                         self.logger.error(f"Unexpected error processing row {index+1} on page {page_num}: {e}", exc_info=True)
                         if self.debug_mode:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            try:
                                result_element.screenshot(str(self.screenshots_dir / f"unexpected_error_proc_row_{page_num}_{index+1}_{timestamp}.png"))
                            except Exception:
                                self.take_screenshot(f"unexpected_error_proc_row_{page_num}_{index+1}_{timestamp}.png")
                         continue # Skip to the next row
                    else:
                        # This 'else' block executes if the 'for' loop completed without a 'break'
                        # Proceed to check for pagination
                        pass
               
                # --- Pagination --- 
                try:
                    self.logger.debug("Checking for 'Next' page link...")
                    # Wait for the 'Next' link to be potentially clickable
                    next_button = self.wait.until(
                        EC.element_to_be_clickable((By.LINK_TEXT, next_page_link_text)),
                        message="'Next' page link not found or not clickable."
                    )
                    self.logger.info(f"Found 'Next' page link. Clicking page {page_num + 1}...")
                    
                    # Scroll into view before clicking (optional but can help)
                    # self.driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                    # time.sleep(0.5) # Small pause before click

                    next_button.click()
                    self.requests_count += 1
                    page_num += 1

                    # Wait for the results table to become stale or reload
                    self.logger.debug("Waiting for results table to update after pagination...")
                    try:
                        # Wait for the previous table instance to become stale
                        WebDriverWait(self.driver, self.default_wait_timeout).until(EC.staleness_of(results_table))
                        self.logger.debug("Previous results table became stale.")
                    except TimeoutException:
                        # Fallback: Check if the table HTML has changed significantly
                        self.logger.warning("Old table did not become stale. Checking for HTML change...")
                        current_table_html = self.driver.find_element(*results_table_locator).get_attribute('outerHTML')
                        if current_table_html == table_html_before:
                            self.logger.error("Pagination clicked, but results table content did not change significantly.")
                            # Consider breaking or further investigation
                            break 
                        else:
                            self.logger.debug("Results table HTML has changed.")
                    # Wait for the *new* results table to be present (redundant if staleness worked, but safe)
                    self.wait.until(EC.presence_of_element_located(results_table_locator), "New results table did not appear after pagination.")

                except (TimeoutException, NoSuchElementException):
                    # If 'Next' link is not found or clickable, assume it's the last page
                    self.logger.info("No 'Next' page link found or clickable. Assuming end of results.")
                    break # Exit the pagination loop
                except ElementClickInterceptedException:
                    self.logger.warning("Clicking 'Next' button intercepted. Trying JavaScript click...")
                    try:
                        # Attempt JavaScript click as fallback
                        next_button_js = self.driver.find_element(By.LINK_TEXT, next_page_link_text)
                        self.driver.execute_script("arguments[0].click();", next_button_js)
                        self.requests_count += 1
                        page_num += 1
                        # Add wait for staleness/reload as above
                        self.logger.debug("Waiting for results table to update after JS pagination click...")
                        WebDriverWait(self.driver, self.default_wait_timeout).until(EC.staleness_of(results_table))
                        self.wait.until(EC.presence_of_element_located(results_table_locator))
                    except Exception as js_e:
                        self.logger.error(f"JavaScript click also failed for 'Next' button: {js_e}")
                        if self.debug_mode:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            self.take_screenshot(f"error_pagination_click_{page_num}_{timestamp}.png")
                            self.save_page_source(f"error_pagination_click_{page_num}_{timestamp}.html")
                        break # Exit loop if JS click fails
            except StaleElementReferenceException:
                     self.logger.warning(f"'Next' button became stale on page {page_num}. Retrying page processing.")
                     # The loop will naturally retry finding the button after re-finding the table
                     continue # Continue to the next iteration of the while loop
            except Exception as e:
                    self.logger.error(f"Unexpected error during pagination on page {page_num}: {e}", exc_info=True)
                    if self.debug_mode:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        self.take_screenshot(f"unexpected_error_pagination_{page_num}_{timestamp}.png")
                        self.save_page_source(f"unexpected_error_pagination_{page_num}_{timestamp}.html")
                    break # Exit loop on unexpected error

            except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e:
                self.logger.error(f"Error finding or processing results table on page {page_num}: {type(e).__name__} - {str(e)}")
                if self.debug_mode:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    self.take_screenshot(f"error_find_table_{page_num}_{timestamp}.png")
                    self.save_page_source(f"error_find_table_{page_num}_{timestamp}.html")
                break # Exit pagination loop if table cannot be reliably processed
            except Exception as e:
                 self.logger.error(f"Unexpected error processing page {page_num}: {e}", exc_info=True)
                 if self.debug_mode:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    self.take_screenshot(f"unexpected_error_page_{page_num}_{timestamp}.png")
                    self.save_page_source(f"unexpected_error_page_{page_num}_{timestamp}.html")
                 break # Exit loop on unexpected error

        self.logger.info(f"Finished processing results for '{company_name}'. Found {len(all_documents)} relevant documents across {page_num} page(s).")
        return all_documents

    def accept_cookies(self):
        """Attempt to find and click the cookie acceptance button."""
        self.logger.debug("Checking for cookie acceptance button...")
        # Use a more flexible XPath that handles common variations
        cookie_button_locator = (By.XPATH, COOKIE_ACCEPT_BUTTON_SELECTOR)
        try:
            # Use a shorter wait time for non-critical elements like cookie banners
            short_wait = WebDriverWait(self.driver, 5) 
            cookie_button = short_wait.until(
                EC.element_to_be_clickable(cookie_button_locator),
                message="Cookie button not found or not clickable within 5s."
            )
            self.logger.info("Cookie acceptance button found. Clicking...")
            cookie_button.click()
            # Wait briefly for banner to disappear (optional)
            WebDriverWait(self.driver, 3).until(
                EC.invisibility_of_element_located(cookie_button_locator)
            )
            self.logger.info("Clicked cookie acceptance button.")
            return True
        except TimeoutException:
            self.logger.debug("Cookie acceptance button not found or did not disappear after click.")
            return False # Not necessarily an error, banner might not be present
        except (NoSuchElementException, ElementClickInterceptedException, ElementNotInteractableException) as e:
            self.logger.warning(f"Error interacting with cookie button: {type(e).__name__} - {str(e)}")
            # Capture state if interaction fails unexpectedly
            if self.debug_mode:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.take_screenshot(f"error_cookie_click_{timestamp}.png")
                self.save_page_source(f"error_cookie_click_{timestamp}.html")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error accepting cookies: {e}", exc_info=True)
            if self.debug_mode:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.take_screenshot(f"unexpected_error_cookie_{timestamp}.png")
                self.save_page_source(f"unexpected_error_cookie_{timestamp}.html")
            return False # Indicate failure

    def get_document_details(self, result_element) -> Optional[Dict]:
        """Extract document details from a single result row element."""
        # Use relative searches within the result_element for robustness
        details = {'issuer_name': '', 'doc_type': '', 'date': '', 'url': '', 'filename': ''}
        try:
            # Wait briefly for the row to be fully rendered before extracting
            WebDriverWait(self.driver, 2).until(EC.visibility_of(result_element)) 

            # First, try to get all td elements in the row
            try:
                cells = result_element.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 3:  # Assume at least 3 cells are needed
                    # Try to extract text from cells using different strategies
                    try:
                        # First cell should be issuer name
                        span = cells[0].find_elements(By.TAG_NAME, "span")
                        if span:
                            details['issuer_name'] = span[0].text.strip()
                        else:
                            details['issuer_name'] = cells[0].text.strip()
                    except (NoSuchElementException, IndexError) as e:
                        self.logger.warning(f"Could not extract issuer name: {e}")
                        details['issuer_name'] = "Unknown Issuer"
                        
                    try:
                        # Second cell should be document type
                        span = cells[1].find_elements(By.TAG_NAME, "span")
                        if span:
                            details['doc_type'] = span[0].text.strip()
                        else:
                            details['doc_type'] = cells[1].text.strip()
                    except (NoSuchElementException, IndexError) as e:
                        self.logger.warning(f"Could not extract document type: {e}")
                        details['doc_type'] = "Unknown Type"
                        
                    try:
                        # Third cell should be date
                        span = cells[2].find_elements(By.TAG_NAME, "span")
                        if span:
                            details['date'] = span[0].text.strip()
                        else:
                            details['date'] = cells[2].text.strip()
                    except (NoSuchElementException, IndexError) as e:
                        self.logger.warning(f"Could not extract date: {e}")
                        details['date'] = datetime.now().strftime("%Y-%m-%d")
                        
                    # Last cell should contain the download link
                    try:
                        # Try to find any link in any of the cells
                        for cell in cells:
                            links = cell.find_elements(By.TAG_NAME, "a")
                            if links:
                                download_link = links[0]
                                details['url'] = download_link.get_attribute('href')
                                # Extract filename from URL or link text if possible
                                parsed_url = urlparse(details['url'])
                                if parsed_url.path:
                                    details['filename'] = Path(parsed_url.path).name
                                else:
                                    details['filename'] = download_link.text.strip() # Fallback to link text
                                break
                    except (NoSuchElementException, IndexError) as e:
                        self.logger.warning(f"Could not find download link in cells: {e}")
                else:
                    self.logger.warning(f"Row doesn't have enough cells. Found: {len(cells)}")
            except NoSuchElementException as e:
                self.logger.warning(f"Could not find td elements in row: {e}")

            # If we couldn't get the URL from cells, try a direct approach
            if not details.get('url'):
                try:
                    # Try to find any link in the row
                    links = result_element.find_elements(By.TAG_NAME, "a")
                    if links:
                        download_link = links[0]
                        details['url'] = download_link.get_attribute('href')
                        # Extract filename from URL if possible
                        parsed_url = urlparse(details['url'])
                        if parsed_url.path:
                            details['filename'] = Path(parsed_url.path).name
                        else:
                            details['filename'] = download_link.text.strip() # Fallback to link text
                except NoSuchElementException:
                    self.logger.warning("Could not find any links in row.")
           
            # Check if essential details were found
            if not details.get('url'):
                self.logger.error("Failed to extract document URL from result row. Cannot download.")
                # Capture state if critical info is missing
                if self.debug_mode:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    try: result_element.screenshot(str(self.screenshots_dir / f"error_extract_url_{timestamp}.png"))
                    except Exception: self.take_screenshot(f"error_extract_url_{timestamp}.png")
                    self.save_page_source(f"error_extract_url_{timestamp}.html")
                return None
           
            self.logger.debug(f"Extracted details: {details}")
            return details

        except StaleElementReferenceException:
            self.logger.warning("Result row became stale while extracting details.")
            # Indicate failure to the caller (process_results) which should handle retrying the page/table
            raise # Re-raise for process_results to catch
        except Exception as e:
            self.logger.error(f"Unexpected error extracting details from row: {e}", exc_info=True)
            # Capture state on unexpected error
            if self.debug_mode:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                try: result_element.screenshot(str(self.screenshots_dir / f"unexpected_error_extract_{timestamp}.png"))
                except Exception: self.take_screenshot(f"unexpected_error_extract_{timestamp}.png")
                self.save_page_source(f"unexpected_error_extract_{timestamp}.html")
            return None # Return None on unexpected error

    def get_file_hash(self, file_path: Path) -> Optional[str]:
        """Calculate SHA-256 hash of a file."""
        if not file_path or not file_path.is_file():
            self.logger.warning(f"Cannot hash non-existent file: {file_path}")
            return None
        hasher = hashlib.sha256()
        try:
            with open(file_path, 'rb') as file:
                while True:
                    chunk = file.read(4096)  # Read in chunks
                    if not chunk:
                        break
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            self.logger.error(f"Error calculating hash for {file_path}: {e}", exc_info=True)
            return None

    def download_document(self, url: str, doc_id: str = None, doc_type_hint: Optional[str] = None, date_hint: Optional[str] = None) -> Optional[str]:
        """Downloads a document using requests, checks for duplicates, and organizes it."""
        self.logger.info(f"Attempting to download document: {doc_id or url}")
        self.requests_count += 1 # Increment request count for session management

        # --- Direct Download Attempt using Requests --- 
        try:
            # Use requests for potentially faster/more reliable downloads than browser clicks
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                # Add other headers if needed (e.g., Referer, Cookies from Selenium session)
                # 'Referer': self.driver.current_url,
                # 'Cookie': '; '.join([f"{c['name']}={c['value']}" for c in self.driver.get_cookies()])
            }
            response = requests.get(url, headers=headers, stream=True, timeout=60) # Increased timeout
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

            # --- Filename Determination --- 
            content_disposition = response.headers.get('content-disposition')
            filename = None
            if content_disposition:
                # Try to parse filename from Content-Disposition header
                filename_match = re.findall('filename="?([^"]+)"?', content_disposition)
                if filename_match:
                    filename = filename_match[0]
           
            # Fallback to URL path if header doesn't provide filename
            if not filename:
                 parsed_url = urlparse(url)
                 if parsed_url.path:
                     filename = Path(parsed_url.path).name
           
            # Generate a default filename if still missing
            if not filename:
                # Use doc_id if available, otherwise hash url
                base_name = doc_id if doc_id else hashlib.md5(url.encode()).hexdigest()
                filename = f"esma_doc_{base_name}.pdf" # Ensure .pdf extension
           
            # Ensure filename has a .pdf extension (or other expected document extension)
            if not re.search(r'\.(pdf|docx|zip)$', filename, re.IGNORECASE):
                 filename += ".pdf"

            # Define temporary download path
            temp_download_path = self.download_dir / f"{filename}.part"

            # --- Download Content --- 
            self.logger.debug(f"Downloading to temporary file: {temp_download_path}")
            hasher = hashlib.sha256()
            try:
                with open(temp_download_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk: # filter out keep-alive new chunks
                            f.write(chunk)
                            hasher.update(chunk)
            except Exception as e:
                self.logger.error(f"Error writing downloaded content to {temp_download_path}: {e}", exc_info=True)
                # Clean up partial file on write error
                if temp_download_path.exists(): temp_download_path.unlink()
                return None
            finally:
                response.close() # Ensure connection is closed
           
            self.logger.info(f"Finished writing temporary file: {temp_download_path} (Size: {temp_download_path.stat().st_size} bytes)")
            content_hash = hasher.hexdigest()
            self.logger.debug(f"Calculated hash for downloaded content: {content_hash}")

            # --- Deduplication Check --- 
            if content_hash in self.document_hashes:
                existing_path = self.document_hashes[content_hash]
                self.logger.info(f"Duplicate document detected (Hash: {content_hash}). Already exists at: {existing_path}")
                # Clean up the temporary downloaded file
                if temp_download_path.exists():
                    temp_download_path.unlink()
                    self.logger.debug(f"Removed temporary duplicate file: {temp_download_path}")
                # Return the path of the existing file
                # Check if the existing file still exists before returning path
                if Path(existing_path).exists():
                    return str(Path(existing_path))
                else:
                    self.logger.warning(f"Duplicate hash found, but existing file {existing_path} is missing. Proceeding to save new download.")
                    # Remove the broken entry from hashes
                    del self.document_hashes[content_hash]
                    # Continue to organize and save the new file

            # --- File Organization --- 
            self.logger.debug("Organizing downloaded file...")
            # Use self.current_company if set (e.g., called from main loop), otherwise use a placeholder
            org_company_name = self.current_company if self.current_company else "UnknownCompany"
            organized_successfully, final_path = self.organize_file(
                temp_download_path, 
                org_company_name, 
                doc_type_hint=doc_type_hint, # Use passed hint
                date_hint=date_hint,       # Use passed hint
                content_hash=content_hash
            )

            if organized_successfully and final_path:
                self.logger.info(f"Document downloaded and organized successfully: {final_path}")
                # Update hashes database
                self.document_hashes[content_hash] = str(final_path)
                self._save_document_hashes()
                return str(final_path)
            else:
                self.logger.error(f"Failed to organize downloaded file from URL: {url}")
                # Keep the temporary file for inspection if organization fails? No, delete.
                if temp_download_path.exists():
                     try:
                         temp_download_path.unlink()
                         self.logger.debug(f"Removed temporary file after organization failure: {temp_download_path}")
                     except OSError as e:
                          self.logger.error(f"Error removing temporary file {temp_download_path}: {e}")
                return None

        except requests.exceptions.RequestException as e:
            self.logger.error(f"HTTP error downloading {url}: {e}", exc_info=False) # Don't need full trace for HTTP errors
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error downloading {url}: {e}", exc_info=True)
            # Clean up temp file on unexpected error
            if 'temp_download_path' in locals() and temp_download_path.exists():
                try:
                     temp_download_path.unlink()
                except OSError as del_e: self.logger.error(f"Error removing temp file {temp_download_path} on error: {del_e}")
            return None

    def organize_file(self, temp_file_path: Path, company_name: str, doc_type_hint: str = None,
                     date_hint: str = None, content_hash: str = None) -> Tuple[bool, Optional[Path]]:
        """Organizes a downloaded file into the correct company folder with standardized naming."""
        self.logger.debug(f"Organizing file: {temp_file_path} for company: {company_name}")
        if not temp_file_path.exists():
             self.logger.error(f"Temporary file {temp_file_path} does not exist for organization.")
             return False, None

        # Sanitize company name for directory creation
        # Replace invalid characters (e.g., /, \, :, *, ?, ", <, >, |) with underscores
        sanitized_company_name = re.sub(r'[\\\\/:*?\"<>|]', '_', company_name)
        # Limit length if necessary
        sanitized_company_name = sanitized_company_name[:100] # Example limit
        
        # Create company-specific directory
        company_dir = self.download_dir / sanitized_company_name
        try:
            company_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Ensured company directory exists: {company_dir}")
        except OSError as e:
            self.logger.error(f"Failed to create company directory {company_dir}: {e}")
            return False, None

        # Determine Document Type
        doc_type = doc_type_hint or "UnknownType"
        # Basic sanitization for filename part
        sanitized_doc_type = re.sub(r'\W+', '_', doc_type).strip('_')[:30]

        # Determine Date
        date_str = date_hint or datetime.now().strftime('%Y%m%d')
        # Basic sanitization/formatting for filename part
        sanitized_date = re.sub(r'[^0-9]', '', date_str)[:8]
        if not sanitized_date:
            sanitized_date = datetime.now().strftime('%Y%m%d')

        # Get Content Hash (calculate if not provided)
        if not content_hash:
            content_hash = self.get_file_hash(temp_file_path)
            if not content_hash:
                self.logger.error(f"Failed to calculate hash for {temp_file_path}. Cannot organize.")
                return False, None
        # Use a short hash for the filename
        short_hash = content_hash[:8]

        # Construct final filename
        # Format: {document_type}_{date}_{short_hash}.pdf
        final_filename = f"{sanitized_doc_type}_{sanitized_date}_{short_hash}.pdf" # Assume PDF for now
        final_path = company_dir / final_filename
        self.logger.debug(f"Determined final path: {final_path}")

        # --- Move/Rename the File --- 
        try:
            # Check if a file with the same name already exists (shouldn't happen if hash check worked)
            if final_path.exists():
                # If destination exists, compare hashes
                existing_hash = self.get_file_hash(final_path)
                if existing_hash == content_hash:
                    self.logger.warning(f"File with same name and content already exists at {final_path}. Discarding temporary file.")
                    if temp_file_path.exists(): temp_file_path.unlink()
                    return True, final_path # Indicate success, using the existing file
                else:
                    # Hash mismatch - potential collision or previous error
                    self.logger.error(f"Filename collision with different content at {final_path}. Cannot move {temp_file_path}.")
                    # Consider adding a unique suffix or logging for manual review
                    return False, None
            else:
                # Move the temporary file to the final destination
                shutil.move(str(temp_file_path), str(final_path))
                self.logger.info(f"Successfully moved {temp_file_path.name} to {final_path}")
                return True, final_path
        except Exception as e:
            self.logger.error(f"Error moving/renaming {temp_file_path} to {final_path}: {e}", exc_info=True)
            # Clean up temp file if move fails
            if temp_file_path.exists():
                try: temp_file_path.unlink()
                except OSError as del_e: self.logger.error(f"Error removing temp file {temp_file_path} after move error: {del_e}")
            return False, None

    def wait_for_page_load(self, timeout=None):
        """Wait for the page to reach a ready state."""
        wait_time = timeout if timeout is not None else self.default_wait_timeout
        self.logger.debug(f"Waiting up to {wait_time}s for page ready state...")
        start_time = time.time()
        try:
            # Wait for document.readyState to be 'complete'
            WebDriverWait(self.driver, wait_time).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            
            # Additionally, wait for a key element that indicates search page is loaded
            # Example: Wait for the search form container or search button to be present
            # Adjust selector as needed
            key_element_selector = (By.ID, SEARCH_INPUT_ID) # Use the search input field ID as indicator
            self.logger.debug(f"Waiting for key element: {key_element_selector}")
            WebDriverWait(self.driver, wait_time).until(EC.presence_of_element_located(key_element_selector))
            
            self.logger.debug(f"Page reached ready state in {time.time() - start_time:.2f}s.")
            return True
        except TimeoutException:
            self.logger.error(f"Timeout waiting for page to load after {wait_time} seconds.")
            if self.debug_mode:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.take_screenshot(f"timeout_page_load_{timestamp}.png")
                self.save_page_source(f"timeout_page_load_{timestamp}.html")
            return False
        except Exception as e:
            self.logger.error(f"Error waiting for page load: {e}", exc_info=True)
            if self.debug_mode:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.take_screenshot(f"error_page_load_{timestamp}.png")
                self.save_page_source(f"error_page_load_{timestamp}.html")
            return False

    def take_screenshot(self, name):
        """Take a screenshot and save it to the debug directory."""
        if not self.debug_mode or not self.driver:
            return
        try:
            path = self.screenshots_dir / name
            self.driver.save_screenshot(str(path))
            self.logger.debug(f"Screenshot saved: {path}")
        except Exception as e:
            self.logger.error(f"Failed to take screenshot '{name}': {str(e)}")

    def save_page_source(self, name):
        """Save the current page source to the debug directory."""
        if not self.debug_mode or not self.driver:
            return
        try:
            path = self.page_sources_dir / name
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            self.logger.debug(f"Page source saved: {path}")
        except Exception as e:
            self.logger.error(f"Failed to save page source '{name}': {str(e)}")

# Example usage (optional, for testing)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Example: Process a single company
    scraper = None
    try:
        # Run headed for easier debugging locally
        scraper = ESMAScraper(debug_mode=True, headless=False)
        
        # --- Test Navigation and Settings --- 
        if scraper.navigate_to_search():
            # --- Test Search and Processing --- 
            test_company = "BNP Paribas" # Choose a company with known results
            if scraper.search_company(test_company):
                # Now set results per page AFTER search (since dropdown only appears after search)
                time.sleep(4)  # Wait for dropdown to appear (up to 4 seconds as user indicated)
                scraper.set_results_per_page(100)  # Set to 100 results per page
                
                # Process results
                results = scraper.process_results(test_company)
                logging.info(f"Found {len(results)} documents for {test_company}.")
                
                # --- Test Download (if results found) ---
                if results:
                    first_doc = results[0]
                    logging.info(f"Attempting to download first document: {first_doc.get('url')}")
                    downloaded_path = scraper.download_document(
                        first_doc.get('url'),
                        first_doc.get('issuer_name', test_company),
                        first_doc.get('doc_type'),
                        first_doc.get('date')
                    )
                    if downloaded_path:
                        logging.info(f"Download successful, file at: {downloaded_path}")
                    else:
                        logging.error("Download failed.")
                else:
                    logging.error(f"Search failed for {test_company}.")
            else:
                logging.error("Navigation to search page failed.")
        
        # --- Test Processing All Companies (Optional, can be long) ---
        # scraper.process_all_eu_companies()
        
    except Exception as main_e:
        logging.error(f"An error occurred during the main execution: {main_e}", exc_info=True)
    finally:
        if scraper:
            scraper.close()
            logging.info("Scraper closed.")