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
import csv
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException, ElementNotInteractableException
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from fuzzywuzzy import fuzz
from .company_list_handler import CompanyListHandler
from .utils.decorators import retry, NETWORK_ERRORS
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
        self.fuzzy_match_threshold = 65 # Lowered from 80
        # self.min_similarity = 80 # Potentially unused, replaced by fuzzy_match_threshold?
        self.company_list_handler = CompanyListHandler()
        
        # User-Agent rotation support
        self.user_agent = self._select_user_agent()
        
        # Proxy configuration from environment
        self.http_proxy = os.environ.get('HTTP_PROXY')
        self.https_proxy = os.environ.get('HTTPS_PROXY')
        
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

        # Seen URLs cache (avoid re-downloading same link across runs)
        self.seen_urls_file = Path("data/processed/seen_urls.txt")
        self.seen_urls_file.parent.mkdir(parents=True, exist_ok=True)
        self.seen_urls: set[str] = self._load_seen_urls()

        # Audit log base dir
        self.audit_dir = Path("logs/audit")
        self.audit_dir.mkdir(parents=True, exist_ok=True)

    def setup_driver(self):
        """Set up the Chrome driver with retries."""
        max_retries = 3
        retry_delay = 5
        
        # Use retry logic for driver setup
        for attempt in range(1, max_retries + 1):
            try:
                self.logger.info(f"Initializing Chrome driver (Attempt {attempt}/{max_retries})...")
                options = self.setup_chrome_options()

                # Detect installed Chrome major version to align driver
                version_main = self._detect_chrome_major_version(default=141)
                self.logger.info(f"Detected Chrome major version: {version_main}")
                self.driver = uc.Chrome(options=options, version_main=version_main)
                
                self.logger.info("Chrome driver initialized successfully")
                self.wait = WebDriverWait(self.driver, self.default_wait_timeout)
                return
            except Exception as e:
                self.logger.error(f"Attempt {attempt} failed to initialize Chrome driver: {str(e)}", exc_info=True)
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

    def setup_chrome_options(self):
        """Set up Chrome options for undetected-chromedriver."""
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

        # User agent rotation - use selected UA
        if self.user_agent:
            options.add_argument(f"user-agent={self.user_agent}")
            self.logger.debug(f"Using User-Agent: {self.user_agent[:50]}...")
        
        # Proxy configuration from environment
        # Chrome only supports one proxy setting, so prioritize HTTPS if both are set
        proxy_to_use = None
        if self.https_proxy:
            proxy_to_use = self.https_proxy
            self.logger.info(f"Using HTTPS proxy: {self.https_proxy}")
        elif self.http_proxy:
            proxy_to_use = self.http_proxy
            self.logger.info(f"Using HTTP proxy: {self.http_proxy}")
        
        if proxy_to_use:
            options.add_argument(f'--proxy-server={proxy_to_use}')
        
        # Set up download preferences
        prefs = {
            "download.default_directory": str(self.download_dir.absolute()),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "plugins.always_open_pdf_externally": True # Try to force download PDFs
        }
        options.add_experimental_option("prefs", prefs)
        return options

    def _detect_chrome_major_version(self, default: int = 145) -> int:
        """Best-effort detection of installed Chrome major version on Windows.

        Falls back to provided default if detection fails.
        """
        try:
            # Common install locations
            candidates = [
                Path(r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"),
                Path(r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"),
                Path(os.path.expandvars(r"%LOCALAPPDATA%\\Google\\Chrome\\Application\\chrome.exe")),
            ]
            for exe in candidates:
                if exe.exists():
                    try:
                        import subprocess
                        out = subprocess.check_output([str(exe), "--version"], text=True, timeout=5)
                        # e.g., 'Google Chrome 138.0.XXXX.XX'
                        parts = re.findall(r"(\d+)\.", out)
                        if parts:
                            major = int(parts[0])
                            return major
                    except Exception:
                        continue
        except Exception:
            pass
        return default
    
    def _select_user_agent(self) -> str:
        """Select a user agent, optionally rotating based on environment."""
        # Check if UA rotation is enabled
        ua_rotation_enabled = os.environ.get('SCRAPER_UA_ROTATION', 'false').lower() == 'true'
        
        # Curated list of modern user agents
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        
        if ua_rotation_enabled:
            selected_ua = random.choice(user_agents)
            self.logger.info(f"UA rotation enabled, selected: {selected_ua[:50]}...")
            return selected_ua
        else:
            # Default UA (same as current default)
            return user_agents[0]

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

    def _load_seen_urls(self) -> set:
        """Load seen URLs from file to skip re-downloading the same link across runs."""
        try:
            if not self.seen_urls_file.exists():
                return set()
            with open(self.seen_urls_file, 'r', encoding='utf-8') as f:
                return set(line.strip() for line in f if line.strip())
        except Exception as e:
            self.logger.error(f"Error loading seen URLs: {e}")
            return set()

    def _save_seen_urls(self) -> None:
        """Persist seen URLs cache to disk."""
        try:
            with open(self.seen_urls_file, 'w', encoding='utf-8') as f:
                for url in sorted(self.seen_urls):
                    f.write(url + "\n")
        except Exception as e:
            self.logger.error(f"Error saving seen URLs: {e}")

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
        """Process only the current results page. Assumes page size already set to 100."""
        self.logger.info(f"Processing current results page for company: {company_name}")
        documents: List[Dict] = []

        results_table_locator = (By.ID, RESULTS_TABLE_ID)
        results_container_locator = (By.ID, RESULTS_CONTAINER_ID)
        result_row_selector = "tbody tr"

        try:
            self.logger.debug("Locating results container and table...")
            results_container = self.wait.until(
                EC.presence_of_element_located(results_container_locator),
                message="Results container not found."
            )
            try:
                short_wait = WebDriverWait(self.driver, 5)
                results_table = short_wait.until(
                    EC.presence_of_element_located(results_table_locator),
                    message="Results table not found within container."
                )
            except TimeoutException:
                results_table = results_container

            rows = results_table.find_elements(By.CSS_SELECTOR, result_row_selector)
            self.logger.info(f"Found {len(rows)} rows on current page.")

            for idx, row in enumerate(rows):
                try:
                    row_data = self.get_document_details(row)
                    if not row_data or not row_data.get('url'):
                        continue
                        
                    # Improved 'already_seen' logic as per Phase 2 plan
                    url = row_data['url']
                    is_seen = url in self.seen_urls
                    row_data['already_seen'] = is_seen
                    
                    if not is_seen:
                        documents.append(row_data)
                    else:
                        self.logger.debug(f"Skipping already-seen URL in process_results: {url}")
                        
                except Exception as e:
                    self.logger.warning(f"Skipping row {idx+idx} due to error: {e}")

        except Exception as e:
            self.logger.error(f"Failed to process current results page: {e}", exc_info=True)

        return documents

    def accept_cookies(self):
        """Attempt to find and click the cookie acceptance button."""
        self.logger.debug("Checking for cookie acceptance button...")
        # Use a more flexible XPath that handles common variations
        cookie_button_locator = (By.XPATH, COOKIE_ACCEPT_BUTTON_SELECTOR)
        try:
            # Increased timeout to 10s as per Phase 2 improvement plan
            short_wait = WebDriverWait(self.driver, 10) 
            cookie_button = short_wait.until(
                EC.element_to_be_clickable(cookie_button_locator),
                message="Cookie button not found or not clickable within 10s."
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
        details = {'issuer_name': '', 'doc_type': '', 'date': '', 'url': '', 'filename': ''}
        try:
            # Use more specific selectors based on the table structure
            cells = result_element.find_elements(By.TAG_NAME, "td")
            if len(cells) < 11: # Expecting 11 columns based on actual table structure
                self.logger.warning(f"Row has fewer than 11 cells, skipping. HTML: {result_element.get_attribute('innerHTML')}")
                return None

            # Extract details based on column position from actual table structure
            # Column 4: Issuer(s) Name / LEI - extract just the company name part
            full_issuer = cells[4].text.strip()
            # Split on " - " to separate company name from LEI code
            if " - " in full_issuer:
                details['issuer_name'] = full_issuer.split(" - ")[0].strip()
            else:
                details['issuer_name'] = full_issuer
            
            details['doc_type'] = cells[1].text.strip()
            details['date'] = cells[3].text.strip()
            # Try to detect ISIN if present (Column 5: ISIN)
            try:
                details['isin'] = cells[5].text.strip()
            except Exception:
                details['isin'] = ''

            # The PDF download link is in column 9 (Physical Document column)
            link_href = None
            try:
                # Column 9 contains the PDF download link
                pdf_cell = cells[9]
                a = pdf_cell.find_element(By.TAG_NAME, "a")
                href = a.get_attribute('href')
                if href and 'downloadFile' in href:
                    link_href = href
            except Exception:
                # Fallback: search for any PDF download link in the row
                try:
                    a = result_element.find_element(By.CSS_SELECTOR, "a[href*='downloadFile']")
                    link_href = a.get_attribute('href')
                except Exception:
                    link_href = None
            details['url'] = link_href or ''
            
            # --- Fuzzy Match Calculation ---
            if self.current_company and details.get('issuer_name'):
                details['fuzzy_score'] = fuzz.token_set_ratio(self.current_company, details['issuer_name'])
            else:
                details['fuzzy_score'] = 0
            # --- End Fuzzy Match Calculation ---

            self.logger.debug(f"Extracted details: {details}")
            return details

        except (NoSuchElementException, IndexError) as e:
            self.logger.error(f"Error parsing row details: {e}. HTML: {result_element.get_attribute('innerHTML')}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error in get_document_details: {e}", exc_info=True)
            return None

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

    @retry(max_retries=3, delay=5, backoff=2, exceptions=NETWORK_ERRORS)
    def download_document(self, url: str, doc_id: str = None, doc_type_hint: Optional[str] = None, date_hint: Optional[str] = None) -> Optional[str]:
        """Downloads a document using requests, checks for duplicates, and organizes it.
        
        Retries network errors with exponential backoff.
        """
        self.logger.info(f"Attempting to download document: {doc_id or url}")
        self.requests_count += 1 # Increment request count for session management

        # --- Direct Download Attempt using Requests --- 
        try:
            # Use requests for potentially faster/more reliable downloads than browser clicks
            headers = {
                'User-Agent': self.user_agent  # Use the same UA as Chrome session
            }
            
            # Add Referer from current page if driver is available
            if self.driver:
                try:
                    headers['Referer'] = self.driver.current_url
                    self.logger.debug(f"Added Referer: {self.driver.current_url}")
                except Exception as e:
                    self.logger.debug(f"Could not get Referer from driver: {e}")
            
            # Add cookies from Selenium session if available
            if self.driver:
                try:
                    cookies = self.driver.get_cookies()
                    if cookies:
                        cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in cookies])
                        headers['Cookie'] = cookie_str
                        self.logger.debug(f"Added {len(cookies)} cookies from Selenium session")
                except Exception as e:
                    self.logger.debug(f"Could not get cookies from driver: {e}")
            
            # Configure proxy for requests if set
            proxies = None
            if self.http_proxy or self.https_proxy:
                proxies = {
                    'http': self.http_proxy,
                    'https': self.https_proxy or self.http_proxy
                }
                self.logger.debug(f"Using proxies for requests: {proxies}")
            
            response = requests.get(url, headers=headers, stream=True, timeout=60, proxies=proxies) # Increased timeout
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
        if not temp_file_path.exists():
            self.logger.error(f"Temporary file {temp_file_path} does not exist for organization.")
            return False, None

        try:
            # Sanitize company name for directory creation
            sanitized_company_name = re.sub(r'[\\\\/:*?\"<>|]', '_', company_name)
            
            # Create company-specific directory
            company_dir = self.download_dir / sanitized_company_name
            company_dir.mkdir(parents=True, exist_ok=True)

            # Sanitize document type for filename
            sanitized_doc_type = re.sub(r'\W+', '_', doc_type_hint or "UnknownType").strip('_')[:30]

            # Sanitize date for filename
            sanitized_date = re.sub(r'[^0-9]', '', date_hint or datetime.now().strftime('%Y%m%d'))[:8]
            if not sanitized_date:
                sanitized_date = datetime.now().strftime('%Y%m%d')

            # Get a short hash for the filename
            short_hash = (content_hash or self.get_file_hash(temp_file_path) or "no_hash")[:8]

            # Construct final path and move the file
            final_filename = f"{sanitized_doc_type}_{sanitized_date}_{short_hash}.pdf"
            final_path = company_dir / final_filename
            
            shutil.move(str(temp_file_path), str(final_path))
            
            self.logger.info(f"Successfully moved file to {final_path}")
            return True, final_path

        except Exception as e:
            self.logger.error(f"Error organizing file {temp_file_path}: {e}", exc_info=True)
            if temp_file_path.exists():
                temp_file_path.unlink()
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

    # -------- Enhanced Matching & Orchestration --------
    @staticmethod
    def _normalize_name(name: str) -> str:
        normalized = re.sub(r"[\W_]+", " ", name or "").lower().strip()
        # Remove common legal suffixes for fuzzy matching
        normalized = re.sub(r"\b(ag|sa|gmbh|nv|n\.v\.|plc|s\.a\.|s\.p\.a\.|b\.v\.|bv|inc|ltd)\b", "", normalized)
        return re.sub(r"\s+", " ", normalized)

    def _build_company_profile(self, company_name: str, company_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Build company profile, merging disk profile and GOGEL identifiers.
        
        Args:
            company_name: The canonical company name.
            company_data: Optional dict from CompanyListHandler with financial
                identifiers (lei, isin_equity, isins_bonds, etc.).
        """
        # Build default profile
        base = company_name
        base_norm = self._normalize_name(base)
        short_token = base.split(" ")[0]
        tokens = [short_token, base]
        default_profile = {
            "canonical_name": base,
            "aliases": [base, base_norm, base.replace(" Aktiengesellschaft", ""), base.split(" ")[0]],
            "lei_codes": [],
            "isins": [],
            "negative_keywords": [],
            "search_tokens": tokens,
        }
        
        # Merge financial identifiers from GOGEL CSV data if available
        if company_data and isinstance(company_data, dict):
            lei = company_data.get('lei', '')
            if lei:
                default_profile['lei_codes'] = [lei]
            
            # Collect all known ISINs into a single flat list for matching
            all_isins = []
            isin_eq = company_data.get('isin_equity', '')
            if isin_eq:
                all_isins.append(isin_eq)
            all_isins.extend(company_data.get('isins_bonds', []))
            all_isins.extend(company_data.get('isins_bonds_subsidiaries', []))
            default_profile['isins'] = list(dict.fromkeys(all_isins))  # dedupe, preserve order
            
            self.logger.info(f"Profile for '{company_name}': {len(default_profile['isins'])} ISINs, LEI={'yes' if lei else 'no'}")
        
        # Load and merge disk profile if present
        profiles_path = Path("data/company_profiles.json")
        if profiles_path.exists():
            try:
                with open(profiles_path, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
                if company_name in profiles:
                    disk_profile = profiles[company_name]
                    merged = default_profile.copy()
                    merged.update(disk_profile)
                    if 'aliases' in disk_profile and isinstance(disk_profile['aliases'], list):
                        merged['aliases'] = list(dict.fromkeys(default_profile['aliases'] + disk_profile['aliases']))
                    if 'search_tokens' in disk_profile and isinstance(disk_profile['search_tokens'], list):
                        merged['search_tokens'] = list(dict.fromkeys(default_profile['search_tokens'] + disk_profile['search_tokens']))
                    # Preserve GOGEL ISINs even when disk profile exists
                    if default_profile.get('isins'):
                        merged['isins'] = list(dict.fromkeys(default_profile['isins'] + merged.get('isins', [])))
                    self.logger.info(f"Loaded and merged profile for '{company_name}' from disk")
                    return merged
            except Exception as e:
                self.logger.warning(f"Could not load company profiles: {e}")

        return default_profile

    def _classify_green(self, details: Dict[str, Any]) -> Dict[str, Any]:
        green_keywords = [
            "green", "sustainability", "sustainable", "climate", "environmental",
            "social bond", "transition"
        ]
        text = f"{details.get('doc_type','')} {details.get('issuer_name','')}".lower()
        score = sum(1 for kw in green_keywords if kw in text) / max(1, len(green_keywords))
        return {
            "is_green": score >= 0.2,
            "confidence": round(score, 3)
        }

    def _compute_multi_signal_score(self, details: Dict[str, Any], profile: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
        """Score a result row against a company profile using multiple signals.
        
        When the profile contains ISINs (from GOGEL 2025 CSV), an exact ISIN
        match produces a near-perfect score (0.95+), making fuzzy name matching
        a fallback rather than the primary signal.
        """
        # --- ISIN match (definitive identifier) ---
        isin_match = 0.0
        row_isin = (details.get('isin') or '').strip()
        known_isins = profile.get('isins', [])
        if row_isin and len(row_isin) >= 12 and known_isins:
            if row_isin in known_isins:
                isin_match = 1.0
                self.logger.debug(f"ISIN match: {row_isin}")

        # --- LEI match (check if LEI appears in the issuer field) ---
        lei_match = 0.0
        lei_codes = profile.get('lei_codes', [])
        issuer_raw = details.get('issuer_name', '') or ''
        for lei in lei_codes:
            if lei and lei in issuer_raw:
                lei_match = 1.0
                self.logger.debug(f"LEI match in issuer field: {lei}")
                break

        # --- Name similarity against aliases ---
        issuer = self._normalize_name(issuer_raw)
        name_sims = [fuzz.token_set_ratio(issuer, self._normalize_name(a)) / 100.0 for a in profile.get('aliases', [])]
        name_sim = max(name_sims) if name_sims else 0.0

        # --- Doc type relevance ---
        doc_type = (details.get('doc_type') or '').lower()
        if 'final' in doc_type:
            doc_type_score = 1.0
        elif 'base prospectus' in doc_type:
            doc_type_score = 0.5
        else:
            doc_type_score = 0.3

        # --- Recency score ---
        date_text = details.get('date', '')
        recency_score = 0.5
        try:
            for fmt in ("%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%y"):
                try:
                    dt = datetime.strptime(date_text, fmt)
                    age_days = max(0, (datetime.now() - dt).days)
                    recency_score = max(0.1, 1.0 / (1.0 + age_days / 365.0))
                    break
                except Exception:
                    continue
        except Exception:
            pass

        # --- Penalties ---
        penalty = 0.0
        noise_terms = ["warrant", "certificate"]
        for term in noise_terms:
            if term in doc_type:
                penalty += 0.2

        # --- Combine ---
        # If we have a definitive identifier match (ISIN or LEI), use a
        # simplified high-confidence score. Otherwise fall back to fuzzy scoring.
        if isin_match > 0 or lei_match > 0:
            identifier_base = max(isin_match, lei_match) * 0.95
            score = identifier_base + 0.05 * doc_type_score - penalty
        else:
            weights = {"name": 0.55, "doctype": 0.3, "recency": 0.15, "penalty": -1.0}
            score = (
                weights["name"] * name_sim +
                weights["doctype"] * doc_type_score +
                weights["recency"] * recency_score +
                weights["penalty"] * penalty
            )
        
        return max(0.0, min(1.0, score)), {
            "name_sim": round(name_sim, 3),
            "doc_type": doc_type_score,
            "recency": round(recency_score, 3),
            "penalty": round(penalty, 3),
            "isin_match": isin_match,
            "lei_match": lei_match,
        }

    def _write_audit_rows(self, company: str, rows: List[Dict[str, Any]]) -> None:
        sanitized = re.sub(r'[\\/:*?"<>|]', '_', company)
        out_dir = self.audit_dir / sanitized
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "esma_rows.csv"
        fieldnames = [
            "issuer_name", "doc_type", "date", "isin", "url", "fuzzy_score",
            "score", "name_sim", "doc_type_score", "recency", "penalty",
            "is_green", "green_confidence", "kept", "already_seen"
        ]
        try:
            write_header = not out_path.exists()
            with open(out_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if write_header:
                    writer.writeheader()
                for r in rows:
                    writer.writerow({k: r.get(k, '') for k in fieldnames})
        except Exception as e:
            self.logger.error(f"Failed to write audit rows: {e}")

    def search_and_process(self, company_name: str, company_data: Dict[str, Any] = None,
                           min_score: float = 0.55) -> List[Dict[str, Any]]:
        """End-to-end: navigate, search, set 100/page, score rows, download above threshold.

        Args:
            company_name: The company name to search for.
            company_data: Optional dict from CompanyListHandler with identifiers
                (lei, isin_equity, isins_bonds, etc.). When provided, the scraper
                can do ISIN-based searches and use identifier matching.
            min_score: Minimum multi-signal score to keep a result row.

        Returns a list of downloaded file paths with metadata.
        """
        self.current_company = company_name
        profile = self._build_company_profile(company_name, company_data=company_data)

        # Choose a broad token for search (first token or alias)
        search_token = profile.get("search_tokens", [company_name.split(" ")[0]])[0]

        self.logger.info(f"Starting search_and_process for '{company_name}' using token '{search_token}'")
        self.navigate_to_search()
        ok = self.search_company(search_token)
        if not ok:
            self.logger.error(f"Search failed for {company_name}")
            return []

        # Ensure 100 rows per page once results present
        time.sleep(4)
        self.set_results_per_page(100)

        # Process the current single page (name-based search)
        rows = self.process_results(company_name)

        # If we have a primary ISIN (equity), do a second search to catch
        # documents that don't match by name but do match by identifier.
        isin_eq = (company_data or {}).get('isin_equity', '') if company_data else ''
        if isin_eq and len(isin_eq) >= 12:
            self.logger.info(f"Running supplementary ISIN search: {isin_eq}")
            self.navigate_to_search()
            isin_ok = self.search_company(isin_eq)
            if isin_ok:
                time.sleep(4)
                self.set_results_per_page(100)
                isin_rows = self.process_results(company_name)
                # Merge, avoiding duplicate URLs
                seen_urls_in_rows = {r.get('url') for r in rows if r.get('url')}
                for ir in isin_rows:
                    if ir.get('url') and ir['url'] not in seen_urls_in_rows:
                        rows.append(ir)
                        seen_urls_in_rows.add(ir['url'])
                self.logger.info(f"After ISIN merge: {len(rows)} total rows")

        scored_rows = []
        for r in rows:
            score, parts = self._compute_multi_signal_score(r, profile)
            g = self._classify_green(r)
            kept = (score >= min_score)
            r.update({
                "score": round(score, 3),
                "name_sim": parts["name_sim"],
                "doc_type_score": parts["doc_type"],
                "recency": parts["recency"],
                "penalty": parts["penalty"],
                "isin_match": parts.get("isin_match", 0.0),
                "lei_match": parts.get("lei_match", 0.0),
                "is_green": g["is_green"],
                "green_confidence": g["confidence"],
                "kept": kept,
            })
            scored_rows.append(r)

        # Audit log
        self._write_audit_rows(company_name, scored_rows)

        # Download kept rows (skip already seen)
        downloads = []
        for r in scored_rows:
            if not r.get('kept'):
                continue
            url = r.get('url')
            if not url:
                continue
            if url in self.seen_urls:
                self.logger.info(f"Skipping already-seen URL: {url}")
                continue
            path = self.download_document(
                url=url,
                doc_id=r.get('isin') or r.get('issuer_name'),
                doc_type_hint=r.get('doc_type'),
                date_hint=r.get('date')
            )
            if path:
                self.seen_urls.add(url)
                downloads.append({
                    "file_path": path,
                    "issuer_name": r.get('issuer_name'),
                    "doc_type": r.get('doc_type'),
                    "date": r.get('date'),
                    "isin": r.get('isin'),
                    "score": r.get('score'),
                    "is_green": r.get('is_green'),
                    "isin_match": r.get('isin_match', 0.0),
                })

        # Persist seen urls
        self._save_seen_urls()
        return downloads

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