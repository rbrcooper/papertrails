#!/usr/bin/env python3
"""
Improved AI-based PDF extraction with intelligent chunking
Addresses the root cause: AI only seeing first 1500 characters
"""

import os
import json
import time
import logging
import argparse
import requests
from pathlib import Path
import sys
import re

# Add the parent directory to the path to import from processes
sys.path.append(str(Path(__file__).parent.parent))

from processes.pdf_extraction.core import ExtractionEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SmartOllamaExtractor:
    """Smart AI extractor that looks for banks throughout the document"""
    
    def __init__(self, model_name="llama3.1:8b", base_url="http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url
        self.api_url = f"{base_url}/api/generate"
        
    def test_connection(self):
        """Test if Ollama is running and accessible"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]
                logger.info(f"Ollama connected. Available models: {model_names}")
                return self.model_name in model_names
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Ollama: {e}")
            return False
    
    def find_bank_sections(self, text):
        """Find sections likely to contain bank information"""
        bank_section_keywords = [
            "underwriter", "manager", "arranger", "dealer", "syndicate",
            "bookrunner", "lead", "co-manager", "agent", "advisor"
        ]
        
        sections = []
        text_lower = text.lower()
        
        for keyword in bank_section_keywords:
            pos = text_lower.find(keyword)
            if pos != -1:
                # Extract context around the keyword (±500 chars)
                context_start = max(0, pos - 500)
                context_end = min(len(text), pos + 1000)
                context = text[context_start:context_end]
                
                sections.append({
                    'keyword': keyword,
                    'position': pos,
                    'context': context
                })
        
        # Sort by position and return top 3
        sections.sort(key=lambda x: x['position'])
        return sections[:3]
    
    def extract_banks_from_chunk(self, text_chunk, chunk_info=""):
        """Extract banks from a specific text chunk"""
        prompt = f"""Find bank names in this financial document text. Look for underwriters, managers, dealers.

Text {chunk_info}:
{text_chunk[:1000]}

Return only JSON: {{"banks": ["Bank Name 1", "Bank Name 2"]}}"""

        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1}
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result.get('response', '')
                
                try:
                    json_start = ai_response.find('{')
                    json_end = ai_response.rfind('}') + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        json_str = ai_response[json_start:json_end]
                        extracted_data = json.loads(json_str)
                        banks = extracted_data.get('banks', [])
                        
                        cleaned_banks = [bank.strip() for bank in banks if isinstance(bank, str) and len(bank.strip()) > 2]
                        
                        if cleaned_banks:
                            logger.info(f"Chunk {chunk_info}: Found {len(cleaned_banks)} banks: {cleaned_banks}")
                        
                        return cleaned_banks
                except json.JSONDecodeError:
                    logger.warning(f"JSON parse error for chunk {chunk_info}")
                    return []
            return []
                
        except Exception as e:
            logger.error(f"AI extraction failed for chunk {chunk_info}: {e}")
            return []
    
    def extract_bond_data(self, pdf_text: str, filename: str) -> dict:
        """Extract bond data using smart chunking strategy"""
        start_time = time.time()
        
        logger.info(f"Smart extraction for {filename} ({len(pdf_text)} chars)")
        
        # Find bank sections
        bank_sections = self.find_bank_sections(pdf_text)
        all_banks = []
        
        logger.info(f"Found {len(bank_sections)} potential bank sections")
        
        # Extract from each section
        for i, section in enumerate(bank_sections, 1):
            chunk_info = f"section {i} ({section['keyword']})"
            banks = self.extract_banks_from_chunk(section['context'], chunk_info)
            all_banks.extend(banks)
        
        # If no banks found, try document chunks
        if not all_banks:
            logger.info("No banks found in sections, trying document chunks...")
            
            # First chunk
            first_chunk = pdf_text[:1500]
            banks = self.extract_banks_from_chunk(first_chunk, "beginning")
            all_banks.extend(banks)
            
            # Middle chunk
            if len(pdf_text) > 3000:
                middle_start = len(pdf_text) // 2 - 750
                middle_chunk = pdf_text[middle_start:middle_start + 1500]
                banks = self.extract_banks_from_chunk(middle_chunk, "middle")
                all_banks.extend(banks)
        
        # Deduplicate
        unique_banks = list(dict.fromkeys(all_banks))  # Preserves order
        
        result = {
            "banks": unique_banks,
            "total_banks_found": len(unique_banks),
            "sections_analyzed": len(bank_sections),
            "extraction_time": time.time() - start_time,
            "extraction_method": "smart_chunking",
            "model_used": self.model_name,
            "confidence": "high" if unique_banks else "low"
        }
        
        logger.info(f"Smart extraction complete: {len(unique_banks)} unique banks found")
        return result

def main():
    # Test on the previously failed PDFs
    failed_pdfs = [
        "data/downloads/AKER BP ASA - 549300NFTY73920OYK69/Final terms, including the  summary of the individual issue annexed to them_28_05_2024.pdf",
        "data/downloads/TotalEnergies SE_Final_terms_including_the_summary_of_the_individual_issue_annexed_to_them__downloadFile.pdf"
    ]
    
    extraction_engine = ExtractionEngine()
    ai_extractor = SmartOllamaExtractor()
    
    if not ai_extractor.test_connection():
        logger.error("Cannot connect to Ollama")
        return
    
    for pdf_path in failed_pdfs:
        if not os.path.exists(pdf_path):
            logger.warning(f"PDF not found: {pdf_path}")
            continue
            
        logger.info(f"\n{'='*60}")
        logger.info(f"TESTING SMART EXTRACTION: {Path(pdf_path).name}")
        logger.info(f"{'='*60}")
        
        try:
            pdf_text = extraction_engine.extract_text(pdf_path)
            filename = Path(pdf_path).name
            result = ai_extractor.extract_bond_data(pdf_text, filename)
            
            logger.info(f"\nRESULT: {result}")
            
        except Exception as e:
            logger.error(f"Failed to process {pdf_path}: {e}")

if __name__ == "__main__":
    main() 