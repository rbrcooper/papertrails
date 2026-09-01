"""
ESMA Web Scraper
---------------
A web scraper for extracting prospectus documents from the ESMA (European Securities and Markets Authority) website.

**ONLY EVER USE THIS WEBSITE**: https://registers.esma.europa.eu/publication/searchRegister?core=esma_registers_priii_securities

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
import base64
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
from urllib.parse import urljoin, urlparse
from .pipeline_components.validators import classify_doc_tier, select_esma_rows, _parse_doc_type_code

# Constants for selectors (Prospectus III Securities register)
SECURITIES_URL = "https://registers.esma.europa.eu/publication/searchRegister?core=esma_registers_priii_securities"
DOCUMENTS_URL = "https://registers.esma.europa.eu/publication/searchRegister?core=esma_registers_priii_documents"
LEI_INPUT_SELECTOR = "input[name='issuer_lei']"
ISIN_INPUT_SELECTOR = "input[name='sec_isin']"
KEYWORD_INPUT_ID = "keywordField"
ISSUER_NAME_INPUT_SELECTOR = f"#{KEYWORD_INPUT_ID}"
SEARCH_INPUT_ID = KEYWORD_INPUT_ID
SEARCH_BUTTON_ID = "searchSolrButton"
MAX_BOND_ISIN_SEARCHES = 10  # L2 ISIN audit only; PaperTrails poll is LEI-first
MAX_LEI_SEARCHES = 10
RESULTS_CONTAINER_ID = "resultsTable"
RESULTS_TABLE_ID = "resultsTable"  # wrapper; data table is nested (#T01)
RESULTS_DATA_ROW_SELECTOR = "#resultsTable table tbody tr"
SECURITIES_DETAILS_CORE = "esma_registers_priii_securities"
COOKIE_ACCEPT_SELECTOR = "//a[text()='OK'] | //button[contains(text(), 'Accept')]" 
RESULTS_PER_PAGE_DROPDOWN_ID = "tablePageSize"
SOLR_SECURITIES_URL = "https://registers.esma.europa.eu/solr/esma_registers_priii_securities/select"
ESMA_REGISTERS_HOST = "registers.esma.europa.eu"
ESMA_REGISTERS_ORIGIN = "https://registers.esma.europa.eu"
ESMA_DOWNLOAD_PATH = "/publication/downloadFile"
DEFAULT_CHROME_USER_DATA_DIR = Path("data/chrome_profile")
ESMA_COOKIE_JAR_NAME = "esma_cookies.json"


def admitted_esma_download_url(url: Any) -> str:
    """Admit only https://registers.esma.europa.eu/publication/downloadFile[?...].

    Relative paths are joined to that origin first. Hostname must match exactly
    (not suffix/contains). Returns the canonical URL, or "" if rejected.
    """
    if not isinstance(url, str):
        return ""
    raw = url.strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if not parsed.netloc:
        raw = urljoin(ESMA_REGISTERS_ORIGIN, raw)
        parsed = urlparse(raw)
    if parsed.scheme != "https":
        return ""
    if parsed.hostname != ESMA_REGISTERS_HOST:
        return ""
    if parsed.path != ESMA_DOWNLOAD_PATH:
        return ""
    return raw


def chrome_user_data_dir_path(override: Any = None) -> Path:
    """Gitignored Chrome profile dir (cookies persist across runs)."""
    if override:
        return Path(override).expanduser()
    env = (os.environ.get("ESMA_CHROME_USER_DATA_DIR") or "").strip()
    if env:
        return Path(env).expanduser()
    return Path(DEFAULT_CHROME_USER_DATA_DIR)


def esma_cookie_jar_path(override: Any = None, *, user_data_dir: Any = None) -> Path:
    """JSON cookie jar under the Chrome profile dir (not committed)."""
    if override:
        return Path(override).expanduser()
    env = (os.environ.get("ESMA_COOKIE_JAR") or "").strip()
    if env:
        return Path(env).expanduser()
    return Path(user_data_dir or chrome_user_data_dir_path()) / ESMA_COOKIE_JAR_NAME


def _esma_cookie_domain_ok(domain: Any) -> bool:
    d = str(domain or "").lstrip(".").lower()
    if not d:
        return True
    return d == ESMA_REGISTERS_HOST or d == "esma.europa.eu" or d.endswith(".esma.europa.eu")


def _iter_cookie_records(cookies: Any) -> List[Dict[str, Any]]:
    if cookies is None:
        return []
    if isinstance(cookies, dict):
        inner = cookies.get("cookies")
        if isinstance(inner, list):
            return [c for c in inner if isinstance(c, dict)]
        if "name" in cookies and "value" in cookies:
            return [cookies]
        return [
            {"name": str(k), "value": str(v), "domain": ESMA_REGISTERS_HOST}
            for k, v in cookies.items()
            if k
        ]
    if isinstance(cookies, list):
        return [c for c in cookies if isinstance(c, dict)]
    return []


def selenium_cookies_to_requests(cookies: Any) -> Dict[str, str]:
    """Name→value map for requests, ESMA-host only; skip expired."""
    now = time.time()
    out: Dict[str, str] = {}
    for c in _iter_cookie_records(cookies):
        name = c.get("name")
        if not name:
            continue
        if not _esma_cookie_domain_ok(c.get("domain")):
            continue
        expiry = c.get("expiry", c.get("expires"))
        if expiry is not None:
            try:
                if float(expiry) < now:
                    continue
            except (TypeError, ValueError):
                pass
        out[str(name)] = str(c.get("value") or "")
    return out


def dump_cookie_jar(path: Any, cookies: Any) -> Path:
    """Write ESMA cookies to disk. Does not log values."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    records: List[Dict[str, Any]] = []
    for c in _iter_cookie_records(cookies):
        name = c.get("name")
        if not name:
            continue
        domain = c.get("domain") or ESMA_REGISTERS_HOST
        if not _esma_cookie_domain_ok(domain):
            continue
        rec: Dict[str, Any] = {
            "name": str(name),
            "value": str(c.get("value") or ""),
            "domain": str(domain),
        }
        for k in ("path", "secure", "httpOnly", "expiry", "sameSite"):
            if k in c and c[k] is not None:
                rec[k] = c[k]
        records.append(rec)
    payload = {
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "host": ESMA_REGISTERS_HOST,
        "cookies": records,
    }
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(dest)
    return dest


def load_cookie_jar(path: Any) -> Dict[str, str]:
    src = Path(path)
    if not src.is_file():
        return {}
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return selenium_cookies_to_requests(data)


def cookie_jar_is_usable(path: Any) -> bool:
    return bool(load_cookie_jar(path))


def apply_cookie_jar_to_driver(driver: Any, cookies: Any) -> int:
    """add_cookie each ESMA record. Caller must already be on the ESMA origin."""
    if not driver:
        return 0
    added = 0
    for c in _iter_cookie_records(cookies):
        if not c.get("name"):
            continue
        if not _esma_cookie_domain_ok(c.get("domain")):
            continue
        payload: Dict[str, Any] = {"name": c["name"], "value": c.get("value") or ""}
        for k in ("domain", "path", "secure", "httpOnly", "expiry", "sameSite"):
            if k in c and c[k] is not None:
                payload[k] = c[k]
        try:
            driver.add_cookie(payload)
            added += 1
        except Exception:
            continue
    return added


def probe_downloadfile_pdf(
    url: str,
    cookies: Optional[Dict[str, str]] = None,
    timeout: int = 30,
) -> Tuple[bool, bytes]:
    """One windowless GET of an admitted downloadFile URL. Returns (is_pdf, head)."""
    admitted = admitted_esma_download_url(url)
    if not admitted:
        return False, b""
    try:
        resp = requests.get(
            admitted,
            headers={
                "User-Agent": "Mozilla/5.0 PaperTrails-session-probe",
                "Referer": SECURITIES_URL,
            },
            cookies=cookies or None,
            timeout=timeout,
        )
        head = bytes(resp.content[:8])
        return head.startswith(b"%PDF"), head
    except requests.RequestException:
        return False, b""


def resolve_download_url(row: Dict) -> str:
    """Return downloadFile URL only (never the details-page href)."""
    dl = (row.get("download_url") or "").strip()
    admitted = admitted_esma_download_url(dl)
    if admitted:
        return admitted
    url = (row.get("url") or "").strip()
    return admitted_esma_download_url(url)


def download_url_from_rfss(rfss: Any) -> str:
    """Build downloadFile URL from Solr sec_docRfssId ('fileId,checksum')."""
    if not isinstance(rfss, str) or "," not in rfss:
        return ""
    file_id, file_hash = rfss.split(",", 1)
    file_id, file_hash = file_id.strip(), file_hash.strip()
    if not file_id.isdigit() or not file_hash:
        return ""
    return (
        "https://registers.esma.europa.eu/publication/downloadFile"
        f"?fileId={file_id}&checksum={file_hash}"
    )


def attach_solr_download_urls(rows: List[Dict], solr_rows: List[Dict]) -> int:
    """Copy Solr downloadFile URLs onto UI rows matched by docId.

    The securities table only exposes a details href. Solr sec_docRfssId is the
    fileId/checksum that actually returns %PDF.
    """
    by_doc: Dict[str, str] = {}
    for s in solr_rows:
        did = str(s.get("doc_id") or s.get("sec_dbId") or s.get("id") or "").strip()
        dl = resolve_download_url(s) or download_url_from_rfss(s.get("sec_docRfssId"))
        if did and dl:
            by_doc[did] = dl
    attached = 0
    for r in rows:
        if resolve_download_url(r):
            continue
        did = str(r.get("doc_id") or "").strip()
        if did in by_doc:
            r["download_url"] = by_doc[did]
            attached += 1
    return attached

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
    def __init__(
        self,
        download_dir=None,
        debug_mode=True,
        headless=True,
        chrome_user_data_dir=None,
        cookie_jar_path=None,
    ):
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
        self.base_url = SECURITIES_URL
        self.documents_url = DOCUMENTS_URL
        self.headless = headless
        self.chrome_user_data_dir = chrome_user_data_dir_path(chrome_user_data_dir)
        self.cookie_jar_path = esma_cookie_jar_path(
            cookie_jar_path, user_data_dir=self.chrome_user_data_dir
        )
        try:
            self.chrome_user_data_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.logger.warning("Could not create Chrome profile dir %s: %s", self.chrome_user_data_dir, e)
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

        self._last_search_isin: Optional[str] = None
        self._last_search_lei: Optional[str] = None

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
                version_main = self._detect_chrome_major_version(default=148)
                self.logger.info(f"Detected Chrome major version: {version_main}")
                # user-data-dir is on options so uc keeps the profile (no temp wipe on quit).
                self.driver = uc.Chrome(options=options, version_main=version_main)
                
                self.logger.info("Chrome driver initialized successfully")
                try:
                    # Avoid Selenium "script timeout" on slower ESMA pages
                    self.driver.set_script_timeout(180)
                    self.driver.set_page_load_timeout(180)
                except Exception:
                    pass
                self.wait = WebDriverWait(self.driver, self.default_wait_timeout)
                return
            except Exception as e:
                self.logger.error(f"Attempt {attempt} failed to initialize Chrome driver: {str(e)}", exc_info=True)
                # Cleanup driver if partially initialized
                if self.driver is not None:
                    try:
                        self.driver.quit()
                    except Exception:
                        pass
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

        profile = Path(
            getattr(self, "chrome_user_data_dir", None) or chrome_user_data_dir_path()
        )
        try:
            profile.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        options.add_argument(f"--user-data-dir={profile.resolve()}")
        self.logger.info("Chrome user-data-dir: %s", profile.resolve())

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

    def _detect_chrome_major_version(self, default: int = 148) -> int:
        """Best-effort detection of installed Chrome major version on Windows.

        Prefer registry detection to avoid spawning Chrome. Falls back to `default`.
        """
        # 1) Environment override (useful when Chrome auto-updates)
        env_major = os.environ.get("CHROME_MAJOR")
        if env_major:
            try:
                return int(env_major)
            except Exception:
                pass

        # 2) Registry keys (fast, no process spawn)
        try:
            import winreg  # type: ignore

            reg_candidates = [
                (winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon", "version"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Google\Chrome\BLBeacon", "version"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Google\Chrome\BLBeacon", "version"),
            ]
            for hive, key_path, value_name in reg_candidates:
                try:
                    with winreg.OpenKey(hive, key_path) as k:
                        ver, _ = winreg.QueryValueEx(k, value_name)
                    parts = re.findall(r"(\d+)\.", str(ver))
                    if parts:
                        return int(parts[0])
                except Exception:
                    continue
        except Exception:
            pass

        # 3) Last resort: try parsing chrome.exe --version (may be noisy on some installs)
        try:
            candidates = [
                Path(r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"),
                Path(r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"),
                Path(os.path.expandvars(r"%LOCALAPPDATA%\\Google\\Chrome\\Application\\chrome.exe")),
            ]
            for exe in candidates:
                if exe.exists():
                    try:
                        import subprocess

                        out = subprocess.check_output([str(exe), "--version"], text=True, timeout=3)
                        parts = re.findall(r"(\d+)\.", out)
                        if parts:
                            return int(parts[0])
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

    def persist_session_cookies(self) -> Optional[Path]:
        """Dump live Selenium cookies to the JSON jar (ESMA host only)."""
        path = getattr(self, "cookie_jar_path", None)
        driver = getattr(self, "driver", None)
        if not path or not driver:
            return None
        try:
            raw = driver.get_cookies() or []
        except Exception as e:
            self.logger.debug("Could not read cookies to persist: %s", e)
            return None
        if not raw:
            return None
        try:
            dumped = dump_cookie_jar(path, raw)
            n = len(load_cookie_jar(dumped))
            self.logger.info("Persisted ESMA cookie jar (%s cookies) to %s", n, dumped)
            return dumped
        except OSError as e:
            self.logger.debug("Could not dump cookie jar: %s", e)
            return None

    def _request_cookie_dict(self) -> Dict[str, str]:
        """Live driver cookies if present (and dump them); else disk jar."""
        live: Dict[str, str] = {}
        raw = None
        driver = getattr(self, "driver", None)
        if driver:
            try:
                raw = driver.get_cookies() or []
                live = selenium_cookies_to_requests(raw)
            except Exception as e:
                self.logger.debug("Could not get cookies from driver: %s", e)
        path = getattr(self, "cookie_jar_path", None)
        if raw and path:
            try:
                dump_cookie_jar(path, raw)
            except OSError as e:
                self.logger.debug("Could not dump cookie jar: %s", e)
        if live:
            return live
        if path:
            return load_cookie_jar(path)
        return {}

    def close(self):
        """Close the browser and clean up resources."""
        try:
            self.persist_session_cookies()
        except Exception:
            pass
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

    def search_by_isin(self, isin: str) -> bool:
        """Search Securities register using the dedicated ISIN field."""
        self._last_search_isin = isin.strip().upper() if isin else None
        return self.search_company(isin, search_mode="isin")

    def _wait_for_search_results_loaded(self, timeout: int = 40) -> bool:
        """Wait until the results table has rows or a no-results state is shown."""

        def _ready(driver):
            try:
                if driver.find_elements(By.CSS_SELECTOR, RESULTS_DATA_ROW_SELECTOR):
                    return True
            except Exception:
                pass
            try:
                body = driver.find_element(By.TAG_NAME, "body").text.lower()
                if "no results" in body or "no records" in body:
                    return True
            except Exception:
                pass
            return False

        try:
            WebDriverWait(self.driver, timeout).until(_ready)
            return True
        except TimeoutException:
            return False

    def fetch_securities_via_solr(
        self, isin: str = "", rows: int = 20, *, lei: str = ""
    ) -> List[Dict]:
        """Fetch securities rows from ESMA Solr by issuer_lei or sec_isin.

        L2 audit still calls this with an ISIN. PaperTrails discovery uses lei=.
        """
        lei = (lei or "").strip()
        isin = (isin or "").strip().upper()
        if lei:
            # issuer_lei: hits issuer-party records (no sec_isin / downloadFile).
            # Prospectus rows store the LEI on sec_issuerNameList as "Name - LEI".
            query = f"sec_issuerNameList:*{lei}*"
            label = f"sec_issuerNameList:*{lei}*"
        elif isin:
            query = f"sec_isin:{isin}"
            label = f"sec_isin:{isin}"
        else:
            return []
        try:
            resp = requests.get(
                SOLR_SECURITIES_URL,
                params={"q": query, "rows": rows, "wt": "json"},
                timeout=20,
            )
            resp.raise_for_status()
            payload = resp.json().get("response", {}) or {}
            num_found = int(payload.get("numFound") or 0)
            docs = payload.get("docs", [])
        except Exception as e:
            self.logger.warning(f"Solr fallback failed for {label}: {e}")
            return []

        out: List[Dict] = []
        for doc in docs:
            issuer_raw = doc.get("sec_issuerNameList") or ""
            if isinstance(issuer_raw, list):
                issuer_join = " | ".join(str(x) for x in issuer_raw if x)
                issuer_raw0 = str(issuer_raw[0]) if issuer_raw else ""
            else:
                issuer_join = str(issuer_raw)
                issuer_raw0 = str(issuer_raw)
            issuer_name = issuer_raw0.split(" - ")[0].strip() if issuer_raw0 else ""
            issuer_lei = ""
            for key in ("issuer_lei", "sec_issuerLei", "sec_lei"):
                v = doc.get(key)
                if isinstance(v, list):
                    v = v[0] if v else ""
                if v:
                    issuer_lei = str(v).strip()
                    break
            if not issuer_lei and lei:
                issuer_lei = lei
            date_raw = doc.get("sec_docLastUpdateDate") or doc.get("sec_approvalFilingDate") or ""
            date_str = str(date_raw)[:10] if date_raw else ""
            doc_type = doc.get("sec_docTypeDesc") or doc.get("sec_docType") or ""
            doc_code = doc.get("sec_docType") or ""
            download_url = download_url_from_rfss(doc.get("sec_docRfssId") or "")
            doc_db_id = doc.get("sec_dbId") or doc.get("id")
            details_url = ""
            if doc_db_id:
                details_url = (
                    "https://registers.esma.europa.eu/publication/details"
                    f"?core={SECURITIES_DETAILS_CORE}&docId={doc_db_id}"
                )
            row = {
                "issuer_name": issuer_name,
                "issuer_name_raw": issuer_join,
                "issuer_lei": issuer_lei,
                "queried_lei": lei or "",
                "doc_type": doc_type,
                "doc_type_code": doc_code,
                "date": date_str,
                "isin": doc.get("sec_isin") or isin,
                "doc_id": str(doc_db_id) if doc_db_id else "",
                "download_url": download_url,
                "details_url": details_url,
                "url": download_url or details_url,
                "filename": doc.get("sec_natDocId") or "",
                "register_source": "solr",
                "already_seen": False,
                "doc_tier": classify_doc_tier(doc_code, doc_type),
                "solr_num_found": num_found,
            }
            if self.current_company and issuer_name:
                row["fuzzy_score"] = fuzz.token_set_ratio(self.current_company, issuer_name)
            else:
                row["fuzzy_score"] = 0
            if row.get("url") and row["url"] not in self.seen_urls:
                out.append(row)
        self.logger.info(
            "Solr %s numFound=%s returned=%s", label, num_found, len(out)
        )
        return out

    @retry_on_failure() # Apply the defined decorator
    def search_company(self, search_term: str, is_lei: bool = False, search_mode: str = "auto"):
        """Search ESMA Securities register by LEI, ISIN, or issuer name."""
        if search_mode != "isin":
            self._last_search_isin = None
        if is_lei:
            self._last_search_lei = (search_term or "").strip() or None
        else:
            self._last_search_lei = None
        if search_mode == "isin":
            field_desc = "ISIN"
        elif is_lei:
            field_desc = "LEI"
        else:
            field_desc = "name"
        self.logger.info(f"Searching for {field_desc}: '{search_term}'")
        if self.check_session_health():
            self.navigate_to_search()

        if search_mode == "isin":
            search_input_locator = (By.CSS_SELECTOR, ISIN_INPUT_SELECTOR)
        elif is_lei:
            search_input_locator = (By.CSS_SELECTOR, LEI_INPUT_SELECTOR)
        else:
            search_input_locator = (By.ID, KEYWORD_INPUT_ID)
        search_button_locator = (By.ID, SEARCH_BUTTON_ID)
        
        try:
            # 1. Find and clear the search input field
            self.logger.debug(f"Waiting for search input field '{search_input_locator}'...")
            search_input = self.wait.until(
                EC.element_to_be_clickable(search_input_locator),
                message=f"Search input '{search_input_locator}' not found or not clickable."
            )
            
            # Handle cookie banner if it appears and blocks input
            try:
                cookie_btn = self.driver.find_elements(By.XPATH, COOKIE_ACCEPT_SELECTOR)
                if cookie_btn and cookie_btn[0].is_displayed():
                    self.logger.info("Closing cookie banner...")
                    cookie_btn[0].click()
                    time.sleep(1)
            except Exception:
                pass

            self.logger.debug("Search input found. Clearing and sending keys...")
            search_input.clear()
            search_input.send_keys(search_term)
            self.logger.debug(f"Entered '{search_term}' into {field_desc} search field.")
            
            # Brief random delay before clicking search
            self.random_delay(0.5, 1.5)

            # 2. Find and click the search button
            self.logger.debug(f"Waiting for search button '{search_button_locator}'...")
            search_button = self.wait.until(
                EC.element_to_be_clickable(search_button_locator),
                message=f"Search button '{search_button_locator}' not clickable."
            )
            self.logger.debug("Search button found. Clicking...")
            # Prefer native click to avoid long-running JS execution on ESMA
            try:
                search_button.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", search_button)
            self.requests_count += 1 # Count actions that trigger server requests
            self.logger.info(f"Clicked search button for '{search_term}'.")

            # 3. Wait for search results to load (or indicate no results)
            self.logger.debug("Waiting for search results table content to load...")
            # Option A: Wait for the results table container (Original - timed out)
            # self.wait.until(
            #     EC.presence_of_element_located(results_table_locator),
            #     message="Results table did not appear after search."
            # )
            # Wait for the results container/table to exist, then proceed even if 0 rows.
            results_container_locator = (By.ID, RESULTS_CONTAINER_ID)
            self.wait.until(
                EC.presence_of_element_located(results_container_locator),
                message="Results table container did not appear after search."
            )
            self.logger.debug("Results table container detected.")
            self._wait_for_search_results_loaded(timeout=20)

            # Option C: Wait for either results table OR a 'no results' message (More complex)
            # ... (keep commented out)
                
            self.logger.info(f"Search completed for '{search_term}'.")
            return True # Indicate search completed, results (or empty table) are present

        except (TimeoutException, NoSuchElementException, ElementClickInterceptedException, ElementNotInteractableException, StaleElementReferenceException) as e:
            self.logger.error(f"Error during search for '{search_term}': {type(e).__name__} - {str(e)}")
            if self.debug_mode:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.take_screenshot(f"error_search_{search_term[:20]}_{timestamp}.png")
                self.save_page_source(f"error_search_{search_term[:20]}_{timestamp}.html")
            # Consider if returning False or raising the exception is better here
            # Returning False might allow processing to continue with the next company
            return False # Indicate search failed
        except Exception as e:
            self.logger.error(f"Unexpected error during search for '{search_term}': {e}", exc_info=True)
            if self.debug_mode:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.take_screenshot(f"unexpected_error_search_{search_term[:20]}_{timestamp}.png")
                self.save_page_source(f"unexpected_error_search_{search_term[:20]}_{timestamp}.html")
            raise # Re-raise unexpected errors

    def _get_results_data_rows(self, timeout: int = 40) -> List:
        """Return securities register data rows (nested table under #resultsTable)."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, RESULTS_DATA_ROW_SELECTOR))
            )
        except TimeoutException:
            return []
        return self.driver.find_elements(By.CSS_SELECTOR, RESULTS_DATA_ROW_SELECTOR)

    @staticmethod
    def _build_securities_column_map(table_element) -> Dict[str, int]:
        mapping: Dict[str, int] = {}
        try:
            headers = table_element.find_elements(By.CSS_SELECTOR, "thead th[id]")
            for idx, th in enumerate(headers):
                col_id = (th.get_attribute("id") or "").strip()
                if col_id:
                    mapping[col_id] = idx
        except Exception:
            pass
        return mapping

    def process_results(self, company_name: str) -> List[Dict]:
        """Process only the current results page. Assumes page size already set to 100."""
        self.logger.info(f"Processing current results page for company: {company_name}")
        documents: List[Dict] = []

        try:
            self.wait.until(
                EC.presence_of_element_located((By.ID, RESULTS_CONTAINER_ID)),
                message="Results container not found.",
            )
            rows = self._get_results_data_rows(timeout=40)
            self.logger.info(f"Found {len(rows)} rows on current page.")
            column_map: Dict[str, int] = {}
            if rows:
                try:
                    table = rows[0].find_element(By.XPATH, "./ancestor::table[1]")
                    column_map = self._build_securities_column_map(table)
                except Exception:
                    column_map = {}

            for idx, row in enumerate(rows):
                try:
                    row_data = self.get_document_details(row, column_map=column_map)
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

        if not documents and self._last_search_isin:
            documents = self.fetch_securities_via_solr(self._last_search_isin)
        elif not documents and self._last_search_lei:
            documents = self.fetch_securities_via_solr(lei=self._last_search_lei)

        return documents

    def accept_cookies(self):
        """Attempt to find and click the cookie acceptance button."""
        self.logger.debug("Checking for cookie acceptance button...")
        # Use a more flexible XPath that handles common variations
        cookie_button_locator = (By.XPATH, COOKIE_ACCEPT_SELECTOR)
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

    def get_document_details(
        self, result_element, column_map: Optional[Dict[str, int]] = None
    ) -> Optional[Dict]:
        """Extract document details from a single securities register row."""
        details = {
            'issuer_name': '', 'doc_type': '', 'date': '', 'url': '', 'filename': '',
            'doc_id': '', 'download_url': '',
        }
        try:
            cells = result_element.find_elements(By.TAG_NAME, "td")
            if len(cells) < 5:
                self.logger.warning(
                    "Row has too few cells (%s), skipping.", len(cells)
                )
                return None

            col = column_map or {}

            def get_by_col(col_id: str, fallback_idx: Optional[int] = None) -> str:
                idx = col.get(col_id)
                if idx is None and fallback_idx is not None:
                    idx = fallback_idx
                if idx is None or idx >= len(cells):
                    return ""
                return cells[idx].text.strip()

            full_issuer = get_by_col("sec_issuerNameList", 2)
            if " - " in full_issuer:
                details['issuer_name'] = full_issuer.split(" - ")[0].strip()
            else:
                details['issuer_name'] = full_issuer

            details['isin'] = get_by_col("sec_isin", 1)
            details['doc_type'] = get_by_col("sec_docTypeDesc", 5)
            details['date'] = get_by_col("sec_approvalFilingDate", 8) or get_by_col(
                "sec_docLastUpdateDate", 9
            )
            details['doc_type_code'] = _parse_doc_type_code(None, details.get('doc_type'))
            details['doc_tier'] = classify_doc_tier(details['doc_type_code'], details.get('doc_type'))
            details['register_source'] = 'securities'

            details_href = ""
            download_href = ""
            for a in result_element.find_elements(By.TAG_NAME, "a"):
                href = a.get_attribute('href') or ""
                if not href:
                    continue
                if "downloadFile" in href:
                    download_href = href
                    continue
                if href.startswith("details") or "details?" in href:
                    if not details_href:
                        details_href = (
                            f"https://registers.esma.europa.eu/publication/{href.lstrip('/')}"
                            if not href.startswith("http")
                            else href
                        )

            details["download_url"] = download_href
            details["details_url"] = details_href
            details["url"] = download_href or details_href
            if details_href and "docId=" in details_href:
                m = re.search(r"docId=(\d+)", details_href)
                if m:
                    details["doc_id"] = m.group(1)
            
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

    def download_via_details_page(
        self,
        doc_id: str,
        doc_type_hint: Optional[str] = None,
        date_hint: Optional[str] = None,
        core: str = SECURITIES_DETAILS_CORE,
    ) -> Optional[str]:
        """Open ESMA document details (requires search-session cookie) and download linked PDF."""
        if not self.driver or not doc_id:
            return None
        doc_id = str(doc_id).strip()
        details_url = (
            f"https://registers.esma.europa.eu/publication/details"
            f"?core={core}&docId={doc_id}"
        )
        self.logger.info(f"Details-page download for docId={doc_id}")
        try:
            if "searchRegister" not in (self.driver.current_url or ""):
                self.navigate_to_search()
                time.sleep(2)
            self.driver.execute_script(
                "if (typeof setNavCookie === 'function') setNavCookie();"
            )
            self.driver.get(details_url)
            time.sleep(4)
            download_links = []
            for a in self.driver.find_elements(By.CSS_SELECTOR, "a[href]"):
                href = a.get_attribute("href") or ""
                if "downloadFile" in href:
                    download_links.append(href)
            if not download_links:
                # Some pages embed download in onclick or form — scan page source.
                for m in re.finditer(
                    r"downloadFile\?fileId=\d+&checksum=[a-f0-9]+", self.driver.page_source
                ):
                    download_links.append(
                        "https://registers.esma.europa.eu/publication/" + m.group(0)
                    )
            for href in download_links[:3]:
                path = self._download_binary_with_session(
                    href, doc_id=doc_id, doc_type_hint=doc_type_hint, date_hint=date_hint
                )
                if path:
                    return path
        except Exception as e:
            self.logger.warning(f"Details-page download failed for {doc_id}: {e}")
        return None

    def download_selected_row(self, row: Dict[str, Any]) -> Optional[str]:
        """HTTP downloadFile first; Selenium session cookies second. Never GET details HTML first."""
        details_href = (row.get("details_url") or row.get("url") or "").strip()
        doc_id = str(row.get("doc_id") or "").strip()
        if not doc_id.isdigit():
            m = re.search(r"docId=(\d+)", details_href)
            doc_id = m.group(1) if m else ""
        search_isin = (row.get("isin") or "").strip() or None

        if not resolve_download_url(row) and search_isin:
            attached = attach_solr_download_urls(
                [row], self.fetch_securities_via_solr(search_isin)
            )
            if attached:
                self.logger.info(
                    "Attached Solr downloadFile for docId=%s ISIN=%s",
                    doc_id or "?",
                    search_isin,
                )

        download_url = resolve_download_url(row)
        path = None
        if download_url:
            path = self.download_document(
                url=download_url,
                doc_id=doc_id or None,
                doc_type_hint=row.get("doc_type"),
                date_hint=row.get("date"),
            )
            if path:
                self.logger.info(
                    "HTTP downloadFile succeeded for docId=%s ISIN=%s",
                    doc_id or "?",
                    search_isin or "?",
                )
            elif search_isin and self.driver:
                try:
                    self.navigate_to_search()
                    if self.search_by_isin(search_isin):
                        time.sleep(2)
                        try:
                            self.driver.execute_script(
                                "if (typeof setNavCookie === 'function') setNavCookie();"
                            )
                        except Exception:
                            pass
                        path = self._download_binary_with_session(
                            download_url,
                            doc_id=doc_id or search_isin,
                            doc_type_hint=row.get("doc_type"),
                            date_hint=row.get("date"),
                        )
                        if path:
                            self.logger.info(
                                "Selenium-session download for docId=%s ISIN=%s",
                                doc_id or "?",
                                search_isin,
                            )
                except Exception as e:
                    self.logger.debug("ISIN-session download failed: %s", e)
        if not path and doc_id:
            path = self.download_via_details_page(
                doc_id,
                doc_type_hint=row.get("doc_type"),
                date_hint=row.get("date"),
            )
        if not path:
            self.logger.warning(
                "No PDF for docId=%s (downloadFile=%s)",
                doc_id or "?",
                bool(download_url),
            )
        return path

    def _download_binary_with_session(
        self,
        url: str,
        doc_id: str = None,
        doc_type_hint: Optional[str] = None,
        date_hint: Optional[str] = None,
    ) -> Optional[str]:
        """Download bytes using Selenium session cookies (after details navigation)."""
        url = admitted_esma_download_url(url)
        if not url or not self.driver:
            return None
        try:
            cookies = self._request_cookie_dict() or None
            headers = {"User-Agent": self.user_agent, "Referer": self.driver.current_url}
            resp = requests.get(url, headers=headers, cookies=cookies, timeout=90)
            resp.raise_for_status()
            if not resp.content[:5].startswith(b"%PDF"):
                self.logger.warning(
                    "Session download did not return PDF (head=%r, size=%s) for %s",
                    resp.content[:20],
                    len(resp.content),
                    url,
                )
                return None
            temp = self.download_dir / f"details_{doc_id or 'doc'}.pdf.part"
            temp.write_bytes(resp.content)
            content_hash = self.get_file_hash(temp)
            org_company = self.current_company or "UnknownCompany"
            organized, final_path = self.organize_file(
                temp,
                org_company,
                doc_type_hint=doc_type_hint,
                date_hint=date_hint,
                content_hash=content_hash,
            )
            if organized and final_path:
                if content_hash:
                    self.document_hashes[content_hash] = str(final_path)
                    self._save_document_hashes()
                return str(final_path)
        except Exception as e:
            self.logger.debug(f"Session download failed for {url}: {e}")
        return None

    def download_from_results_table(
        self,
        isin: Optional[str] = None,
        doc_type_hint: Optional[str] = None,
        date_hint: Optional[str] = None,
    ) -> Optional[str]:
        """Click the download link on the current results table (UI href may differ from Solr-built URL)."""
        if not self.driver:
            return None
        rows = self._get_results_data_rows(timeout=15)
        if not rows:
            self.logger.debug("No results table rows for row download.")
            return None
        target_isin = (isin or "").strip().upper()
        before = {p.resolve() for p in self.download_dir.rglob("*") if p.is_file()}
        for row in rows:
            details = self.get_document_details(row)
            if not details:
                continue
            row_isin = (details.get("isin") or "").strip().upper()
            if target_isin and row_isin and row_isin != target_isin:
                continue
            if details.get("doc_id"):
                path = self.download_via_details_page(
                    details["doc_id"],
                    doc_type_hint=doc_type_hint or details.get("doc_type"),
                    date_hint=date_hint or details.get("date"),
                )
                if path:
                    return path
            url = resolve_download_url(details) or (details.get("url") or "")
            if "downloadFile" not in url:
                continue
            # Prefer clicking the anchor (ESMA often requires in-page navigation).
            try:
                link = None
                for a in row.find_elements(By.TAG_NAME, "a"):
                    href = a.get_attribute("href") or ""
                    if "downloadFile" in href or "detailsUrl" in href:
                        link = a
                        if "downloadFile" in href:
                            break
                if link:
                    self.logger.info("Clicking results-table download link for %s", row_isin or isin)
                    try:
                        link.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", link)
                    deadline = time.time() + self.download_wait_time
                    while time.time() < deadline:
                        current = {p.resolve() for p in self.download_dir.rglob("*") if p.is_file()}
                        new_files = [
                            p for p in current - before
                            if not p.name.endswith(".crdownload") and not p.name.endswith(".part")
                        ]
                        for path in sorted(new_files, key=lambda p: p.stat().st_mtime, reverse=True):
                            try:
                                if path.read_bytes()[:5].startswith(b"%PDF"):
                                    content_hash = self.get_file_hash(path)
                                    org_company = self.current_company or "UnknownCompany"
                                    organized, final_path = self.organize_file(
                                        path,
                                        org_company,
                                        doc_type_hint=doc_type_hint or details.get("doc_type"),
                                        date_hint=date_hint or details.get("date"),
                                        content_hash=content_hash,
                                    )
                                    if organized and final_path:
                                        if content_hash:
                                            self.document_hashes[content_hash] = str(final_path)
                                            self._save_document_hashes()
                                        return str(final_path)
                            except OSError:
                                continue
                        time.sleep(1)
            except Exception as e:
                self.logger.debug(f"Table click download failed: {e}")
            return self.download_document(
                url=url,
                doc_id=details.get("isin") or details.get("issuer_name"),
                doc_type_hint=doc_type_hint or details.get("doc_type"),
                date_hint=date_hint or details.get("date"),
            )
        return None

    def _download_via_browser(
        self,
        url: str,
        doc_id: str = None,
        doc_type_hint: Optional[str] = None,
        date_hint: Optional[str] = None,
        timeout: int = 90,
    ) -> Optional[str]:
        """Fallback: trigger Chrome download for ESMA file URLs that return HTML via requests."""
        if not self.driver:
            return None
        self.logger.info(f"Browser download fallback for: {doc_id or url}")
        try:
            if "registers.esma.europa.eu" not in (self.driver.current_url or ""):
                self.navigate_to_search()
                time.sleep(2)
        except Exception:
            pass

        before = {p.resolve() for p in self.download_dir.rglob("*") if p.is_file()}
        try:
            self.driver.get(url)
        except Exception as e:
            self.logger.warning(f"Browser navigation to download URL failed: {e}")
            return None

        deadline = time.time() + timeout
        while time.time() < deadline:
            current = {p.resolve() for p in self.download_dir.rglob("*") if p.is_file()}
            new_files = [
                p for p in current - before
                if not p.name.endswith(".crdownload") and not p.name.endswith(".part")
            ]
            for path in sorted(new_files, key=lambda p: p.stat().st_mtime, reverse=True):
                try:
                    if path.read_bytes()[:5].startswith(b"%PDF"):
                        content_hash = self.get_file_hash(path)
                        org_company = self.current_company or "UnknownCompany"
                        organized, final_path = self.organize_file(
                            path,
                            org_company,
                            doc_type_hint=doc_type_hint,
                            date_hint=date_hint,
                            content_hash=content_hash,
                        )
                        if organized and final_path:
                            if content_hash:
                                self.document_hashes[content_hash] = str(final_path)
                                self._save_document_hashes()
                            return str(final_path)
                except OSError:
                    continue
            time.sleep(1)
        self.logger.warning(f"Browser download timed out for {url}")
        return None

    def _download_via_fetch(
        self,
        url: str,
        doc_id: str = None,
        doc_type_hint: Optional[str] = None,
        date_hint: Optional[str] = None,
    ) -> Optional[str]:
        """Download PDF bytes via in-page fetch() using the live browser session."""
        if not self.driver:
            return None
        self.logger.info(f"Session fetch download for: {doc_id or url}")
        try:
            if "registers.esma.europa.eu" not in (self.driver.current_url or ""):
                self.navigate_to_search()
                time.sleep(1)
        except Exception:
            pass

        script = """
        const url = arguments[0];
        const cb = arguments[arguments.length - 1];
        fetch(url, {credentials: 'include', redirect: 'follow'})
          .then(r => r.arrayBuffer())
          .then(buf => {
            const u8 = new Uint8Array(buf);
            let binary = '';
            const chunk = 0x8000;
            for (let i = 0; i < u8.length; i += chunk) {
              binary += String.fromCharCode.apply(null, u8.subarray(i, i + chunk));
            }
            cb(btoa(binary));
          })
          .catch(err => cb('ERROR:' + err));
        """
        try:
            b64 = self.driver.execute_async_script(script, url)
        except Exception as e:
            self.logger.warning(f"Session fetch script failed: {e}")
            return None

        if not b64 or (isinstance(b64, str) and b64.startswith("ERROR:")):
            self.logger.warning(f"Session fetch failed: {b64}")
            return None

        try:
            raw = base64.b64decode(b64)
        except Exception as e:
            self.logger.warning(f"Session fetch base64 decode failed: {e}")
            return None

        if not raw[:5].startswith(b"%PDF"):
            self.logger.warning(
                "Session fetch did not return PDF (head=%r, size=%s)",
                raw[:20],
                len(raw),
            )
            return None

        base_name = doc_id if doc_id else hashlib.md5(url.encode()).hexdigest()
        temp_download_path = self.download_dir / f"esma_fetch_{base_name}.pdf.part"
        temp_download_path.write_bytes(raw)
        content_hash = hashlib.sha256(raw).hexdigest()
        org_company_name = self.current_company if self.current_company else "UnknownCompany"
        organized_successfully, final_path = self.organize_file(
            temp_download_path,
            org_company_name,
            doc_type_hint=doc_type_hint,
            date_hint=date_hint,
            content_hash=content_hash,
        )
        if organized_successfully and final_path:
            self.document_hashes[content_hash] = str(final_path)
            self._save_document_hashes()
            return str(final_path)
        if temp_download_path.exists():
            temp_download_path.unlink()
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

        requested_url = url
        url = admitted_esma_download_url(url)
        if not url:
            self.logger.warning("Refusing non-downloadFile URL: %s", requested_url)
            return None

        details_doc_id = (doc_id or "").strip()
        if details_doc_id and not details_doc_id.isdigit():
            details_doc_id = ""
        if not details_doc_id and url and "docId=" in url:
            m = re.search(r"docId=(\d+)", url)
            if m:
                details_doc_id = m.group(1)

        if self.driver:
            try:
                if "searchRegister" not in (self.driver.current_url or ""):
                    self.navigate_to_search()
                    time.sleep(1)
                path = self._download_binary_with_session(
                    url, doc_id=details_doc_id or doc_id, doc_type_hint=doc_type_hint, date_hint=date_hint
                )
                if path:
                    return path
            except Exception as e:
                self.logger.debug(f"Early session download failed: {e}")

        # --- Direct Download Attempt using Requests --- 
        try:
            # Use requests for potentially faster/more reliable downloads than browser clicks
            headers = {
                'User-Agent': self.user_agent  # Use the same UA as Chrome session
            }
            
            headers['Referer'] = SECURITIES_URL
            if self.driver:
                try:
                    headers['Referer'] = self.driver.current_url or SECURITIES_URL
                    self.logger.debug(f"Added Referer: {headers['Referer']}")
                except Exception as e:
                    self.logger.debug(f"Could not get Referer from driver: {e}")
            
            cookie_jar = self._request_cookie_dict() or None
            if cookie_jar:
                self.logger.debug("Using %s cookies for downloadFile GET", len(cookie_jar))
            
            # Configure proxy for requests if set
            proxies = None
            if self.http_proxy or self.https_proxy:
                proxies = {
                    'http': self.http_proxy,
                    'https': self.https_proxy or self.http_proxy
                }
                self.logger.debug(f"Using proxies for requests: {proxies}")
            
            response = requests.get(
                url, headers=headers, cookies=cookie_jar, stream=True, timeout=60, proxies=proxies
            )
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

            if not temp_download_path.read_bytes()[:5].startswith(b"%PDF"):
                self.logger.warning("HTTP download did not return a PDF; trying session fetch.")
                if temp_download_path.exists():
                    temp_download_path.unlink()
                fetched = self._download_via_fetch(url, doc_id, doc_type_hint, date_hint)
                if fetched:
                    return fetched
                browser_path = self._download_via_browser(url, doc_id, doc_type_hint, date_hint)
                if browser_path:
                    return browser_path
                if details_doc_id and self.driver:
                    return self.download_via_details_page(
                        details_doc_id,
                        doc_type_hint=doc_type_hint,
                        date_hint=date_hint,
                    )
                return None

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
                    try:
                        if Path(existing_path).read_bytes()[:5].startswith(b"%PDF"):
                            return str(Path(existing_path))
                    except OSError:
                        pass
                    self.logger.warning(
                        f"Duplicate hash points to non-PDF file {existing_path}; removing stale hash entry."
                    )
                    del self.document_hashes[content_hash]
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
            # ESMA pages can keep the document in "interactive" due to async assets.
            # Do not require readyState=="complete"; require not-loading and key UI elements.
            WebDriverWait(self.driver, wait_time).until(
                lambda driver: driver.execute_script("return document.readyState") in ("interactive", "complete")
            )

            key_elements = [
                (By.ID, SEARCH_BUTTON_ID),
                (By.ID, KEYWORD_INPUT_ID),
                (By.CSS_SELECTOR, LEI_INPUT_SELECTOR),
                (By.CSS_SELECTOR, ISIN_INPUT_SELECTOR),
            ]
            found = False
            for loc in key_elements:
                try:
                    WebDriverWait(self.driver, min(15, wait_time)).until(
                        EC.presence_of_element_located(loc)
                    )
                    found = True
                    break
                except Exception:
                    continue

            if not found:
                raise TimeoutException("Key search elements not found")
            
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
            lei_codes: List[str] = []
            raw_leis = company_data.get("leis")
            if isinstance(raw_leis, list):
                lei_codes.extend(str(x).strip() for x in raw_leis if x and str(x).strip())
            raw_lei = company_data.get("lei", "")
            if isinstance(raw_lei, list):
                lei_codes.extend(str(x).strip() for x in raw_lei if x and str(x).strip())
            elif isinstance(raw_lei, str) and raw_lei.strip():
                lei_codes.append(raw_lei.strip())
            seen_lei = set()
            deduped = []
            for lei in lei_codes:
                if lei not in seen_lei:
                    seen_lei.add(lei)
                    deduped.append(lei)
            default_profile["lei_codes"] = deduped

            # Scoring only: equity + any known bonds. Do not use these as the ESMA query key.
            all_isins = []
            isin_eq = company_data.get("isin_equity", "")
            if isin_eq:
                all_isins.append(isin_eq)
            all_isins.extend(company_data.get("isins_bonds", []) or [])
            all_isins.extend(company_data.get("isins_bonds_subsidiaries", []) or [])
            default_profile["isins"] = list(dict.fromkeys(all_isins))

            self.logger.info(
                f"Profile for '{company_name}': {len(default_profile['isins'])} ISINs, "
                f"LEIs={len(deduped)}"
            )
        
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

        # --- LEI match (issuer identity: name list, Solr issuer_lei, or queried LEI) ---
        lei_match = 0.0
        lei_codes = profile.get('lei_codes', [])
        issuer_raw = details.get('issuer_name', '') or ''
        issuer_blob = " ".join(
            str(x)
            for x in (
                issuer_raw,
                details.get("issuer_name_raw") or "",
                details.get("issuer_lei") or "",
                details.get("queried_lei") or "",
            )
            if x
        )
        for lei in lei_codes:
            if lei and lei in issuer_blob:
                lei_match = 1.0
                self.logger.debug(f"LEI match in issuer field: {lei}")
                break

        # --- Name similarity against aliases ---
        issuer = self._normalize_name(issuer_raw)
        name_sims = [fuzz.token_set_ratio(issuer, self._normalize_name(a)) / 100.0 for a in profile.get('aliases', [])]
        name_sim = max(name_sims) if name_sims else 0.0

        # --- Doc type relevance ---
        doc_type = (details.get('doc_type') or '').lower()
        doc_code = (details.get('doc_type_code') or '').upper()
        if doc_code == 'FTWS' or 'final' in doc_type:
            doc_type_score = 1.0
        elif doc_code == 'SUPP':
            doc_type_score = 0.85
        elif doc_code == 'STDA':
            doc_type_score = 0.4
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
            "issuer_name", "doc_type", "doc_tier", "date", "isin", "url", "fuzzy_score",
            "score", "name_sim", "doc_type_score", "recency", "penalty",
            "isin_match", "lei_match", "is_green", "green_confidence",
            "kept", "selection_reason", "register_source", "already_seen",
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
                           min_score: float = 0.55, doc_policy: str = "strict",
                           allow_fallback_search: bool = False) -> List[Dict[str, Any]]:
        """Search ESMA by company LEI(s), select tier1 rows, download.

        Discovery key is issuer_lei (parent + finance/operating sub LEIs).
        GOGEL bond ISINs are not queried. Name search stays off unless
        allow_fallback_search=True. Deal ISIN is the document's ESMA sec_isin.
        """
        self.current_company = company_name
        profile = self._build_company_profile(company_name, company_data=company_data)
        rows: List[Dict[str, Any]] = []
        seen_urls: set = set()

        def _merge(new_rows: List[Dict]):
            for r in new_rows:
                url = r.get('url')
                if url and url not in seen_urls:
                    rows.append(r)
                    seen_urls.add(url)

        leis: List[str] = []
        for lei in profile.get("lei_codes") or []:
            s = str(lei).strip()
            if s and len(s) >= 20 and s not in leis:
                leis.append(s)
        leis = leis[:MAX_LEI_SEARCHES]

        if not leis:
            if allow_fallback_search:
                search_token = profile.get("search_tokens", [company_name.split(" ")[0]])[0]
                self.logger.info(f"No LEI for {company_name}; name fallback search: {search_token}")
                self.navigate_to_search()
                if self.search_company(search_token, is_lei=False):
                    time.sleep(4)
                    self.set_results_per_page(100)
                    _merge(self.process_results(company_name))
            else:
                self.logger.warning(
                    f"No LEI for {company_name} — skip ESMA search (status: no_tier1)"
                )
                self._write_audit_rows(company_name, [])
                return []

        solr_acc: List[Dict[str, Any]] = []
        for lei in leis:
            fetched = self.fetch_securities_via_solr(lei=lei, rows=50)
            for r in fetched:
                r["queried_lei"] = lei
            solr_acc.extend(fetched)
        _merge(solr_acc)

        if not rows and leis:
            self.logger.info(
                f"Solr issuer_lei empty for {company_name}; trying UI LEI search"
            )
            for lei in leis:
                self.logger.info(f"LEI-field search: {lei}")
                self.navigate_to_search()
                if self.search_company(lei, is_lei=True):
                    time.sleep(4)
                    self.set_results_per_page(100)
                    _merge(self.process_results(company_name))
                    if rows:
                        break

        if not rows and allow_fallback_search:
            search_token = profile.get("search_tokens", [company_name.split(" ")[0]])[0]
            self.logger.info(f"Name fallback search: {search_token}")
            self.navigate_to_search()
            if self.search_company(search_token, is_lei=False):
                time.sleep(4)
                self.set_results_per_page(100)
                _merge(self.process_results(company_name))
        elif not rows:
            self.logger.info(
                f"No ESMA rows from LEI search for {company_name}; "
                "name fallback disabled"
            )

        n_attached = attach_solr_download_urls(rows, solr_acc)
        n_dl = sum(1 for r in rows if resolve_download_url(r))
        self.logger.info(
            "Solr downloadFile attached to %s row(s); %s/%s rows have downloadFile",
            n_attached,
            n_dl,
            len(rows),
        )

        scored_rows = []
        for r in rows:
            score, parts = self._compute_multi_signal_score(r, profile)
            g = self._classify_green(r)
            tier = classify_doc_tier(r.get('doc_type_code'), r.get('doc_type'))
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
                "doc_tier": tier,
                "kept": False,
            })
            scored_rows.append(r)

        selected = select_esma_rows(scored_rows, policy=doc_policy, min_score=min_score)
        selected = [
            s for s in selected
            if s.get("doc_tier") == "tier1"
            and (
                float(s.get("lei_match") or 0) > 0
                or float(s.get("isin_match") or 0) > 0
            )
        ]
        selected_urls = {r.get('url') for r in selected}
        for r in scored_rows:
            r['kept'] = r.get('url') in selected_urls
            if r.get('kept'):
                r['selection_reason'] = next(
                    (s.get('selection_reason') for s in selected if s.get('url') == r.get('url')),
                    'selected',
                )

        self._write_audit_rows(company_name, scored_rows)

        downloads = []
        for r in selected:
            seen_key = resolve_download_url(r) or (r.get("url") or "").strip() or str(r.get("doc_id") or "")
            if seen_key and seen_key in self.seen_urls:
                continue
            path = self.download_selected_row(r)
            if path:
                if seen_key:
                    self.seen_urls.add(seen_key)
                try:
                    r['file_size_bytes'] = Path(path).stat().st_size
                except OSError:
                    pass
                downloads.append({
                    "file_path": path,
                    "issuer_name": r.get('issuer_name'),
                    "doc_type": r.get('doc_type'),
                    "date": r.get('date'),
                    "isin": r.get('isin'),
                    "score": r.get('score'),
                    "is_green": r.get('is_green'),
                    "isin_match": r.get('isin_match', 0.0),
                    "lei_match": r.get('lei_match', 0.0),
                    "doc_tier": r.get('doc_tier'),
                    "selection_reason": r.get('selection_reason'),
                    "register_source": r.get('register_source', 'securities'),
                    "doc_id": r.get('doc_id'),
                    "download_url": resolve_download_url(r) or r.get('download_url'),
                    "url": resolve_download_url(r) or r.get('url'),
                })

        self._save_seen_urls()
        if leis and not selected:
            self.logger.warning(
                f"No tier1 document selected for {company_name} "
                f"({len(leis)} LEI(s) searched) — status: no_tier1_on_esma"
            )
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