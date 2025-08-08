#!/usr/bin/env python3
"""
Test script to check scoring threshold issues
"""
import logging
import sys

# Add current directory to path
sys.path.append('.')

from processes.esma_scraper import ESMAScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_different_thresholds():
    """Test the search_and_process with different scoring thresholds"""
    logger.info("Testing different scoring thresholds...")
    
    test_company = "OMV"
    thresholds = [0.8, 0.6, 0.4, 0.2, 0.1]
    
    for threshold in thresholds:
        logger.info(f"\n{'='*50}")
        logger.info(f"Testing with threshold: {threshold}")
        logger.info(f"{'='*50}")
        
        scraper = None
        try:
            scraper = ESMAScraper(debug_mode=False, headless=True)
            results = scraper.search_and_process(test_company, min_score=threshold)
            
            logger.info(f"Threshold {threshold}: Found {len(results)} documents")
            
            if len(results) > 0:
                logger.info("Sample results:")
                for i, result in enumerate(results[:3]):  # Show first 3
                    logger.info(f"  {i+1}. {result.get('issuer_name')} - Score: {result.get('score')} - Doc: {result.get('doc_type')}")
                break  # Found results, no need to test lower thresholds
            
        except Exception as e:
            logger.error(f"Error with threshold {threshold}: {e}")
        finally:
            if scraper:
                scraper.close()
    
    logger.info("Threshold testing completed")

if __name__ == "__main__":
    test_different_thresholds()
