from pdf_extractor import PDFExtractor
import os
import json
from datetime import datetime
import time
import logging
from typing import Dict, List

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bank_info_extraction.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def process_bank_data(bank_data: Dict) -> Dict:
    """Process and clean bank data for better output format"""
    processed_data = {
        "banks": [],
        "bank_details": {}
    }
    
    for bank in bank_data.get("banks", []):
        processed_data["banks"].append(bank)
        processed_data["bank_details"][bank] = {
            "roles": bank_data.get("roles", {}).get(bank, []),
            "contact_info": bank_data.get("contact_info", {}).get(bank, ""),
            "is_global_coordinator": "global_coordinator" in bank_data.get("roles", {}).get(bank, []),
            "is_bookrunner": "bookrunner" in bank_data.get("roles", {}).get(bank, [])
        }
    
    return processed_data

def main():
    # Setup logging
    logger = setup_logging()
    logger.info("Starting bank information extraction process")
    
    # Initialize the PDF extractor
    extractor = PDFExtractor()
    
    # Get all PDF files in the downloads directory
    pdf_files = [f for f in os.listdir(extractor.pdf_dir) if f.endswith('.pdf')]
    
    # Filter for final terms documents first
    final_terms = [f for f in pdf_files if 'Final terms' in f or 'Final_terms' in f]
    logger.info(f"Found {len(final_terms)} final terms documents")
    
    results = []
    for i, pdf_file in enumerate(final_terms, 1):
        logger.info(f"\nProcessing document {i}/{len(final_terms)}: {pdf_file}")
        pdf_path = os.path.join(extractor.pdf_dir, pdf_file)
        
        try:
            # Extract text from PDF with progress indicator
            logger.info("Extracting text...")
            start_time = time.time()
            text = extractor.extract_text(pdf_path)
            if not text:
                logger.warning(f"Could not extract text from {pdf_file}")
                continue
            logger.info(f"Text extraction took {time.time() - start_time:.2f} seconds")
            
            # Extract bank information
            logger.info("Extracting bank information...")
            bank_data = extractor.extract_bank_info(text)
            
            # Process and clean the bank data
            processed_data = process_bank_data(bank_data)
            
            # Add metadata
            processed_data["metadata"] = {
                "pdf_file": pdf_file,
                "processed_at": datetime.utcnow().isoformat(),
                "document_type": "Final Terms"
            }
            
            results.append(processed_data)
            
            # Print results for this file
            logger.info(f"\nFound {len(processed_data['banks'])} banks:")
            for bank in processed_data["banks"]:
                details = processed_data["bank_details"][bank]
                logger.info(f"\nBank: {bank}")
                logger.info(f"Roles: {', '.join(details['roles'])}")
                if details["contact_info"]:
                    logger.info(f"Contact: {details['contact_info']}")
                    
        except Exception as e:
            logger.error(f"Error processing {pdf_file}: {str(e)}", exc_info=True)
            continue
        
        # Save intermediate results after each file
        output_file = "bank_info.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logger.info(f"\nIntermediate results saved to {output_file}")
    
    logger.info("\nProcessing complete!")

if __name__ == "__main__":
    main() 