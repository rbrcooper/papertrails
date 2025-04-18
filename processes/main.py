"""
ESMA Document Processing Pipeline
------------------------------
Main orchestration script that coordinates the document scraping and processing pipeline.
Manages the workflow between the ESMA scraper, PDF extractor, and company list handler.

Key Features:
- Pipeline orchestration
- Error handling and recovery
- Progress tracking
- Logging and reporting
- Batch processing management
- File organization and deduplication

Dependencies:
- esma_scraper: Web scraping functionality
- pdf_extractor: PDF processing
- company_list_handler: Company data management
- logging: Logging functionality

Usage:
python main.py [--companies-file PATH] [--output-dir PATH]

The script will:
1. Load the list of companies to process
2. Initialize the ESMA scraper
3. Download relevant documents for each company
4. Extract and process document content
5. Save results and generate reports
"""

import logging
from pathlib import Path
import json
import time
import random
import colorlog
import os
import argparse
import sys

# Add parent directory to sys.path to allow imports when run directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import from processes package
from processes.esma_scraper import ESMAScraper
from processes.company_list_handler import CompanyListHandler

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

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/workflow.log'),
        handler
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main function to run the ESMA document processing pipeline"""
    # Parse arguments
    parser = argparse.ArgumentParser(description="ESMA document processing pipeline")
    parser.add_argument("--companies-file", default=os.path.join("data", "raw", "urgewald GOGEL 2023 V1.2.xlsx"), 
                        help="Path to the companies Excel file")
    parser.add_argument("--output-dir", default="data/processed", help="Directory to save output files")
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    base_dir = Path(args.output_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        logger.info("Starting ESMA document processing pipeline")
        
        # Initialize scraper and company list handler
        scraper = ESMAScraper()
        company_handler = CompanyListHandler(args.companies_file)
        
        try:
            # Get all unprocessed companies
            companies = company_handler.get_unprocessed_companies()
            logger.info(f"Found {len(companies)} European companies to process")
            
            # Process each company
            for company in companies:
                company_name = company['name']
                logger.info(f"Processing company: {company_name}")
                
                try:
                    results = scraper.search_and_process(company_name, company_info=company)
                    
                    if results:
                        logger.info(f"Found {len(results)} documents for {company_name}")
                        # Save results
                        output_file = base_dir / f"{company_name.replace('/', '_')}.json"
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump({
                                'company': company,
                                'documents': results
                            }, f, indent=2, ensure_ascii=False)
                        logger.info(f"Saved results to {output_file}")
                    else:
                        logger.warning(f"No documents found for {company_name}")
                    
                    # Mark company as processed
                    company_handler.mark_company_as_processed(company_name)
                    # Save progress after each company
                    company_handler.save_progress()
                    
                except Exception as e:
                    logger.error(f"Error processing {company_name}: {str(e)}")
                    continue  # Continue with next company even if one fails
            
            scraper.close()
            
        except Exception as e:
            logger.error(f"Error processing companies: {str(e)}")
            if 'scraper' in locals() and scraper:
                scraper.close()
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        if 'scraper' in locals() and scraper:
            scraper.close()

if __name__ == "__main__":
    main() 