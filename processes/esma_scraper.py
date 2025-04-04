from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException
import logging
import colorlog
from pathlib import Path
import time
import os
import random
import requests
from company_list_handler import CompanyListHandler
import json
from datetime import datetime
from selenium.webdriver.common.keys import Keys
import re
from typing import List, Dict, Any, Optional

class ESMAScraper:
    def __init__(self, base_dir: str):
        # Configure colored logging
        handler = colorlog.StreamHandler()
        handler.setFormatter(colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        ))
        
        self.logger = colorlog.getLogger(__name__)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.DEBUG)
        
        self.base_dir = str(Path(base_dir))
        self.base_url = "https://registers.esma.europa.eu"
        self.search_url = f"{self.base_url}/publication/searchRegister?core=esma_registers_priii_documents"
        
        # Create necessary directories
        self.pdf_dir = Path(base_dir) / "pdfs"
        self.pdf_dir.mkdir(exist_ok=True)
        
        # Initialize error tracking
        self.error_tracking = {
            'blocking_errors': [],
            'download_errors': [],
            'search_errors': [],
            'validation_errors': []
        }
        
        # Initialize Chrome options
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-popup-blocking')
        chrome_options.add_argument('--disable-notifications')
        
        # Set modern user agent
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        
        # Add performance options
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument('--no-default-browser-check')
        chrome_options.add_argument('--disable-background-networking')
        
        # Try to find Chrome in common locations
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")
        ]
        
        chrome_found = False
        for path in chrome_paths:
            if os.path.exists(path):
                chrome_options.binary_location = path
                chrome_found = True
                self.logger.info(f"Found Chrome at: {path}")
                break
        
        if not chrome_found:
            self.logger.warning("Chrome not found in common locations")
        
        # Create the driver with error logging disabled
        os.environ['WDM_LOG_LEVEL'] = '0'
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(30)  # Set page load timeout
            self.wait = WebDriverWait(self.driver, 30)
            self.logger.info("Chrome driver initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Chrome driver: {str(e)}")
            raise
        
        # More natural delays
        self.min_delay = 5  # Increased from 3
        self.max_delay = 10  # Increased from 7
        
        # More natural company delays
        self.min_company_delay = 15  # Increased from 10
        self.max_company_delay = 30  # Increased from 20
        
        # Initialize request tracking
        self.request_timestamps = []
        self.session_start_time = time.time()
        
        # Simplified blocking counter
        self.blocking_counter = 0
        self.max_blocks = 3
        
        # More natural wait times
        self.wait_times = {
            0: (30, 60),    # First block: 30-60 seconds
            1: (60, 120),   # Second block: 1-2 minutes
            2: (120, 180)   # Third block: 2-3 minutes
        }
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/pdf,application/x-pdf,*/*',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        self.search_errors = []
        self.download_errors = []
        self.validation_errors = []
        
    def track_error(self, error_type: str, company: str, error_details: dict):
        """Track and log errors with detailed information"""
        error_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'company': company,
            'error_type': error_type,
            'details': error_details
        }
        
        # Add to error tracking
        self.error_tracking[f'{error_type}_errors'].append(error_entry)
        
        # Log the error
        self.logger.error(f"{error_type} error for {company}: {error_details}")
        
    def get_error_summary(self) -> dict:
        """Get summary of all errors"""
        return {
            'total_errors': sum(len(errors) for errors in self.error_tracking.values()),
            'error_types': {
                error_type: len(errors) 
                for error_type, errors in self.error_tracking.items()
            },
            'timestamp': datetime.utcnow().isoformat()
        }
        
    def download_pdf(self, url: str, company_name: str, doc_type: str, approval_date: str) -> str:
        """Download PDF file with enhanced error handling"""
        try:
            # Create company directory if it doesn't exist
            company_dir = self.pdf_dir / company_name.replace('/', '_')
            company_dir.mkdir(exist_ok=True)
            
            # Create filename from document type and approval date
            filename = f"{doc_type}_{approval_date.replace('/', '_')}.pdf"
            filepath = company_dir / filename
            
            # Skip if file already exists
            if filepath.exists():
                self.logger.info(f"PDF already exists: {filepath}")
                return str(filepath)
            
            # Visit the detail page
            self.driver.get(url)
            self.wait_for_page_load()
            
            # Look for PDF download link with enhanced detection
            pdf_link = None
            
            # First try to find the download button/link in the document viewer section
            viewer_selectors = [
                "div[id*='viewer'] a[href*='.pdf']",
                "div[id*='viewer'] a[href*='download']",
                "div[id*='viewer'] button[onclick*='download']",
                "div[id*='viewer'] a[onclick*='download']",
                "div[id*='viewer'] a[onclick*='getDocument']",
                "div[class*='viewer'] a[href*='.pdf']",
                "div[class*='viewer'] a[href*='download']",
                "div[class*='viewer'] button[onclick*='download']",
                "div[class*='document'] a[href*='.pdf']",
                "div[class*='document'] a[href*='download']",
                "div[class*='document'] button[onclick*='download']",
                "div[class*='document'] a[onclick*='download']",
                "div[class*='document'] a[onclick*='getDocument']",
                "iframe[src*='viewer']"
            ]
            
            for selector in viewer_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        self.logger.debug(f"Found potential viewer element with selector: {selector}")
                        if "iframe" in selector:
                            try:
                                self.driver.switch_to.frame(elem)
                                iframe_links = self.driver.find_elements(By.CSS_SELECTOR, 
                                    "a[href*='.pdf'], a[href*='download'], button[onclick*='download'], " +
                                    "a[onclick*='download'], a[onclick*='getDocument']"
                                )
                                for link in iframe_links:
                                    href = link.get_attribute("href")
                                    onclick = link.get_attribute("onclick")
                                    if href:
                                        pdf_link = href
                                        self.logger.info(f"Found PDF link in iframe via href: {pdf_link}")
                                        break
                                    elif onclick and ('download' in onclick.lower() or 'getdocument' in onclick.lower()):
                                        try:
                                            link.click()
                                            time.sleep(2)  # Wait for any redirects
                                            if self.driver.current_url.endswith('.pdf'):
                                                pdf_link = self.driver.current_url
                                                self.logger.info(f"Found PDF link in iframe via click: {pdf_link}")
                                                break
                                        except:
                                            continue
                                self.driver.switch_to.default_content()
                                if pdf_link:
                                    break
                            except:
                                self.driver.switch_to.default_content()
                                continue
                        else:
                            href = elem.get_attribute("href")
                            onclick = elem.get_attribute("onclick")
                            if href:
                                pdf_link = href
                                self.logger.info(f"Found PDF link via href: {pdf_link}")
                                break
                            elif onclick and ("download" in onclick.lower() or "getdocument" in onclick.lower()):
                                try:
                                    # Try to click the element to trigger the download
                                    elem.click()
                                    time.sleep(2)  # Wait for any redirects
                                    if self.driver.current_url.endswith('.pdf'):
                                        pdf_link = self.driver.current_url
                                        self.logger.info(f"Found PDF link via click: {pdf_link}")
                                        break
                                except:
                                    continue
                except Exception as e:
                    self.logger.debug(f"Error with selector {selector}: {str(e)}")
                    continue
                
                if pdf_link:
                    break
            
            # If still no PDF link, try looking in the main document area
            if not pdf_link:
                try:
                    # Look for any download buttons or links
                    download_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                        "a[href*='.pdf'], a[href*='download'], button[onclick*='download'], " +
                        "a[onclick*='download'], a[onclick*='getDocument'], a[onclick*='viewDocument'], " +
                        "a[href*='getDocument'], a[href*='viewDocument'], " +
                        "button[class*='download'], a[class*='download'], " +
                        "button[title*='download'], a[title*='download'], " +
                        "button[aria-label*='download'], a[aria-label*='download']"
                    )
                    
                    for elem in download_elements:
                        href = elem.get_attribute("href")
                        onclick = elem.get_attribute("onclick")
                        text = elem.text.lower()
                        title = (elem.get_attribute("title") or "").lower()
                        aria_label = (elem.get_attribute("aria-label") or "").lower()
                        
                        if href and ('.pdf' in href.lower() or 'download' in href.lower() or 'getdocument' in href.lower()):
                            pdf_link = href
                            self.logger.info(f"Found PDF link in main area via href: {pdf_link}")
                            break
                        elif onclick and ('download' in onclick.lower() or 'getdocument' in onclick.lower()):
                            try:
                                # Try to click the element to trigger the download
                                elem.click()
                                time.sleep(2)  # Wait for any redirects
                                if self.driver.current_url.endswith('.pdf'):
                                    pdf_link = self.driver.current_url
                                    self.logger.info(f"Found PDF link in main area via click: {pdf_link}")
                                    break
                            except:
                                continue
                        elif text and ('download' in text or 'view document' in text or 'get document' in text):
                            try:
                                # Try to click text links that might trigger downloads
                                elem.click()
                                time.sleep(2)  # Wait for any redirects
                                if self.driver.current_url.endswith('.pdf'):
                                    pdf_link = self.driver.current_url
                                    self.logger.info(f"Found PDF link in main area via text click: {pdf_link}")
                                    break
                            except:
                                continue
                        elif title and ('download' in title or 'pdf' in title):
                            try:
                                elem.click()
                                time.sleep(2)
                                if self.driver.current_url.endswith('.pdf'):
                                    pdf_link = self.driver.current_url
                                    self.logger.info(f"Found PDF link via title click: {pdf_link}")
                                    break
                            except:
                                continue
                        elif aria_label and ('download' in aria_label or 'pdf' in aria_label):
                            try:
                                elem.click()
                                time.sleep(2)
                                if self.driver.current_url.endswith('.pdf'):
                                    pdf_link = self.driver.current_url
                                    self.logger.info(f"Found PDF link via aria-label click: {pdf_link}")
                                    break
                            except:
                                continue
                except Exception as e:
                    self.logger.debug(f"Error checking main document area: {str(e)}")
            
            # Try to find any links that might be PDF downloads
            if not pdf_link:
                try:
                    all_links = self.driver.find_elements(By.TAG_NAME, "a")
                    for link in all_links:
                        href = link.get_attribute("href")
                        text = link.text.lower()
                        if href and ('.pdf' in href.lower() or 'download' in href.lower() or 'getdocument' in href.lower()):
                            pdf_link = href
                            self.logger.info(f"Found PDF link via general link search: {pdf_link}")
                            break
                        elif text and ('download' in text or 'view document' in text or 'get document' in text):
                            try:
                                link.click()
                                time.sleep(2)
                                if self.driver.current_url.endswith('.pdf'):
                                    pdf_link = self.driver.current_url
                                    self.logger.info(f"Found PDF link via general text click: {pdf_link}")
                                    break
                            except:
                                continue
                except Exception as e:
                    self.logger.debug(f"Error in general link search: {str(e)}")
            
            if pdf_link:
                # If the URL is relative, make it absolute
                if pdf_link.startswith('/'):
                    pdf_link = f"https://registers.esma.europa.eu{pdf_link}"
                
                # Download the PDF
                try:
                    response = requests.get(pdf_link, headers=self.headers, timeout=30, allow_redirects=True)
                    
                    # Check if we got a PDF
                    content_type = response.headers.get('content-type', '').lower()
                    if response.status_code == 200 and ('application/pdf' in content_type or pdf_link.lower().endswith('.pdf') or '%PDF-' in response.text):
                        # Save the PDF
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        self.logger.info(f"Successfully downloaded PDF to: {filepath}")
                        return str(filepath)
                    else:
                        self.logger.error(f"Failed to download PDF - Status: {response.status_code}, Content-Type: {content_type}")
                        self.track_error('download', company_name, {
                            'url': pdf_link,
                            'error': f'Invalid response - Status: {response.status_code}, Content-Type: {content_type}'
                        })
                except Exception as e:
                    self.logger.error(f"Error downloading PDF from {pdf_link}: {str(e)}")
                    self.track_error('download', company_name, {
                        'url': pdf_link,
                        'error': str(e)
                    })
            else:
                self.logger.error(f"No PDF link found on page: {url}")
                self.track_error('download', company_name, {
                    'url': url,
                    'error': 'No PDF link found'
                })
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error in download_pdf: {str(e)}")
            self.track_error('download', company_name, {
                'url': url,
                'error': str(e)
            })
            return None
        
    def random_delay(self, min_delay=None, max_delay=None):
        """Add random delay between actions with optional min and max parameters"""
        min_d = min_delay if min_delay is not None else self.min_delay
        max_d = max_delay if max_delay is not None else self.max_delay
        time.sleep(random.uniform(min_d, max_d))
        
    def close(self):
        """Close the webdriver and log final error summary"""
        try:
            if hasattr(self, 'driver'):
                self.driver.quit()
                
            # Log final error summary
            summary = self.get_error_summary()
            self.logger.info("Final error summary:")
            self.logger.info(f"Total errors: {summary['total_errors']}")
            for error_type, count in summary['error_types'].items():
                self.logger.info(f"{error_type}: {count}")
                
        except Exception as e:
            self.logger.error(f"Error during close: {str(e)}")
            
    def wait_for_page_load(self, timeout=15):
        """Wait for page to be fully loaded with enhanced checks"""
        try:
            # Wait for document ready state
            self.wait.until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            
            # Wait for any loading indicators to disappear
            try:
                self.wait.until(
                    lambda driver: not driver.find_elements(By.CSS_SELECTOR, '.loading, .spinner, .progress')
                )
            except:
                pass  # Ignore if no loading indicators found
                
            # Wait for any AJAX requests to complete
            try:
                self.wait.until(
                    lambda driver: driver.execute_script('return jQuery.active == 0')
                )
            except:
                pass  # Ignore if jQuery is not present
                
        except TimeoutException:
            self.logger.warning("Page load timeout")
            
    def check_for_blocking(self):
        """More precise blocking detection"""
        try:
            # Get current page source and URL
            current_url = self.driver.current_url
            page_source = self.driver.page_source.lower()
            
            # Only check for actual blocking indicators
            blocking_indicators = [
                "access denied",
                "blocked",
                "rate limit exceeded",
                "too many requests",
                "please try again later"
            ]
            
            # Check for actual blocking messages
            for indicator in blocking_indicators:
                if indicator in page_source:
                    self.logger.warning(f"Detected actual blocking: {indicator}")
                    self.logger.info(f"Page content snippet: {page_source[:500]}")
                    return True
                    
            # Check for actual CAPTCHA elements with detailed logging
            captcha_selectors = [
                "iframe[src*='recaptcha']",
                "iframe[src*='captcha']",
                "div[class*='recaptcha']",
                "div[class*='captcha']"
            ]
            
            for selector in captcha_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    self.logger.warning(f"Detected actual CAPTCHA element using selector: {selector}")
                    for element in elements:
                        self.logger.info(f"CAPTCHA element found: {element.get_attribute('outerHTML')[:200]}")
                    return True
                    
            # Check for text-based CAPTCHA with context
            captcha_text_indicators = [
                "please complete the security check",
                "verify you are human",
                "prove you are not a robot"
            ]
            
            for indicator in captcha_text_indicators:
                if indicator in page_source:
                    # Get the surrounding context
                    index = page_source.find(indicator)
                    context = page_source[max(0, index-100):min(len(page_source), index+100)]
                    self.logger.warning(f"Detected CAPTCHA text: {indicator}")
                    self.logger.info(f"Context: {context}")
                    return True
                    
            # Check for unexpected redirects to error pages
            if "error" in current_url or "security" in current_url:
                self.logger.warning(f"Detected unexpected redirect to: {current_url}")
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"Error in blocking detection: {str(e)}")
            return False
            
    def handle_blocking(self):
        """Simplified blocking recovery"""
        if self.check_for_blocking():
            self.logger.warning("Detected actual blocking, implementing recovery measures")
            
            # Track the blocking event
            self.track_error('blocking', 'system', {
                'action': 'blocking_detected',
                'block_count': self.blocking_counter,
                'current_url': self.driver.current_url
            })
            
            # Get wait time based on blocking counter
            min_wait, max_wait = self.wait_times.get(self.blocking_counter, (30, 60))
            wait_time = random.uniform(min_wait, max_wait)
            
            self.logger.info(f"Block #{self.blocking_counter + 1}: Waiting {wait_time:.0f} seconds")
            time.sleep(wait_time)
            
            # Simple recovery: clear cookies and refresh
            self.driver.delete_all_cookies()
            self.driver.refresh()
            self.wait_for_page_load()
            
            # Increment blocking counter
            self.blocking_counter += 1
            
            # If still blocked after max blocks, reset everything
            if self.check_for_blocking() and self.blocking_counter >= self.max_blocks:
                self.track_error('blocking', 'system', {
                    'action': 'max_blocks_reached',
                    'block_count': self.blocking_counter
                })
                
                # Reset blocking counter
                self.blocking_counter = 0
                
                # Wait and restart session
                time.sleep(random.uniform(60, 120))
                self.driver.quit()
                self.initialize_session()
            
    def get_company_variations(self, company_name: str) -> list:
        """Generate variations of company name for better search results"""
        # Remove common suffixes
        base_name = company_name
        suffixes = [' AS', ' ASA', ' SA', ' SE', ' AG', ' BV', ' Ltd', ' Ltd.', ' Limited', ' plc', ' Inc.', ' Inc', ' SGPS']
        for suffix in suffixes:
            if company_name.endswith(suffix):
                base_name = company_name[:-len(suffix)]
                break
        
        # Get country from company info if available
        country = ""
        if hasattr(self, 'company_info') and self.company_info.get('country'):
            country = self.company_info['country']
        
        variations = [
            company_name,  # Original name
            base_name,     # Without suffix
            base_name + " AS",
            base_name + " ASA",
            base_name + " SA",
            base_name + " SE",
            base_name + " AG",
            base_name + " BV",
            base_name + " Ltd",
            base_name + " Limited",
            base_name + " plc",
            base_name + " SGPS",
            base_name + " " + country,  # Add country
            base_name + " " + country + " AS",
            base_name + " " + country + " SA",
            base_name + " " + country + " SGPS"
        ]
        
        # Remove duplicates and empty strings
        return list(set(filter(None, variations)))
        
    def search_and_process(self, company_name: str, company_info: dict = None) -> list:
        """Search and process with enhanced error tracking"""
        try:
            self.logger.info(f"Processing company: {company_name}")
            
            # Navigate to base URL with required parameters
            search_url = "https://registers.esma.europa.eu/publication/searchRegister?core=esma_registers_priii_documents"
            self.driver.get(search_url)
            self.wait_for_page_load()
            
            # Verify we're on the correct page
            current_url = self.driver.current_url
            if "registers.esma.europa.eu" not in current_url or "core=esma_registers_priii_documents" not in current_url:
                self.logger.error(f"Not on correct ESMA page. Current URL: {current_url}")
                raise Exception("Failed to load correct ESMA page")
            
            # Wait for cookie consent if present and accept it
            try:
                cookie_button = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "button.accept-cookies, button[class*='cookie'], #cookie-accept"))
                )
                cookie_button.click()
                self.logger.info("Accepted cookies")
            except:
                self.logger.info("No cookie consent found")
            
            # Wait for the search form and input
            try:
                # Find the keyword input - try multiple approaches
                keyword_input = None
                input_selectors = [
                    "input[type='text']",
                    "#keyword",
                    "input[name='keyword']",
                    "input[name*='search']",
                    ".keyword-search input"
                ]
                
                for selector in input_selectors:
                    try:
                        keyword_input = self.wait.until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        if keyword_input and keyword_input.is_displayed():
                            self.logger.info(f"Found keyword input using selector: {selector}")
                            break
                    except:
                        continue
                
                if not keyword_input:
                    raise Exception("Could not find keyword input")
                
                # Clear and fill the input
                self.random_delay(1, 2)
                keyword_input.clear()
                self.random_delay(1, 2)
                
                # Type the company name character by character
                for char in company_name:
                    keyword_input.send_keys(char)
                    self.random_delay(0.1, 0.3)
                
                self.logger.info(f"Entered search term: {company_name}")
                
                # Try clicking search button first
                try:
                    search_button = None
                    search_selectors = [
                        "button[type='submit']",
                        "input[type='submit']",
                        "button:contains('Search')",
                        "input[value='Search']",
                        ".search-button",
                        "#search-button",
                        "button.search",
                        "input.search"
                    ]
                    
                    for selector in search_selectors:
                        try:
                            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            for element in elements:
                                if element.is_displayed() and element.is_enabled():
                                    search_button = element
                                    self.logger.info(f"Found search button using selector: {selector}")
                                    break
                        except:
                            continue
                        if search_button:
                            break
                    
                    if search_button:
                        search_button.click()
                        self.logger.info("Clicked search button")
                        self.wait_for_page_load(timeout=30)
                        return self._process_search_results(company_name)
                except Exception as e:
                    self.logger.info(f"Could not find or click search button: {str(e)}")

                # Try pressing Enter key
                try:
                    keyword_input.send_keys(Keys.RETURN)
                    self.logger.info("Pressed Enter key to submit search")
                    self.wait_for_page_load(timeout=30)
                    return self._process_search_results(company_name)
                except Exception as e:
                    self.logger.info(f"Enter key submission failed: {str(e)}")

                # Fall back to form submission if both button click and Enter key fail
                self.logger.info("Falling back to form submission...")
                
                # Find the form element
                form = keyword_input.find_element(By.XPATH, "./ancestor::form")
                
                # Get the form's action URL and method
                form_action = form.get_attribute('action')
                form_method = form.get_attribute('method')
                
                # Ensure we maintain the core parameter
                if form_action and not 'core=esma_registers_priii_documents' in form_action:
                    if '?' in form_action:
                        form_action += '&core=esma_registers_priii_documents'
                    else:
                        form_action += '?core=esma_registers_priii_documents'
                
                # Submit using JavaScript to maintain URL parameters
                script = """
                var form = arguments[0];
                var action = arguments[1];
                form.action = action;
                form.submit();
                """
                self.driver.execute_script(script, form, form_action)
                self.logger.info("Submitted search form with parameters")
                
                # Wait for results with increased timeout
                self.wait_for_page_load(timeout=30)
                
                # Verify the URL still contains our parameter
                if "core=esma_registers_priii_documents" not in self.driver.current_url:
                    self.logger.warning("Search URL missing required parameter, retrying...")
                    self.driver.get(search_url)
                    return []
                
                # Process results
                results = self._process_search_results(company_name)
                return results
                
            except Exception as e:
                self.logger.error(f"Error during search: {str(e)}")
                return []
            
        except Exception as e:
            self.logger.error(f"Error in search_and_process: {str(e)}")
            return []
            
    def _process_search_results(self, keyword: str) -> List[Dict[str, Any]]:
        """Process search results and extract document information."""
        results = []
        
        try:
            # Wait for table to be present
            table = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
            )
            
            # Get initial row count
            rows = table.find_elements(By.TAG_NAME, "tr")[1:]  # Skip header row
            self.logger.info(f"Found {len(rows)} result rows")
            
            if not rows:
                self.logger.warning("No documents found")
                return results

            # Process each row
            for i in range(len(rows)):
                try:
                    # Re-find the table and rows to avoid stale elements
                    table = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
                    )
                    rows = table.find_elements(By.TAG_NAME, "tr")[1:]  # Skip header row
                    row = rows[i]
                    
                    # Wait for cells to be present and visible
                    cells = WebDriverWait(row, 10).until(
                        lambda r: [cell for cell in r.find_elements(By.TAG_NAME, "td") if cell.is_displayed()]
                    )
                    
                    if len(cells) != 11:
                        self.logger.warning(f"Unexpected number of cells in row: {len(cells)}")
                        continue

                    # Extract document information
                    doc_info = {
                        'country': cells[0].get_attribute('textContent').strip(),
                        'document_type': cells[1].get_attribute('textContent').strip(),
                        'document_subtype': cells[2].get_attribute('textContent').strip(),
                        'approval_date': cells[3].get_attribute('textContent').strip(),
                        'issuer': cells[4].get_attribute('textContent').strip(),
                        'isin': cells[5].get_attribute('textContent').strip(),
                        'home_member_state': cells[6].get_attribute('textContent').strip(),
                        'host_member_state': cells[7].get_attribute('textContent').strip(),
                        'publication_date': cells[8].get_attribute('textContent').strip()
                    }

                    # Look for PDF link in the last cell
                    last_cell = cells[-1]
                    pdf_link = None

                    try:
                        # First try to find direct PDF links
                        links = last_cell.find_elements(By.CSS_SELECTOR, 
                            "a[href*='.pdf'], a[href*='download'], a[onclick*='download'], a[onclick*='getDocument'], a[href]")
                        
                        for link in links:
                            href = link.get_attribute('href')
                            onclick = link.get_attribute('onclick')
                            
                            if href:
                                if '.pdf' in href.lower() or 'download' in href.lower():
                                    pdf_link = href
                                    self.logger.info(f"Found direct PDF link: {pdf_link}")
                                    break
                                else:
                                    # Click the link to navigate to document detail page
                                    current_url = self.driver.current_url
                                    link.click()
                                    
                                    # Wait for page load and any dynamic content
                                    WebDriverWait(self.driver, 10).until(
                                        lambda d: d.current_url != current_url
                                    )
                                    time.sleep(2)  # Wait for dynamic content to load
                                    
                                    # Look for PDF download link in viewer or main document area
                                    try:
                                        # Check for iframe first
                                        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                                        if iframes:
                                            for iframe in iframes:
                                                try:
                                                    self.driver.switch_to.frame(iframe)
                                                    pdf_elements = self.driver.find_elements(By.CSS_SELECTOR,
                                                        "a[href*='.pdf'], a[href*='download'], button[onclick*='download'], " +
                                                        "a[onclick*='getDocument'], a[onclick*='downloadDocument'], " +
                                                        "button[onclick*='getDocument'], button[onclick*='downloadDocument']")
                                                    if pdf_elements:
                                                        pdf_link = pdf_elements[0].get_attribute('href')
                                                        if not pdf_link:
                                                            # Try to get the link from onclick attribute
                                                            onclick = pdf_elements[0].get_attribute('onclick')
                                                            if onclick:
                                                                # Extract URL from onclick if possible
                                                                match = re.search(r"'(https?://[^']+)'", onclick)
                                                                if match:
                                                                    pdf_link = match.group(1)
                                                                else:
                                                                    # Click the element and try to get URL
                                                                    pdf_elements[0].click()
                                                                    time.sleep(1)
                                                                    pdf_link = self.driver.current_url
                                                        break
                                                finally:
                                                    self.driver.switch_to.default_content()
                                        
                                        # If no PDF found in iframes, check main document
                                        if not pdf_link:
                                            # Try multiple selectors for PDF links
                                            selectors = [
                                                "a[href*='.pdf']",
                                                "a[href*='download']",
                                                "button[onclick*='download']",
                                                "a[onclick*='getDocument']",
                                                "a[onclick*='downloadDocument']",
                                                "button[onclick*='getDocument']",
                                                "button[onclick*='downloadDocument']",
                                                "a[href*='document']",
                                                "a[href*='view']",
                                                "button[onclick*='view']"
                                            ]
                                            
                                            for selector in selectors:
                                                pdf_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                                                if pdf_elements:
                                                    element = pdf_elements[0]
                                                    pdf_link = element.get_attribute('href')
                                                    if not pdf_link:
                                                        onclick = element.get_attribute('onclick')
                                                        if onclick:
                                                            match = re.search(r"'(https?://[^']+)'", onclick)
                                                            if match:
                                                                pdf_link = match.group(1)
                                                            else:
                                                                # Click and get URL
                                                                element.click()
                                                                time.sleep(1)
                                                                pdf_link = self.driver.current_url
                                                    if pdf_link:
                                                        break
                                    
                                    except Exception as e:
                                        self.logger.error(f"Error finding PDF in document page: {str(e)}")
                                    
                                    # Go back to results page
                                    self.driver.back()
                                    
                                    # Re-find table elements
                                    table = WebDriverWait(self.driver, 10).until(
                                        EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
                                    )
                                    rows = table.find_elements(By.TAG_NAME, "tr")[1:]
                                    row = rows[i]
                                    cells = row.find_elements(By.TAG_NAME, "td")
                                    last_cell = cells[-1]
                                    
                                    if pdf_link:
                                        self.logger.info(f"Found PDF link in document page: {pdf_link}")
                                        break
                            
                            elif onclick and ('download' in onclick.lower() or 'getdocument' in onclick.lower()):
                                # Click the element to trigger the download
                                link.click()
                                time.sleep(2)  # Wait for potential redirect
                                
                                # Check if we're on a PDF page
                                if self.driver.current_url.endswith('.pdf'):
                                    pdf_link = self.driver.current_url
                                    self.logger.info(f"Found PDF link after click: {pdf_link}")
                                    
                                # Go back to results page
                                self.driver.back()
                                break
                    
                    except Exception as e:
                        self.logger.error(f"Error finding PDF link: {str(e)}")
                        continue

                    if pdf_link:
                        doc_info['pdf_url'] = pdf_link
                        try:
                            # Try to download the PDF
                            if self.download_pdf(pdf_link, doc_info['issuer'], doc_info['document_type'], doc_info['approval_date']):
                                doc_info['download_status'] = 'success'
                            else:
                                doc_info['download_status'] = 'failed'
                                self.error_tracking['download_errors'].append(f"Failed to download PDF for {doc_info['issuer']}")
                        except Exception as e:
                            self.logger.error(f"Error downloading PDF: {str(e)}")
                            doc_info['download_status'] = 'failed'
                            self.error_tracking['download_errors'].append(f"Error downloading PDF for {doc_info['issuer']}: {str(e)}")
                    else:
                        doc_info['download_status'] = 'no_pdf_found'
                        self.error_tracking['download_errors'].append(f"No PDF link found for {doc_info['issuer']}")

                    results.append(doc_info)

                except StaleElementReferenceException:
                    self.logger.error("Stale element reference while processing row")
                    continue
                except Exception as e:
                    self.logger.error(f"Error processing row: {str(e)}")
                    self.error_tracking['search_errors'].append(str(e))
                    continue

        except Exception as e:
            self.logger.error(f"Error processing search results: {str(e)}")
            self.error_tracking['search_errors'].append(str(e))
            
        return results

    def _find_pdf_in_viewer(self) -> Optional[str]:
        """Find PDF download link in document viewer."""
        # List of selectors to try
        viewer_selectors = [
            "div[id*='viewer'] a[href*='.pdf']",
            "div[id*='viewer'] a[href*='download']",
            "div[id*='viewer'] button[onclick*='download']",
            "div[id*='viewer'] a[onclick*='download']",
            "div[id*='viewer'] a[onclick*='getDocument']",
            "div[class*='viewer'] a[href*='.pdf']",
            "div[class*='viewer'] a[href*='download']",
            "div[class*='viewer'] button[onclick*='download']",
            "div[class*='document'] a[href*='.pdf']",
            "div[class*='document'] a[href*='download']",
            "div[class*='document'] button[onclick*='download']",
            "div[class*='document'] a[onclick*='download']",
            "div[class*='document'] a[onclick*='getDocument']"
        ]
        
        # Check for iframe first
        iframes = self.driver.find_elements(By.CSS_SELECTOR, "iframe[src*='viewer']")
        if iframes:
            self.driver.switch_to.frame(iframes[0])
            try:
                for selector in viewer_selectors:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        for element in elements:
                            href = element.get_attribute('href')
                            if href:
                                self.logger.info(f"Found PDF link in iframe via {selector}")
                                return href
            finally:
                self.driver.switch_to.default_content()
        
        # Try selectors in main document
        for selector in viewer_selectors:
            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                for element in elements:
                    href = element.get_attribute('href')
                    if href:
                        self.logger.info(f"Found PDF link in main area via href: {href}")
                        return href
                    onclick = element.get_attribute('onclick')
                    if onclick:
                        self.logger.info(f"Found PDF link in main area via onclick: {onclick}")
                        return onclick
        
        # Fallback to any download link
        elements = self.driver.find_elements(By.CSS_SELECTOR, 
            "a[href*='.pdf'], a[href*='download'], button[onclick*='download'], a[onclick*='download'], a[onclick*='getDocument']")
        
        if elements:
            for element in elements:
                href = element.get_attribute('href')
                if href:
                    self.logger.info(f"Found PDF link in main area via href: {href}")
                    return href
                onclick = element.get_attribute('onclick')
                if onclick:
                    self.logger.info(f"Found PDF link in main area via onclick: {onclick}")
                    return onclick
        
        return None