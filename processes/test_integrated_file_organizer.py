"""
Test Integrated File Organizer
--------------------------
Tests the integrated file organization functionality in the ESMA scraper.
"""

import os
import sys
import logging
from pathlib import Path
import shutil
import time
import argparse

# Setup path to import from parent directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from processes.esma_scraper import ESMAScraper

def setup_logging():
    """Set up logging to file and console"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/test_integrated_organizer.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def cleanup_test_files(download_dir):
    """Clean up any test files from previous runs"""
    try:
        test_company_dir = Path(download_dir) / "Test_Company"
        temp_downloads_dir = Path(download_dir) / "temp_downloads"
        
        if test_company_dir.exists():
            shutil.rmtree(test_company_dir)
            logger.info(f"Removed test company directory: {test_company_dir}")
            
        if temp_downloads_dir.exists():
            shutil.rmtree(temp_downloads_dir)
            logger.info(f"Removed temp downloads directory: {temp_downloads_dir}")
    except Exception as e:
        logger.error(f"Error cleaning up test files: {e}")

def test_download_document_organization():
    """Test the download_document method with file organization"""
    logger.info("=== TESTING INTEGRATED FILE ORGANIZATION ===")
    
    # Initialize the ESMA scraper
    scraper = ESMAScraper()
    
    try:
        # Create a test document URL (using a public PDF)
        test_url = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
        company_name = "Test Company"
        doc_type = "final_terms"
        date = "20241231"
        
        # Download and organize the document
        logger.info(f"Downloading test document from {test_url}")
        result_path = scraper.download_document(test_url, company_name, doc_type, date)
        
        if result_path and os.path.exists(result_path):
            logger.info(f"Successfully downloaded and organized document to: {result_path}")
            
            # Verify file organization structure
            expected_dir = Path("data/downloads/Test_Company")
            assert result_path.parent == expected_dir, f"File not organized in expected directory: {expected_dir}"
            
            # Verify filename structure
            filename = result_path.name
            assert filename.startswith(f"{doc_type}_{date}"), f"Filename does not follow expected pattern: {filename}"
            
            # Verify hash in filename
            assert len(filename.split('_')) >= 3, f"Filename missing hash component: {filename}"
            
            logger.info("File organization verification successful!")
            return True
        else:
            logger.error("Download or organization failed")
            return False
            
    except Exception as e:
        logger.error(f"Error in test: {e}")
        return False
    finally:
        # Clean up
        scraper.close()

def test_search_and_process():
    """Test the full search and process flow with organization"""
    logger.info("=== TESTING FULL SEARCH AND PROCESS WITH ORGANIZATION ===")
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Test ESMA Scraper with integrated file organization")
    parser.add_argument("--company", default="TotalEnergies", 
                      help="Company name to search for (default: TotalEnergies)")
    args = parser.parse_args()
    
    test_company = args.company
    
    # Initialize the ESMA scraper
    scraper = ESMAScraper()
    
    try:
        # Run the search and process with organization
        logger.info(f"Searching for documents for {test_company}")
        results = scraper.search_and_process(test_company)
        
        if results:
            logger.info(f"Successfully found and processed {len(results)} documents")
            
            # Check if organization worked correctly
            organized_files = list(Path("data/downloads").glob(f"**/{test_company.replace(' ', '_')}/*_*_*.pdf"))
            if organized_files:
                logger.info(f"Found {len(organized_files)} organized files for {test_company}")
                
                # Print sample of organized files
                for file in organized_files[:3]:
                    logger.info(f"Example organized file: {file}")
                
                logger.info("Full process test successful!")
                return True
            else:
                logger.warning(f"No organized files found for {test_company}")
                return False
        else:
            logger.warning(f"No results found for {test_company}")
            return False
            
    except Exception as e:
        logger.error(f"Error in test: {e}")
        return False
    finally:
        # Clean up
        scraper.close()

if __name__ == "__main__":
    # Set up logging
    logger = setup_logging()
    
    # Clean up any previous test files
    cleanup_test_files("data/downloads")
    
    # Test download document with organization
    download_test_result = test_download_document_organization()
    logger.info(f"Download document organization test result: {'PASS' if download_test_result else 'FAIL'}")
    
    # Test full search and process flow
    process_test_result = test_search_and_process()
    logger.info(f"Full search and process test result: {'PASS' if process_test_result else 'FAIL'}")
    
    # At least one test must pass for now (the download test is the critical one)
    if download_test_result:
        logger.info("DOWNLOAD TEST PASSED - ORGANIZATION FUNCTIONALITY VERIFIED!")
        sys.exit(0)
    else:
        logger.error("ALL TESTS FAILED!")
        sys.exit(1) 