"""
ESMA Test Runner
--------------
A simplified runner for the ESMA test harness using the mock scraper.
This avoids browser dependencies and makes testing faster and more reliable.
"""

import sys
import argparse
import logging
from pathlib import Path

# Add parent directory to sys.path if needed
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from processes.tests.mock_esma_scraper import MockESMAScraper
from processes.tests.esma_test_harness import (
    TestConfig, PerformanceMetrics, DocumentCache, 
    CompanyMatcher, setup_logger, test_scraper,
    generate_test_report
)

def run_test(company_name):
    """Run a test for a specific company using the mock scraper"""
    # Configure test
    config = TestConfig()
    config.test_companies = [{"name": company_name}]
    config.use_mock = True
    config.component = "scraper"
    
    # Initialize components
    metrics = PerformanceMetrics(config)
    cache = DocumentCache(config)
    logger = setup_logger(config)
    
    try:
        # Initialize mock scraper
        logger.info(f"Initializing Mock ESMA scraper for {company_name}...")
        scraper = MockESMAScraper(
            download_dir=config.cache_dir,
            debug_mode=config.detailed_logging
        )
        
        # Create company matcher
        matcher = CompanyMatcher(logger=logger)
        
        # Run the test
        logger.info(f"Running test for company: {company_name}")
        test_scraper(scraper, config, metrics, cache, matcher, logger)
        
        # Close scraper
        logger.info("Closing scraper...")
        scraper.close()
        
    except Exception as e:
        logger.error(f"Test error: {str(e)}", exc_info=True)
        return 1
    finally:
        # Save metrics and generate report
        metrics.save_metrics()
        generate_test_report(config, metrics)
        
        # Print summary of results
        print("\nTest Results Summary:")
        print(f"Company: {company_name}")
        if company_name in metrics.metrics["company_timings"]:
            company_data = metrics.metrics["company_timings"][company_name]
            print(f"Documents found: {company_data['documents_found']}")
            print(f"Documents processed: {company_data['documents_processed']}")
            print(f"Success rate: {company_data['documents_processed'] / max(1, company_data['documents_found']):.2%}")
            print(f"Runtime: {company_data['duration']:.2f} seconds")
        else:
            print("No data collected for company")
    
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run ESMA test with mock scraper")
    parser.add_argument("company", help="Company name to test")
    args = parser.parse_args()
    
    print(f"Starting ESMA test for company: {args.company}")
    sys.exit(run_test(args.company)) 