#!/usr/bin/env python3
"""
Test script for ESMA scraper to validate recent updates
"""
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.append(str(Path(__file__).resolve().parents[3]))

from processes.esma_scraper import ESMAScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/esma_test.log')
    ]
)

logger = logging.getLogger(__name__)

def test_scraper_basic():
    """Test basic functionality of the ESMA scraper"""
    logger.info("Starting ESMA scraper test...")
    
    scraper = None
    try:
        # Initialize scraper with debug mode
        logger.info("Initializing ESMA scraper...")
        scraper = ESMAScraper(debug_mode=True, headless=False)
        
        # Test navigation
        logger.info("Testing navigation to search page...")
        if scraper.navigate_to_search():
            logger.info("✅ Navigation successful")
            
            # Test setting results per page
            logger.info("Testing results per page setting...")
            scraper.set_results_per_page(100)
            
            # Test search with a well-known company
            test_company = "OMV"
            logger.info(f"Testing search for: {test_company}")
            
            if scraper.search_company(test_company):
                logger.info("✅ Search successful")
                
                # Test the new search_and_process method with scoring
                logger.info("Testing search_and_process with scoring system...")
                results = scraper.search_and_process(test_company, min_score=0.4)
                
                logger.info(f"✅ Search and process completed. Found {len(results)} documents")
                
                # Log results summary
                for i, result in enumerate(results[:5]):  # Show first 5 results
                    logger.info(f"Result {i+1}: {result.get('issuer_name')} - {result.get('doc_type')} - Score: {result.get('score')} - Green: {result.get('is_green')}")
                
                # Check audit logs
                audit_dir = Path("logs/audit")
                if audit_dir.exists():
                    company_audit_files = list(audit_dir.glob("*/esma_rows.csv"))
                    logger.info(f"✅ Found {len(company_audit_files)} audit files")
                    for audit_file in company_audit_files:
                        logger.info(f"  - {audit_file}")
                
                return True
            else:
                logger.error("❌ Search failed")
                return False
        else:
            logger.error("❌ Navigation failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}", exc_info=True)
        return False
    finally:
        if scraper:
            logger.info("Closing scraper...")
            scraper.close()
    
    return False

def test_scoring_system():
    """Test the new scoring system independently"""
    logger.info("Testing scoring system...")
    
    scraper = ESMAScraper(debug_mode=True, headless=True)  # Headless for this test
    
    try:
        # Test company profile building
        test_company = "OMV AG"
        profile = scraper._build_company_profile(test_company)
        logger.info(f"Company profile for {test_company}:")
        logger.info(f"  - Canonical name: {profile.get('canonical_name')}")
        logger.info(f"  - Aliases: {profile.get('aliases')}")
        logger.info(f"  - Search tokens: {profile.get('search_tokens')}")
        
        # Test scoring with mock document data
        mock_doc = {
            'issuer_name': 'OMV AG',
            'doc_type': 'Final Terms',
            'date': '15/01/2024',
            'isin': 'AT0000743059',
            'url': 'https://example.com/doc.pdf'
        }
        
        score, parts = scraper._compute_multi_signal_score(mock_doc, profile)
        logger.info(f"Scoring test - Overall score: {score}")
        logger.info(f"  - Name similarity: {parts['name_sim']}")
        logger.info(f"  - Doc type score: {parts['doc_type']}")
        logger.info(f"  - Recency score: {parts['recency']}")
        logger.info(f"  - Penalty: {parts['penalty']}")
        
        # Test green classification
        green_result = scraper._classify_green(mock_doc)
        logger.info(f"Green classification: {green_result}")
        
        logger.info("✅ Scoring system test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Scoring system test failed: {e}", exc_info=True)
        return False
    finally:
        scraper.close()

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("ESMA SCRAPER TEST SUITE")
    logger.info("=" * 60)
    
    # Test 1: Scoring system (independent)
    logger.info("\n" + "=" * 40)
    logger.info("TEST 1: Scoring System")
    logger.info("=" * 40)
    scoring_success = test_scoring_system()
    
    # Test 2: Basic scraper functionality
    logger.info("\n" + "=" * 40)
    logger.info("TEST 2: Basic Scraper Functionality")
    logger.info("=" * 40)
    basic_success = test_scraper_basic()
    
    # Summary
    logger.info("\n" + "=" * 40)
    logger.info("TEST SUMMARY")
    logger.info("=" * 40)
    logger.info(f"Scoring System: {'✅ PASS' if scoring_success else '❌ FAIL'}")
    logger.info(f"Basic Functionality: {'✅ PASS' if basic_success else '❌ FAIL'}")
    
    if scoring_success and basic_success:
        logger.info("🎉 ALL TESTS PASSED")
        sys.exit(0)
    else:
        logger.error("💥 SOME TESTS FAILED")
        sys.exit(1)


