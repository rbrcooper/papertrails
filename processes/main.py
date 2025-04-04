import logging
from pathlib import Path
import json
from esma_scraper import ESMAScraper
from company_list_handler import CompanyListHandler
import time
import random
import colorlog

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
logger = colorlog.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

def main():
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Initialize scraper and company list handler
    base_dir = "results"  # Use results directory in current path
    scraper = ESMAScraper(base_dir=base_dir)
    company_handler = CompanyListHandler("urgewald GOGEL 2023 V1.2.xlsx")  # Updated with correct filename
    
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
                    output_file = Path(base_dir) / f"{company_name.replace('/', '_')}.json"
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
                company_handler.save_progress(base_dir)
                
            except Exception as e:
                logger.error(f"Error processing {company_name}: {str(e)}")
                continue  # Continue with next company even if one fails
        
        scraper.close()
            
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        if scraper:
            scraper.close()

if __name__ == "__main__":
    main() 