# TASK: Create Efficient ESMA Test Harness

## PROJECT CONTEXT
My ESMA Prospectus Scraper needs a reliable test framework for quick iteration during development. The current testing approach tests too many companies and takes hours to run, making debugging inefficient.

## CURRENT TEST LIMITATIONS
1. Full test runs are too slow for development feedback
2. Tests don't provide performance metrics
3. Tests repeatedly download the same documents
4. No way to test specific components in isolation
5. Limited visibility into what's failing and why

## TEST HARNESS REQUIREMENTS
Create a comprehensive test harness in `processes/tests/esma_test_harness.py` that:
1. Provides fast feedback during development
2. Includes detailed metrics and logging
3. Uses cached documents when available
4. Can test individual components or the full pipeline
5. Is configurable via command line arguments

## IMPLEMENTATION DETAILS

### 1. Test Configuration
```python
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
```

### 2. Performance Metrics Collection
```python
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
        
    # Add more methods for tracking various metrics
    
    def save_metrics(self):
        """Save metrics to file"""
        self.metrics["end_time"] = time.time()
        self.metrics["total_runtime"] = self.metrics["end_time"] - self.metrics["start_time"]
        
        # Calculate success rates
        for company, timing in self.metrics["company_timings"].items():
            if timing["documents_found"] > 0:
                success_rate = timing["documents_processed"] / timing["documents_found"]
                self.metrics["company_success_rates"][company] = success_rate
        
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
        print(f"Extraction success rate: {self.metrics['successful_extractions']/max(1, self.metrics['extraction_attempts']):.2%}")
        print(f"Bot detections: {self.metrics['bot_detections']}")
```

### 3. Document Caching System
```python
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
            
        # Copy file to cache
        cache_path = self.cache_dir / f"{doc_id}.pdf"
        shutil.copy2(file_path, cache_path)
        
        # Update index
        self.cache_index[doc_id] = {
            "url": url,
            "cached_at": datetime.now().isoformat(),
            "cache_path": str(cache_path)
        }
        self._save_cache_index()
```

### 4. Main Test Harness
```python
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
    
    # Initialize components
    metrics = PerformanceMetrics(config)
    cache = DocumentCache(config)
    logger = setup_logger(config)
    
    # Initialize scraper with optimized settings for testing
    scraper = ESMAScraper(
        download_dir=config.cache_dir,
        headless=True,
        debug_mode=config.detailed_logging,
        timeout=config.timeout
    )
    
    # Add monitoring hooks to track bot detection
    original_random_delay = scraper.random_delay
    def monitored_delay(*args, **kwargs):
        metrics.record_bot_detection()
        return original_random_delay(*args, **kwargs)
    scraper.random_delay = monitored_delay
    
    # Add company name matcher if testing the full pipeline
    matcher = None
    if config.component in ["all", "matcher"]:
        matcher = CompanyMatcher(logger=logger)
    
    # Run the test based on the selected component
    if config.component in ["all", "scraper"]:
        test_scraper(scraper, config, metrics, cache, matcher, logger)
    
    if config.component in ["all", "extractor"]:
        test_extractor(config, metrics, cache, logger)
    
    # Save metrics
    metrics.save_metrics()
    
    # Generate visualization
    generate_test_report(config, metrics)
    
    return metrics

def test_scraper(scraper, config, metrics, cache, matcher, logger):
    """Test the scraper component"""
    for company in config.test_companies:
        company_name = company["name"]
        metrics.start_company(company_name)
        logger.info(f"Testing scraper for company: {company_name}")
        
        try:
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
            for doc in documents:
                # Check cache first
                cached_path = cache.get_cached_document(doc["id"], doc["url"])
                if cached_path:
                    logger.info(f"Using cached document: {doc['id']}")
                    metrics.record_cache_hit(company_name)
                    continue
                
                # Download document
                try:
                    download_path = scraper.download_document(doc["url"], doc["id"])
                    if download_path:
                        metrics.record_download_success(company_name)
                        cache.cache_document(doc["id"], doc["url"], download_path)
                    else:
                        metrics.record_download_failure(company_name)
                except Exception as e:
                    logger.error(f"Download error for {doc['id']}: {str(e)}")
                    metrics.record_error("scraper", f"Download error: {str(e)}")
            
            metrics.end_company(company_name)
            
        except Exception as e:
            logger.error(f"Error processing {company_name}: {str(e)}")
            metrics.record_error("scraper", f"Company processing error: {str(e)}")
            metrics.end_company(company_name, success=False)

def test_extractor(config, metrics, cache, logger):
    """Test the extractor component"""
    # Implementation for testing just the extractor
    pass

def generate_test_report(config, metrics):
    """Generate an HTML report with visualizations"""
    # Implementation to create a visual report of metrics
    pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ESMA Scraper Test Harness")
    parser.add_argument("--companies", help="Comma-separated list of companies to test")
    parser.add_argument("--component", choices=["all", "scraper", "extractor", "matcher"], 
                       default="all", help="Component to test")
    parser.add_argument("--no-cache", action="store_true", help="Disable document caching")
    parser.add_argument("--detailed-logging", action="store_true", help="Enable detailed logging")
    
    args = parser.parse_args()
    run_test(args)
```

## TESTING STRATEGY
1. **Baseline Testing**:
   - Run the test harness without optimizations
   - Record metrics for comparison

2. **Component Testing**:
   - Test scraper in isolation with `--component scraper`
   - Test extractor in isolation with `--component extractor`
   - Test name matcher in isolation with `--component matcher`

3. **Optimization Testing**:
   - Add each optimization one by one
   - Compare metrics to baseline
   - Document improvements

## EXPECTED OUTPUTS
1. **Metrics File** (JSON):
   - Detailed performance metrics
   - Error tracking by component
   - Success rates by company

2. **Visual Report** (HTML):
   - Charts showing performance metrics
   - Company-by-company breakdown
   - Error summary and patterns

3. **Cached Documents**:
   - Organized by document ID
   - Includes metadata for reuse

Use this test harness to quickly identify and fix issues with the ESMA scraper, particularly focusing on bot detection, company name matching, and overall efficiency. The metrics will help prioritize which areas need the most improvement. 