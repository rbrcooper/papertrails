#!/usr/bin/env python3
"""
Quick AI Integration Test
------------------------
Fast test to verify AI extraction works without processing full PDFs.
"""

import os
import sys
import logging
from pathlib import Path

# Add the parent directory to the path to import from processes
sys.path.append(str(Path(__file__).parent.parent))

from processes.pdf_extraction.extractors.ai_bank_extractor import AIBankExtractor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def quick_ai_test():
    """Quick test of AI bank extraction with sample text"""
    
    logger.info("=== Quick AI Integration Test ===")
    
    # Sample text that should contain banks
    sample_text = """
    JOINT BOOKRUNNERS AND JOINT LEAD MANAGERS
    
    Goldman Sachs International
    J.P. Morgan Securities plc
    BNP Paribas
    Deutsche Bank AG, London Branch
    
    CO-MANAGERS
    
    Barclays Bank PLC
    Citigroup Global Markets Limited
    HSBC Bank plc
    """
    
    # Test AI extractor
    ai_extractor = AIBankExtractor(debug_mode=True)
    
    # Check connection
    if not ai_extractor.test_connection():
        logger.error("❌ Ollama connection failed")
        return False
    
    logger.info("✅ Ollama connected successfully")
    
    # Test extraction
    logger.info("Testing AI extraction with sample text...")
    result = ai_extractor.extract(sample_text)
    
    banks_found = result.get('extracted_banks', [])
    logger.info(f"✅ AI extraction complete:")
    logger.info(f"   Banks found: {len(banks_found)}")
    logger.info(f"   Banks: {banks_found}")
    logger.info(f"   Method: {result.get('extraction_method')}")
    logger.info(f"   Confidence: {result.get('confidence')}")
    
    if banks_found:
        logger.info("🎉 AI integration is working!")
        return True
    else:
        logger.warning("⚠️ No banks found - may need prompt tuning")
        return False

if __name__ == "__main__":
    success = quick_ai_test()
    if success:
        print("\n✅ AI integration test PASSED")
    else:
        print("\n❌ AI integration test needs attention") 