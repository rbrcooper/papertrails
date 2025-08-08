#!/usr/bin/env python3
"""
Debug script for ESMA scraper scoring and row processing
"""
import logging
import sys
import time
from pathlib import Path

# Add current directory to path
sys.path.append('.')

from processes.esma_scraper import ESMAScraper

# Configure logging for better debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/debug_scoring.log')
    ]
)

logger = logging.getLogger(__name__)

def debug_row_processing():
    """Debug the row processing and scoring in detail"""
    logger.info("Starting detailed debug of ESMA scraper row processing...")
    
    scraper = None
    try:
        # Initialize scraper with debug mode
        scraper = ESMAScraper(debug_mode=True, headless=False)
        
        # Navigate and search
        test_company = "OMV"
        logger.info(f"Navigating and searching for: {test_company}")
        
        if not scraper.navigate_to_search():
            logger.error("Navigation failed")
            return
            
        if not scraper.search_company(test_company):
            logger.error("Search failed") 
            return
            
        # Wait and set results per page
        time.sleep(4)
        scraper.set_results_per_page(100)
        
        # Get company profile
        profile = scraper._build_company_profile(test_company)
        logger.info(f"Company profile: {profile}")
        
        # Process results with detailed logging
        logger.info("Processing results with detailed logging...")
        scraper.current_company = test_company
        
        # Call process_results directly to debug
        raw_results = scraper.process_results(test_company)
        logger.info(f"Raw results count: {len(raw_results)}")
        
        # Process each result with scoring
        scored_results = []
        for i, result in enumerate(raw_results):
            logger.info(f"\n--- Processing result {i+1}/{len(raw_results)} ---")
            logger.info(f"Raw result: {result}")
            
            if not result or not result.get('url'):
                logger.warning(f"Skipping result {i+1} - no URL or empty result")
                continue
                
            # Apply scoring
            score, parts = scraper._compute_multi_signal_score(result, profile)
            green_result = scraper._classify_green(result)
            
            # Apply threshold
            min_score = 0.4  # Same as in search_and_process
            kept = (score >= min_score)
            
            result.update({
                "score": round(score, 3),
                "name_sim": parts["name_sim"],
                "doc_type_score": parts["doc_type"],
                "recency": parts["recency"],
                "penalty": parts["penalty"],
                "is_green": green_result["is_green"],
                "green_confidence": green_result["confidence"],
                "kept": kept,
            })
            
            logger.info(f"Scored result:")
            logger.info(f"  - Issuer: {result.get('issuer_name')}")
            logger.info(f"  - Doc Type: {result.get('doc_type')}")
            logger.info(f"  - Date: {result.get('date')}")
            logger.info(f"  - Score: {score:.3f} (threshold: {min_score})")
            logger.info(f"  - Name similarity: {parts['name_sim']:.3f}")
            logger.info(f"  - Doc type score: {parts['doc_type']:.3f}")
            logger.info(f"  - Recency: {parts['recency']:.3f}")
            logger.info(f"  - Penalty: {parts['penalty']:.3f}")
            logger.info(f"  - Kept: {kept}")
            logger.info(f"  - Green: {green_result['is_green']}")
            
            scored_results.append(result)
        
        # Summary
        kept_results = [r for r in scored_results if r.get('kept')]
        logger.info(f"\n=== SUMMARY ===")
        logger.info(f"Total results processed: {len(scored_results)}")
        logger.info(f"Results above threshold: {len(kept_results)}")
        logger.info(f"Threshold used: {min_score}")
        
        if len(kept_results) == 0:
            logger.warning("No results above threshold! Consider lowering threshold.")
            # Show top results
            sorted_results = sorted(scored_results, key=lambda x: x.get('score', 0), reverse=True)
            logger.info("Top 5 results by score:")
            for i, result in enumerate(sorted_results[:5]):
                logger.info(f"  {i+1}. {result.get('issuer_name')} - Score: {result.get('score'):.3f}")
        
        return scored_results
        
    except Exception as e:
        logger.error(f"Debug failed with error: {e}", exc_info=True)
        return []
    finally:
        if scraper:
            scraper.close()

if __name__ == "__main__":
    results = debug_row_processing()
    print(f"\nDebug completed. Check logs/debug_scoring.log for detailed output.")
    print(f"Processed {len(results)} results.")
