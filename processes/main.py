import logging
from datetime import datetime
import json
import os
from esma_scraper import ESMAScraper
import pandas as pd

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('esma_scraper.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def main():
    logger = setup_logging()
    logger.info("Starting ESMA bond data extraction process")
    
    # Create results directory if it doesn't exist
    os.makedirs("results", exist_ok=True)
    
    # Initialize scraper
    scraper = ESMAScraper(download_dir="downloads")
    
    try:
        # Focus on TotalEnergies
        company = "TotalEnergies"
        logger.info(f"Processing {company}...")
        
        # Search and download documents
        results = scraper.search_and_download(company)
        
        if not results:
            logger.warning(f"No documents found for {company}")
        else:
            logger.info(f"Found {len(results)} documents for {company}")
            
            # Save results to JSON
            with open("results/extracted_data.json", "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            # Convert to DataFrame and save to Excel
            df = pd.DataFrame(results)
            df.to_excel("results/extracted_data.xlsx", index=False)
            
            # Save summary
            summary = {
                "company": company,
                "total_documents": len(results),
                "timestamp": datetime.utcnow().isoformat(),
                "status": "completed"
            }
            with open("results/summary.json", "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
            
            logger.info("Results saved to results/ directory")
            
    except Exception as e:
        logger.error(f"Error during processing: {str(e)}")
        raise
    finally:
        scraper.close()
        logger.info("Process completed")

if __name__ == "__main__":
    main() 