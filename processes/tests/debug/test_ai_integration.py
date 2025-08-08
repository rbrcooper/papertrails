#!/usr/bin/env python3
"""
Test AI Integration in Main Pipeline
-----------------------------------
Quick test to verify AI extraction works in the integrated pipeline.
"""

import os
import sys
import logging
from pathlib import Path

# Add the parent directory to the path to import from processes
sys.path.append(str(Path(__file__).parent.parent))

from processes.pdf_extractor import PDFExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_ai_integration():
    """Test AI integration in the main PDF extractor"""
    
    # Test PDFs (use the ones we know work)
    test_pdfs = [
        "data/downloads/AKER BP ASA - 549300NFTY73920OYK69/Final terms, including the  summary of the individual issue annexed to them_28_05_2024.pdf",
        "data/downloads/TotalEnergies SE_Final_terms_including_the_summary_of_the_individual_issue_annexed_to_them__downloadFile.pdf"
    ]
    
    logger.info("Testing AI Integration in Main Pipeline")
    logger.info("=" * 50)
    
    # Test with AI enabled
    logger.info("Testing with AI extraction enabled...")
    pdf_extractor_ai = PDFExtractor(debug_mode=True, use_ai_extraction=True)
    
    for pdf_path in test_pdfs:
        if not os.path.exists(pdf_path):
            logger.warning(f"PDF not found: {pdf_path}")
            continue
            
        logger.info(f"\nProcessing: {Path(pdf_path).name}")
        
        try:
            result = pdf_extractor_ai.process_single_pdf(pdf_path)
            
            if result:
                banks = result.get('extracted_banks', [])
                ai_used = result.get('ai_extraction_used', False)
                ai_metadata = result.get('ai_extraction_metadata', {})
                
                logger.info(f"✅ Success: {len(banks)} banks found")
                logger.info(f"   AI Used: {ai_used}")
                if ai_used:
                    logger.info(f"   Model: {ai_metadata.get('model_used', 'Unknown')}")
                    logger.info(f"   Method: {ai_metadata.get('extraction_method', 'Unknown')}")
                    logger.info(f"   Confidence: {ai_metadata.get('confidence', 'Unknown')}")
                logger.info(f"   Banks: {banks}")
            else:
                logger.error("❌ Extraction failed - no result returned")
                
        except Exception as e:
            logger.error(f"❌ Error processing {pdf_path}: {e}")
    
    # Test with AI disabled (fallback)
    logger.info("\n" + "=" * 50)
    logger.info("Testing with AI extraction disabled (regex fallback)...")
    pdf_extractor_regex = PDFExtractor(debug_mode=True, use_ai_extraction=False)
    
    for pdf_path in test_pdfs:
        if not os.path.exists(pdf_path):
            continue
            
        logger.info(f"\nProcessing: {Path(pdf_path).name}")
        
        try:
            result = pdf_extractor_regex.process_single_pdf(pdf_path)
            
            if result:
                banks = result.get('extracted_banks', [])
                ai_used = result.get('ai_extraction_used', False)
                
                logger.info(f"✅ Success: {len(banks)} banks found")
                logger.info(f"   AI Used: {ai_used}")
                logger.info(f"   Banks: {banks}")
            else:
                logger.error("❌ Extraction failed - no result returned")
                
        except Exception as e:
            logger.error(f"❌ Error processing {pdf_path}: {e}")
    
    logger.info("\n" + "=" * 50)
    logger.info("AI Integration Test Complete!")

if __name__ == "__main__":
    test_ai_integration() 