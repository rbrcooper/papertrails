"""
AI-based Bank Extractor using Ollama
-----------------------------------
Intelligent bank extraction using local Ollama models with smart chunking strategy.
Addresses the main issue: AI only seeing first 1500 characters by analyzing multiple document sections.
"""

import json
import time
import logging
import requests
from typing import Dict, List, Optional, Any
from pathlib import Path

class AIBankExtractor:
    """
    AI-based bank extractor using Ollama for intelligent extraction
    """
    
    def __init__(self, model_name: str = "llama3.1:8b", base_url: str = "http://localhost:11434", debug_mode: bool = False):
        """
        Initialize the AI bank extractor
        
        Args:
            model_name: Ollama model to use
            base_url: Ollama API base URL
            debug_mode: Enable debug logging
        """
        self.model_name = model_name
        self.base_url = base_url
        self.api_url = f"{base_url}/api/generate"
        self.debug_mode = debug_mode
        self.logger = logging.getLogger(__name__)
        
    def test_connection(self) -> bool:
        """Test if Ollama is running and accessible"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]
                if self.debug_mode:
                    self.logger.info(f"Ollama connected. Available models: {model_names}")
                return self.model_name in model_names
            return False
        except Exception as e:
            self.logger.error(f"Failed to connect to Ollama: {e}")
            return False
    
    def find_bank_sections(self, text: str) -> List[Dict[str, Any]]:
        """Find sections likely to contain bank information"""
        bank_section_keywords = [
            "underwriter", "manager", "arranger", "dealer", "syndicate",
            "bookrunner", "lead", "co-manager", "agent", "advisor",
            "joint lead", "co-lead", "global coordinator"
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
    
    def extract_banks_from_chunk(self, text_chunk: str, chunk_info: str = "") -> List[str]:
        """Extract banks from a specific text chunk"""
        prompt = f"""Extract bank names from this text. Look for underwriters, managers, dealers, bookrunners.

Text:
{text_chunk[:800]}

Return ONLY a JSON array like: ["Goldman Sachs", "JPMorgan", "Deutsche Bank"]"""

        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_ctx": 2048}
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result.get('response', '')
                
                try:
                    # Look for JSON array first
                    json_start = ai_response.find('[')
                    json_end = ai_response.rfind(']') + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        json_str = ai_response[json_start:json_end]
                        banks = json.loads(json_str)
                        
                        cleaned_banks = [bank.strip() for bank in banks if isinstance(bank, str) and len(bank.strip()) > 2]
                        
                        if cleaned_banks and self.debug_mode:
                            self.logger.info(f"Chunk {chunk_info}: Found {len(cleaned_banks)} banks: {cleaned_banks}")
                        
                        return cleaned_banks
                    
                    # Fallback: look for object format
                    json_start = ai_response.find('{')
                    json_end = ai_response.rfind('}') + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        json_str = ai_response[json_start:json_end]
                        extracted_data = json.loads(json_str)
                        banks = extracted_data.get('banks', [])
                        
                        cleaned_banks = [bank.strip() for bank in banks if isinstance(bank, str) and len(bank.strip()) > 2]
                        
                        if cleaned_banks and self.debug_mode:
                            self.logger.info(f"Chunk {chunk_info}: Found {len(cleaned_banks)} banks: {cleaned_banks}")
                        
                        return cleaned_banks
                        
                except json.JSONDecodeError:
                    if self.debug_mode:
                        self.logger.warning(f"JSON parse error for chunk {chunk_info}: {ai_response[:200]}")
                    return []
            return []
                
        except Exception as e:
            self.logger.error(f"AI extraction failed for chunk {chunk_info}: {e}")
            return []
    
    def extract(self, text: str) -> Dict[str, Any]:
        """
        Extract bank information using AI with smart chunking
        
        Args:
            text: PDF text content
            
        Returns:
            Dictionary with extracted banks and metadata
        """
        start_time = time.time()
        
        if self.debug_mode:
            self.logger.info(f"AI extraction for text ({len(text)} chars)")
        
        # Test connection first
        if not self.test_connection():
            return {
                'extracted_banks': [],
                'bank_sections': {},
                'error': 'Ollama not available',
                'extraction_method': 'ai_failed'
            }
        
        # Find bank sections
        bank_sections = self.find_bank_sections(text)
        all_banks = []
        
        if self.debug_mode:
            self.logger.info(f"Found {len(bank_sections)} potential bank sections")
        
        # Extract from each section
        for i, section in enumerate(bank_sections, 1):
            chunk_info = f"section {i} ({section['keyword']})"
            banks = self.extract_banks_from_chunk(section['context'], chunk_info)
            all_banks.extend(banks)
        
        # If no banks found, try document chunks
        if not all_banks:
            if self.debug_mode:
                self.logger.info("No banks found in sections, trying document chunks...")
            
            # First chunk
            first_chunk = text[:1500]
            banks = self.extract_banks_from_chunk(first_chunk, "beginning")
            all_banks.extend(banks)
            
            # Middle chunk
            if len(text) > 3000:
                middle_start = len(text) // 2 - 750
                middle_chunk = text[middle_start:middle_start + 1500]
                banks = self.extract_banks_from_chunk(middle_chunk, "middle")
                all_banks.extend(banks)
        
        # Deduplicate
        unique_banks = list(dict.fromkeys(all_banks))  # Preserves order
        
        result = {
            'extracted_banks': unique_banks,
            'bank_sections': {f"section_{i}": section for i, section in enumerate(bank_sections, 1)},
            'total_banks_found': len(unique_banks),
            'sections_analyzed': len(bank_sections),
            'extraction_time': time.time() - start_time,
            'extraction_method': 'ai_smart_chunking',
            'model_used': self.model_name,
            'confidence': 'high' if unique_banks else 'low'
        }
        
        if self.debug_mode:
            self.logger.info(f"AI extraction complete: {len(unique_banks)} unique banks found")
        
        return result 