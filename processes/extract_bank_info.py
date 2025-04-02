from pdf_extractor import PDFExtractor
import os
import json
from datetime import datetime
import time
import logging
from typing import Dict, List
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError

def setup_logging():
    """Setup logging configuration"""
    # Ensure log directory exists
    os.makedirs('log', exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # Remove any existing handlers
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    
    # Add handlers
    file_handler = logging.FileHandler(os.path.join('log', 'bank_info_extraction.log'), encoding='utf-8')
    console_handler = logging.StreamHandler()
    
    # Set format
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger, [file_handler, console_handler]

def process_bank_data(bank_data: Dict) -> Dict:
    """Process and clean bank data for better output format"""
    processed_data = {
        "banks": [],
        "bank_details": {},
        "distribution_method": bank_data.get("distribution_method", "Not specified")
    }
    
    for bank in bank_data.get("banks", []):
        processed_data["banks"].append(bank)
        processed_data["bank_details"][bank] = {
            "roles": bank_data.get("roles", {}).get(bank, []),
            "contact_info": bank_data.get("contact_info", {}).get(bank, ""),
            "is_global_coordinator": "global_coordinator" in bank_data.get("roles", {}).get(bank, []),
            "is_joint_active_bookrunner": "joint_active_bookrunner" in bank_data.get("roles", {}).get(bank, []),
            "is_stabilisation_manager": "stabilisation_manager" in bank_data.get("roles", {}).get(bank, []),
            "is_calculation_agent": "calculation_agent" in bank_data.get("roles", {}).get(bank, [])
        }
    
    return processed_data

def extract_text_with_timeout(extractor, pdf_path, timeout=60):
    """Extract text from PDF with timeout"""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(extractor.extract_text, pdf_path)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            raise TimeoutError(f"Text extraction timed out after {timeout} seconds")

def extract_bank_info_with_timeout(extractor, text, timeout=30):
    """Extract bank information with timeout"""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(extractor.extract_bank_info, text)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            raise TimeoutError(f"Bank information extraction timed out after {timeout} seconds")

def main():
    # Setup logging
    logger, handlers = setup_logging()
    try:
        logger.info("Starting bank information extraction process")
        
        # Initialize the PDF extractor
        extractor = PDFExtractor()
        
        # Get all PDF files in the downloads directory
        pdf_files = [f for f in os.listdir(extractor.pdf_dir) if f.endswith('.pdf')]
        logger.info(f"Found {len(pdf_files)} PDF files in total")
        
        # Filter for final terms documents first
        final_terms = [f for f in pdf_files if 'Final terms' in f or 'Final_terms' in f]
        logger.info(f"Found {len(final_terms)} final terms documents")
        
        # Ensure results directory exists
        os.makedirs('results', exist_ok=True)
        
        results = []
        for i, pdf_file in enumerate(final_terms, 1):
            logger.info(f"\nProcessing document {i}/{len(final_terms)}: {pdf_file}")
            pdf_path = os.path.join(extractor.pdf_dir, pdf_file)
            
            try:
                # Extract text from PDF with progress indicator and timeout
                logger.info("Starting text extraction...")
                start_time = time.time()
                
                try:
                    text = extract_text_with_timeout(extractor, pdf_path)
                except TimeoutError as e:
                    logger.error(str(e))
                    continue
                except Exception as e:
                    logger.error(f"Error during text extraction: {str(e)}", exc_info=True)
                    continue
                
                if not text:
                    logger.warning(f"Could not extract text from {pdf_file}")
                    continue
                    
                extraction_time = time.time() - start_time
                logger.info(f"Text extraction completed in {extraction_time:.2f} seconds")
                logger.info(f"Extracted text length: {len(text)} characters")
                
                # Extract bank information with timeout
                logger.info("Starting bank information extraction...")
                bank_start_time = time.time()
                
                try:
                    bank_data = extract_bank_info_with_timeout(extractor, text)
                except TimeoutError as e:
                    logger.error(str(e))
                    continue
                except Exception as e:
                    logger.error(f"Error during bank information extraction: {str(e)}", exc_info=True)
                    continue
                
                bank_extraction_time = time.time() - bank_start_time
                logger.info(f"Bank information extraction completed in {bank_extraction_time:.2f} seconds")
                
                # Process and clean the bank data
                processed_data = process_bank_data(bank_data)
                
                # Add metadata
                processed_data["metadata"] = {
                    "pdf_file": pdf_file,
                    "processed_at": datetime.utcnow().isoformat(),
                    "document_type": "Final Terms",
                    "extraction_time": extraction_time,
                    "bank_extraction_time": bank_extraction_time
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
            output_file = os.path.join('results', 'bank_info.json')
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            logger.info(f"\nIntermediate results saved to {output_file}")
        
        logger.info("\nProcessing complete!")
    finally:
        # Clean up logging handlers
        for handler in handlers:
            handler.close()
            logger.removeHandler(handler)

if __name__ == "__main__":
    main() 