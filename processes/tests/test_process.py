"""
Test Process for ESMA Scraper
---------------------------
This script tests the ESMA scraper functionality.
"""

import logging
import os
import sys
import time
import argparse
from pathlib import Path
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select

# Add the parent directory to the Python path
sys.path.append(str(Path(__file__).parent.parent.parent))

from processes.esma_scraper import ESMAScraper
from processes.company_list_handler import CompanyListHandler
from processes.utils.tracking_system import TrackingSystem

# Define EU countries
EU_COUNTRIES = [
    'Austria', 'Belgium', 'Bulgaria', 'Croatia', 'Cyprus', 'Czech Republic',
    'Denmark', 'Estonia', 'Finland', 'France', 'Germany', 'Greece', 'Hungary',
    'Ireland', 'Italy', 'Latvia', 'Lithuania', 'Luxembourg', 'Malta', 'Netherlands',
    'Poland', 'Portugal', 'Romania', 'Slovakia', 'Slovenia', 'Spain', 'Sweden'
]

# Setup logging
log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'test_process.log'),
        logging.StreamHandler()
    ]
)

# Get logger for this module
logger = logging.getLogger(__name__)

def test_process(num_companies: int, headless: bool = True):
    """Test the ESMA scraper by processing a specified number of companies."""
    try:
        logging.info("Starting test process")
        
        # Initialize systems
        company_handler = CompanyListHandler(eu_countries=EU_COUNTRIES)
        tracking = TrackingSystem()
        
        # Initialize the scraper with debug mode enabled
        scraper = ESMAScraper(debug_mode=True)
        
        # Set headless mode in Chrome options
        if headless:
            scraper.headless = True
        else:
            scraper.headless = False
        
        # Load company stats
        company_handler.load_company_stats()
        logger.info(f"Loaded stats for {len(company_handler.company_stats)} companies")
        
        # Load companies
        logger.info("Loading companies from data/raw/urgewald GOGEL 2023 V1.2.xlsx")
        companies = company_handler.get_all_companies()
        eu_companies = [c for c in companies if c.get('country') in EU_COUNTRIES]
        logger.info(f"Loaded {len(eu_companies)} EU companies")
        
        # Get processed companies
        processed_companies = company_handler.get_processed_companies()
        logger.info(f"Loaded {len(processed_companies)} processed companies")
        
        # Get unprocessed companies
        unprocessed_companies = [c for c in eu_companies if c['name'] not in processed_companies]
        logger.info(f"Processing {num_companies} unprocessed EU companies")
        
        # Take first num_companies
        companies_to_process = unprocessed_companies[:num_companies]
        if not companies_to_process:
            logger.warning("No unprocessed companies found")
            return
            
        # Replace first company with TotalEnergies for testing
        companies_to_process[0] = {
            'name': 'TotalEnergies SE',
            'country': 'France',
            'sector': 'Oil & Gas',
            'subsector': 'Integrated Oil & Gas'
        }
        
        logger.info(f"Companies to process: {[c['name'] for c in companies_to_process]}")
        
        # Process each company
        for company in companies_to_process:
            company_name = company['name']
            logger.info(f"\nProcessing company: {company_name}")
            search_successful = False
            process_successful = False

            try:
                # Step 1: Search for the company
                logger.info(f"Initiating search for {company_name}...")
                search_successful = scraper.search_company(company_name)

                if search_successful:
                    logger.info(f"Search sequence completed for {company_name}. Proceeding to process results.")
                    # Step 2: Process the results if search was successful
                    process_successful = scraper.process_results(company_name)

                    if process_successful:
                        logger.info(f"Successfully processed results (documents checked/downloaded) for {company_name}")
                    else:
                        logger.warning(f"Result processing failed for {company_name}. Check logs/page source.")
                        # Track failure during processing phase
                        tracking.track_failed_extraction(company_name, "Result processing failed after successful search")
                else:
                    logger.error(f"Search sequence failed for {company_name}. Skipping result processing.")
                    # Track failure during search phase
                    tracking.track_failed_extraction(company_name, "Search sequence failed")

                if search_successful is not None:
                    company_handler.mark_company_as_processed(company_name)
                    logger.info(f"Marked {company_name} as processed.")
                else:
                    logger.warning(f"Did not mark {company_name} as processed due to search exception.")
                
            except Exception as e:
                # Catch exceptions from either search_company or process_results
                logger.error(f"An exception occurred while processing {company_name}: {str(e)}", exc_info=True)
                tracking.track_failed_extraction(company_name, f"Exception: {str(e)}")
                # Decide if you want to mark as processed even on exception
                # company_handler.mark_company_as_processed(company_name)
                continue # Move to the next company

        logger.info("Test process completed")
                
    except Exception as e:
        logger.error(f"Error in test process: {str(e)}")
    finally:
        if 'scraper' in locals():
            scraper.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test ESMA scraper')
    parser.add_argument('--num-companies', type=int, default=1,
                      help='Number of companies to process')
    parser.add_argument('--visible', action='store_false', dest='headless',
                      help='Run browser in visible mode')
    args = parser.parse_args()

    logging.info("Starting test process")
    test_process(num_companies=args.num_companies, headless=args.headless)
    logging.info("Test process completed") 