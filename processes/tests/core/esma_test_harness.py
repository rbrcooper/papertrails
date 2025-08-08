"""
ESMA Test Harness
----------------
A comprehensive test framework for the ESMA document scraping system.

This test harness provides:
1. Fast feedback during development
2. Detailed metrics and logging
3. Document caching to avoid redundant downloads
4. Component-level or full pipeline testing
5. Command-line configuration

Usage:
    python -m processes.tests.esma_test_harness [--companies NAMES] [--no-cache] [--component COMPONENT] [--use-mock]
"""

import os
import sys
import time
import json
import shutil
import argparse
import logging
import colorlog
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any

# Add parent directory to sys.path to allow imports when run directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import from processes package
from processes.esma_scraper import ESMAScraper
from processes.company_list_handler import CompanyListHandler
from processes.tests.mock_esma_scraper import MockESMAScraper


class TestConfig:
    """Configuration for ESMA test harness"""
    def __init__(self):
        self.test_companies = [
            {"name": "TotalEnergies SE", "country": "France"},  # Known to have many documents
            {"name": "Aker BP ASA", "country": "Norway"},       # Good candidate with varied docs
            {"name": "MEDIOBANCA", "country": "Italy"}          # Tests name matching edge case
        ]
        self.use_cache = True                # Use cached documents when available
        self.cache_dir = "data/test_cache"   # Directory for cached documents
        self.metrics_file = "logs/test_metrics.json"  # Output file for metrics
        self.timeout = 30                    # Timeout for web operations in seconds
        self.max_retries = 3                 # Maximum retries per operation
        self.detailed_logging = True         # Enable detailed logging
        self.component = "all"               # Component to test (scraper, extractor, or all)
        self.use_mock = False                # Whether to use the mock scraper instead of real one


class PerformanceMetrics:
    """Collects and reports performance metrics"""
    def __init__(self, config):
        self.config = config
        self.metrics = {
            "start_time": time.time(),
            "end_time": None,
            "total_runtime": 0,
            "companies_processed": 0,
            "documents_found": 0,
            "documents_downloaded": 0,
            "documents_from_cache": 0,
            "extraction_attempts": 0,
            "successful_extractions": 0,
            "bot_detections": 0,
            "errors": {
                "scraper": [],
                "extractor": [],
                "name_matching": []
            },
            "company_timings": {},
            "company_success_rates": {}
        }
        
    def start_company(self, company_name):
        """Start timing a company process"""
        self.metrics["company_timings"][company_name] = {
            "start_time": time.time(),
            "end_time": None,
            "duration": 0,
            "documents_found": 0,
            "documents_processed": 0
        }
        
    def end_company(self, company_name):
        """End timing a company process"""
        if company_name in self.metrics["company_timings"]:
            company_data = self.metrics["company_timings"][company_name]
            company_data["end_time"] = time.time()
            company_data["duration"] = company_data["end_time"] - company_data["start_time"]
            self.metrics["companies_processed"] += 1
    
    def record_documents_found(self, company_name, count):
        """Record number of documents found for a company"""
        if company_name in self.metrics["company_timings"]:
            self.metrics["company_timings"][company_name]["documents_found"] = count
            self.metrics["documents_found"] += count
    
    def record_download_success(self, company_name):
        """Record a successful document download"""
        self.metrics["documents_downloaded"] += 1
        if company_name in self.metrics["company_timings"]:
            self.metrics["company_timings"][company_name]["documents_processed"] += 1
    
    def record_download_failure(self, company_name):
        """Record a failed document download"""
        self.metrics["errors"]["scraper"].append(f"Download failure for {company_name}")
    
    def record_cache_hit(self, company_name):
        """Record a document found in cache"""
        self.metrics["documents_from_cache"] += 1
        if company_name in self.metrics["company_timings"]:
            self.metrics["company_timings"][company_name]["documents_processed"] += 1
    
    def record_extraction_attempt(self):
        """Record an attempt to extract content from a document"""
        self.metrics["extraction_attempts"] += 1
    
    def record_extraction_success(self):
        """Record a successful content extraction"""
        self.metrics["successful_extractions"] += 1
    
    def record_bot_detection(self):
        """Record a bot detection event"""
        self.metrics["bot_detections"] += 1
    
    def record_error(self, component, message):
        """Record an error in a specific component"""
        if component in self.metrics["errors"]:
            self.metrics["errors"][component].append(message)
        
    def save_metrics(self):
        """Save metrics to file"""
        self.metrics["end_time"] = time.time()
        self.metrics["total_runtime"] = self.metrics["end_time"] - self.metrics["start_time"]
        
        # Calculate success rates
        for company, timing in self.metrics["company_timings"].items():
            if timing["documents_found"] > 0:
                success_rate = timing["documents_processed"] / timing["documents_found"]
                self.metrics["company_success_rates"][company] = success_rate
        
        # Create directory if it doesn't exist
        metrics_dir = os.path.dirname(self.config.metrics_file)
        if not os.path.exists(metrics_dir):
            os.makedirs(metrics_dir)
            
        # Save to file
        with open(self.config.metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=2)
        
        # Print summary
        print(f"\nTest Summary:")
        print(f"Total runtime: {self.metrics['total_runtime']:.2f} seconds")
        print(f"Companies processed: {self.metrics['companies_processed']}")
        print(f"Documents found: {self.metrics['documents_found']}")
        print(f"Documents downloaded: {self.metrics['documents_downloaded']}")
        print(f"Documents from cache: {self.metrics['documents_from_cache']}")
        if self.metrics['extraction_attempts'] > 0:
            print(f"Extraction success rate: {self.metrics['successful_extractions']/max(1, self.metrics['extraction_attempts']):.2%}")
        print(f"Bot detections: {self.metrics['bot_detections']}")
        
        # Print errors if any
        for component, errors in self.metrics["errors"].items():
            if errors:
                print(f"\nErrors in {component}: {len(errors)}")
                for error in errors[:5]:  # Show at most 5 errors
                    print(f"  - {error}")
                if len(errors) > 5:
                    print(f"  ... and {len(errors) - 5} more.")


class DocumentCache:
    """Caches downloaded documents to avoid redownloading"""
    def __init__(self, config):
        self.config = config
        self.cache_dir = Path(config.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_index = self._load_cache_index()
        
    def _load_cache_index(self):
        """Load the cache index file"""
        index_file = self.cache_dir / "cache_index.json"
        if index_file.exists():
            with open(index_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_cache_index(self):
        """Save the cache index file"""
        index_file = self.cache_dir / "cache_index.json"
        with open(index_file, 'w') as f:
            json.dump(self.cache_index, f, indent=2)
    
    def get_cached_document(self, doc_id, url):
        """Get a document from cache if it exists"""
        if not self.config.use_cache:
            return None
            
        if doc_id in self.cache_index:
            cache_path = self.cache_dir / f"{doc_id}.pdf"
            if cache_path.exists():
                return str(cache_path)
        return None
    
    def cache_document(self, doc_id, url, file_path):
        """Cache a document for future use"""
        if not self.config.use_cache:
            return
        
        # Define the target cache path
        cache_path = self.cache_dir / f"{doc_id}.pdf"
        
        # Check if the file already exists in cache
        if cache_path.exists():
            # Update index only if needed
            if doc_id not in self.cache_index:
                self.cache_index[doc_id] = {
                    "url": url,
                    "cached_at": datetime.now().isoformat(),
                    "cache_path": str(cache_path)
                }
                self._save_cache_index()
            return
        
        # Try to copy file with retries
        max_retries = 3
        retry_delay = 0.5
        success = False
        
        for attempt in range(max_retries):
            try:
                # Create a temp file path to avoid conflicts
                temp_cache_path = self.cache_dir / f"temp_{doc_id}_{int(time.time())}.pdf"
                
                # Copy to temp location first
                shutil.copy2(file_path, temp_cache_path)
                
                # Ensure the copy is complete
                time.sleep(0.1)
                
                # Rename to final location
                try:
                    import os
                    os.replace(str(temp_cache_path), str(cache_path))
                except Exception as e:
                    # If rename fails, try to use the rename method
                    if temp_cache_path.exists() and not cache_path.exists():
                        temp_cache_path.rename(cache_path)
                    else:
                        raise e
                
                # Update cache index
                self.cache_index[doc_id] = {
                    "url": url,
                    "cached_at": datetime.now().isoformat(),
                    "cache_path": str(cache_path)
                }
                self._save_cache_index()
                
                success = True
                break
                
            except Exception as e:
                # Clean up temp file if it exists
                if 'temp_cache_path' in locals() and temp_cache_path.exists():
                    try:
                        temp_cache_path.unlink()
                    except Exception:
                        pass
                
                # If last attempt, no need to wait
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))  # Increasing delay with each attempt
        
        # If all attempts failed, log the error
        if not success:
            print(f"Warning: Failed to cache document {doc_id} after {max_retries} attempts")


class CompanyMatcher:
    """Helper for matching company names"""
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        
    def match_company_name(self, company_name):
        """Match company name for better search results
        This is a simple implementation. A more sophisticated version
        could be implemented if needed.
        """
        # Remove common company suffixes
        suffixes = [" SE", " ASA", " SA", " NV", " AG", " plc", " Ltd", " LLC", " GmbH"]
        search_name = company_name
        for suffix in suffixes:
            if company_name.endswith(suffix):
                search_name = company_name[:-len(suffix)]
                self.logger.info(f"Removed suffix from {company_name} -> {search_name}")
                break
                
        return search_name


def setup_logger(config):
    """Set up a logger with color formatting"""
    # Create a colored formatter
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
    
    # Create file handler
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler("logs/esma_test.log")
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(file_formatter)
    
    # Configure logger
    logger = logging.getLogger("esma_test")
    logger.setLevel(logging.DEBUG if config.detailed_logging else logging.INFO)
    logger.handlers = []  # Remove existing handlers if any
    logger.addHandler(handler)
    logger.addHandler(file_handler)
    logger.propagate = False
    
    return logger


def test_scraper(scraper, config, metrics, cache, matcher, logger):
    """Test the scraper component"""
    for company in config.test_companies:
        company_name = company["name"]
        metrics.start_company(company_name)
        logger.info(f"Testing scraper for company: {company_name}")
        
        try:
            # Set current company context for the scraper (useful for organize_file)
            scraper.current_company = company_name
            
            # Match company name if matcher is available
            search_name = company_name
            if matcher:
                matched_name = matcher.match_company_name(company_name)
                if matched_name:
                    search_name = matched_name
                    logger.info(f"Using matched name: {matched_name}")
            
            # Search for documents
            documents = scraper.search_documents(search_name)
            metrics.record_documents_found(company_name, len(documents))
            
            # Process each document
            for doc in documents[:5]:  # Limit to 5 documents per company for testing
                doc_id = doc.get("id")
                doc_url = doc.get("url")
                doc_type = doc.get("type")
                doc_date = doc.get("date")
                
                if not doc_id or not doc_url:
                    logger.warning(f"Skipping document due to missing ID or URL: {doc}")
                    continue
                    
                # Set current doc type context
                scraper.current_doc_type = doc_type

                # Check cache first
                cached_path = cache.get_cached_document(doc_id, doc_url)
                if cached_path:
                    logger.info(f"Using cached document: {doc_id}")
                    metrics.record_cache_hit(company_name)
                    continue
                
                # Download document, passing hints
                try:
                    download_path = scraper.download_document(
                        doc_url,
                        doc_id=doc_id,
                        doc_type_hint=doc_type, # Pass type hint
                        date_hint=doc_date       # Pass date hint
                    )
                    if download_path:
                        logger.info(f"Successfully downloaded: {doc_id}")
                        metrics.record_download_success(company_name)
                        cache.cache_document(doc_id, doc_url, download_path)
                    else:
                        logger.warning(f"Failed to download: {doc_id}")
                        metrics.record_download_failure(company_name)
                except Exception as e:
                    logger.error(f"Download error for {doc_id}: {str(e)}", exc_info=True) # Add exc_info
                    metrics.record_error("scraper", f"Download error for {doc_id}: {str(e)}")
            
            metrics.end_company(company_name)
            
        except Exception as e:
            logger.error(f"Error processing company {company_name}: {str(e)}", exc_info=True) # Add exc_info
            metrics.record_error("scraper", f"Error processing company {company_name}: {str(e)}")
            metrics.end_company(company_name)
        finally:
            # Clear context after processing company
            scraper.current_company = None
            scraper.current_doc_type = None


def test_extractor(config, metrics, cache, logger):
    """Test the extractor component"""
    logger.info("Extractor testing is not implemented yet")
    # This would be implemented if we had a document extractor component


def generate_test_report(config, metrics):
    """Generate visualizations and reports from test metrics"""
    # Simple report generation - could be expanded with matplotlib charts
    report_path = Path("logs/test_report.txt")
    with open(report_path, "w") as f:
        f.write("ESMA Test Harness Report\n")
        f.write("======================\n\n")
        f.write(f"Test run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total runtime: {metrics.metrics['total_runtime']:.2f} seconds\n")
        f.write(f"Companies tested: {', '.join([c['name'] for c in config.test_companies])}\n\n")
        
        f.write("Company Results:\n")
        for company, timing in metrics.metrics["company_timings"].items():
            f.write(f"  - {company}:\n")
            f.write(f"    - Runtime: {timing['duration']:.2f} seconds\n")
            f.write(f"    - Documents found: {timing['documents_found']}\n")
            f.write(f"    - Documents processed: {timing['documents_processed']}\n")
            success_rate = timing['documents_processed'] / max(1, timing['documents_found'])
            f.write(f"    - Success rate: {success_rate:.2%}\n")
        
        f.write("\nError summary:\n")
        total_errors = sum(len(errors) for errors in metrics.metrics["errors"].values())
        f.write(f"Total errors: {total_errors}\n")
        for component, errors in metrics.metrics["errors"].items():
            if errors:
                f.write(f"  - {component}: {len(errors)} errors\n")


def run_test(args):
    """Run the test harness with given arguments"""
    # Parse arguments
    config = TestConfig()
    if args.companies:
        config.test_companies = [{"name": name} for name in args.companies.split(",")]
    if args.no_cache:
        config.use_cache = False
    if args.component:
        config.component = args.component
    if args.use_mock:
        config.use_mock = True
    
    # Initialize components
    metrics = PerformanceMetrics(config)
    cache = DocumentCache(config)
    logger = setup_logger(config)
    
    try:
        # Initialize scraper with optimized settings for testing
        logger.info(f"Initializing {'Mock' if config.use_mock else 'Real'} ESMA scraper...")
        if config.use_mock:
            scraper = MockESMAScraper(
                download_dir=config.cache_dir,
                headless=True,
                debug_mode=config.detailed_logging
            )
        else:
            scraper = ESMAScraper(
                download_dir=config.cache_dir,
                headless=True,
                debug_mode=config.detailed_logging
            )
        
        # Add company name matcher if testing the full pipeline
        matcher = None
        if config.component in ["all", "matcher"]:
            matcher = CompanyMatcher(logger=logger)
        
        # Run the test based on the selected component
        if config.component in ["all", "scraper"]:
            test_scraper(scraper, config, metrics, cache, matcher, logger)
        
        if config.component in ["all", "extractor"]:
            test_extractor(config, metrics, cache, logger)
        
        # Close scraper
        logger.info("Closing scraper...")
        scraper.close()
        
    except Exception as e:
        logger.error(f"Test harness error: {str(e)}", exc_info=True)
        metrics.record_error("general", f"Test harness error: {str(e)}")
    finally:
        # Save metrics
        metrics.save_metrics()
        
        # Generate visualization
        generate_test_report(config, metrics)
    
    return metrics


if __name__ == "__main__":
    """Main entry point when run as a script"""
    parser = argparse.ArgumentParser(description="ESMA Test Harness")
    parser.add_argument("--companies", help="Comma-separated list of company names to test")
    parser.add_argument("--no-cache", action="store_true", help="Disable document caching")
    parser.add_argument("--component", choices=["all", "scraper", "extractor", "matcher"], default="all",
                        help="Component to test (default: all)")
    parser.add_argument("--use-mock", action="store_true", help="Use mock implementation instead of real scraper")
    args = parser.parse_args()
    
    print(f"Starting ESMA Test Harness with components: {args.component} {'(MOCK MODE)' if args.use_mock else ''}")
    run_test(args) 