import os
import json
import logging
from pathlib import Path
from processes.esma_scraper import ESMA_Scraper
from processes.pdf_extractor import PDF_Extractor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_directories():
    """Create necessary directories for the test process."""
    base_dir = Path("data/test")
    downloads_dir = base_dir / "downloads"
    results_dir = base_dir / "results"
    
    for directory in [base_dir, downloads_dir, results_dir]:
        directory.mkdir(parents=True, exist_ok=True)
    
    return downloads_dir, results_dir

def main():
    try:
        # Setup directories
        downloads_dir, results_dir = setup_directories()
        logger.info("Directories set up successfully")
        
        # Initialize scraper
        scraper = ESMA_Scraper(download_dir=str(downloads_dir))
        logger.info("ESMA Scraper initialized")
        
        # Test companies
        test_companies = [
            "BNP Paribas",
            "Société Générale",
            "Deutsche Bank"
        ]
        
        # Process each company
        for company in test_companies:
            logger.info(f"Processing documents for {company}")
            
            # Search and download documents
            documents = scraper.search_documents(company, doc_type="Final Terms")
            logger.info(f"Found {len(documents)} documents for {company}")
            
            # Initialize PDF extractor
            extractor = PDF_Extractor()
            
            # Process each document
            results = []
            for doc in documents:
                try:
                    pdf_path = Path(downloads_dir) / doc['filename']
                    if pdf_path.exists():
                        logger.info(f"Processing {pdf_path.name}")
                        bank_info = extractor.extract_bank_info(str(pdf_path))
                        if bank_info:
                            results.append({
                                'document': doc['filename'],
                                'banks': bank_info
                            })
                except Exception as e:
                    logger.error(f"Error processing {doc['filename']}: {str(e)}")
            
            # Save results
            if results:
                output_file = results_dir / f"{company.replace(' ', '_')}_results.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                logger.info(f"Results saved to {output_file}")
            else:
                logger.warning(f"No bank information found for {company}")
        
        logger.info("Test process completed successfully")
        
    except Exception as e:
        logger.error(f"Error in test process: {str(e)}")
        raise
    finally:
        # Clean up
        if 'scraper' in locals():
            scraper.close()

if __name__ == "__main__":
    main() 