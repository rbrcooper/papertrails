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
import hashlib
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
from ...utils.decorators import retry, NETWORK_ERRORS

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
        
        # Cache configuration
        self.cache_dir = Path("data/test_cache/ai_extraction")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_index_file = self.cache_dir / "cache_index.json"
        self.cache_index = self._load_cache_index()
        
        # Load known banks for prompting hints
        self.known_banks = self._load_known_banks()

    def _load_known_banks(self) -> Dict[str, Any]:
        """Load canonical bank names to use as LLM hints."""
        bank_file = Path("data/bank_names.json")
        if bank_file.exists():
            try:
                with open(bank_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Could not load bank_names.json for hints: {e}")
        return {}
        
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
    
    def _load_cache_index(self) -> Dict[str, Any]:
        """Load the cache index from disk."""
        if not self.cache_index_file.exists():
            return {}
        try:
            with open(self.cache_index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.warning(f"Could not load cache index: {e}")
            return {}
    
    def _save_cache_index(self):
        """Save the cache index to disk."""
        try:
            with open(self.cache_index_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache_index, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.warning(f"Could not save cache index: {e}")
    
    def _get_cache_key(self, chunk_text: str) -> str:
        """Generate cache key from model name and chunk text."""
        cache_input = f"{self.model_name}:{chunk_text[:1500]}"
        return hashlib.sha256(cache_input.encode('utf-8')).hexdigest()
    
    def _get_cache_entry(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached extraction result if available."""
        if cache_key not in self.cache_index:
            return None
        
        cache_entry = self.cache_index[cache_key]
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if not cache_file.exists():
            # Cache entry exists but file is missing - clean up
            del self.cache_index[cache_key]
            self._save_cache_index()
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                if self.debug_mode:
                    self.logger.debug(f"Cache hit for key {cache_key[:8]}...")
                return cached_data.get('banks', [])
        except Exception as e:
            self.logger.warning(f"Could not load cache file {cache_file}: {e}")
            return None
    
    def _save_cache_entry(self, cache_key: str, banks: List[Dict[str, Any]]):
        """Save extraction result to cache."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            cache_data = {
                'banks': banks,
                'cached_at': datetime.now().isoformat(),
                'model': self.model_name
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            # Update index
            self.cache_index[cache_key] = {
                'cached_at': cache_data['cached_at'],
                'model': self.model_name,
                'bank_count': len(banks)
            }
            self._save_cache_index()
            
            if self.debug_mode:
                self.logger.debug(f"Cached extraction result for key {cache_key[:8]}...")
        except Exception as e:
            self.logger.warning(f"Could not save cache entry: {e}")
    
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
                # Extract context around the keyword (expanded for better coverage)
                context_start = max(0, pos - 750)
                context_end = min(len(text), pos + 2250)
                context = text[context_start:context_end]
                
                sections.append({
                    'keyword': keyword,
                    'position': pos,
                    'context': context
                })
        
        # Sort by position and return top 3
        sections.sort(key=lambda x: x['position'])
        return sections[:3]
    
    @retry(max_retries=3, delay=5, backoff=2, exceptions=NETWORK_ERRORS)
    def extract_banks_from_chunk(self, text_chunk: str, chunk_info: str = "") -> List[Dict[str, Any]]:
        """
        Extract banks from a specific text chunk using structured JSON output.
        Returns list of bank objects with raw_name, role, and confidence.
        
        Retries network errors with exponential backoff.
        """
        # Check cache first
        cache_key = self._get_cache_key(text_chunk)
        cached_result = self._get_cache_entry(cache_key)
        if cached_result is not None:
            if self.debug_mode:
                self.logger.info(f"Chunk {chunk_info}: Cache hit, returning {len(cached_result)} banks")
            return cached_result
        
        # Build known banks hint from bank_names.json
        known_banks_hint = ", ".join(sorted(set(
            info.get("standard_name", key)
            for key, info in self.known_banks.items()
        ))) if self.known_banks else ""

        # Prepare prompt with strict JSON schema and few-shot examples
        prompt = f"""You are extracting bank names from a bond prospectus document. 
Your task: identify every bank mentioned as an underwriter, manager, dealer, bookrunner, 
arranger, or similar role.

CRITICAL INSTRUCTION: If multiple banks are listed together in a continuous string or separated by 'and' (e.g., 'global coordinators barclays bank plc hsbc natixis'), you MUST separate them into individual bank array objects. Never return them combined.

Here are some known major banks for reference (the document may contain others not listed here):
{known_banks_hint}

Example 1 (input text):
"Joint Lead Managers: BNP Paribas, Deutsche Bank AG, J.P. Morgan Securities plc"
Example 1 (output):
[
  {{"raw_name": "BNP Paribas", "role": "Joint Lead Manager", "confidence": 0.95}},
  {{"raw_name": "Deutsche Bank AG", "role": "Joint Lead Manager", "confidence": 0.95}},
  {{"raw_name": "J.P. Morgan Securities plc", "role": "Joint Lead Manager", "confidence": 0.95}}
]

Example 2 (input text):
"Dealer: Barclays Bank PLC"
Example 2 (output):
[
  {{"raw_name": "Barclays Bank PLC", "role": "Dealer", "confidence": 0.95}}
]

Example 3 (continuous text):
"global coordinators and active bookrunners barclays bank ireland plc goldman sachs bank europe se joint active bookrunners bofa securities europe sa hsbc"
Example 3 (output):
[
  {{"raw_name": "Barclays Bank Ireland PLC", "role": "Active Bookrunner", "confidence": 0.90}},
  {{"raw_name": "Goldman Sachs Bank Europe SE", "role": "Active Bookrunner", "confidence": 0.90}},
  {{"raw_name": "BofA Securities Europe SA", "role": "Active Bookrunner", "confidence": 0.90}},
  {{"raw_name": "HSBC", "role": "Active Bookrunner", "confidence": 0.90}}
]

Now extract from this text:
{text_chunk[:2000]}

Return ONLY a JSON array. No other text."""

        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_ctx": 4096}
                },
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result.get('response', '')
                
                # Try to parse structured JSON array
                banks = self._parse_structured_response(ai_response, chunk_info)
                
                # If parsing failed, try once more with stricter prompt
                if not banks:
                    if self.debug_mode:
                        self.logger.warning(f"Chunk {chunk_info}: First parse failed, retrying with stricter prompt...")
                    retry_prompt = f"""Return ONLY a JSON array per this schema:

[
  {{"raw_name": "Bank Name", "role": "Role", "confidence": 0.9}}
]

Text to extract from:
{text_chunk[:2000]}

Return ONLY the JSON array, nothing else."""
                    
                    retry_response = requests.post(
                        self.api_url,
                        json={
                        "model": self.model_name,
                        "prompt": retry_prompt,
                        "stream": False,
                        "options": {"temperature": 0.05, "num_ctx": 4096}
                    },
                        timeout=120
                    )
                    
                    if retry_response.status_code == 200:
                        retry_result = retry_response.json()
                        banks = self._parse_structured_response(retry_result.get('response', ''), chunk_info)
                
                # Clean and validate banks
                cleaned_banks = self._clean_and_validate_banks(banks)
                
                if cleaned_banks:
                    # Cache the result
                    self._save_cache_entry(cache_key, cleaned_banks)
                    if self.debug_mode:
                        self.logger.info(f"Chunk {chunk_info}: Found {len(cleaned_banks)} banks: {[b['raw_name'] for b in cleaned_banks]}")
                else:
                    if self.debug_mode:
                        self.logger.warning(f"Chunk {chunk_info}: No banks extracted")
                
                return cleaned_banks
            
            return []
                
        except Exception as e:
            self.logger.error(f"AI extraction failed for chunk {chunk_info}: {e}")
            return []
    
    def _parse_structured_response(self, ai_response: str, chunk_info: str = "") -> List[Dict[str, Any]]:
        """
        Parse AI response to extract structured bank objects.
        Handles various JSON formats and extracts the first valid JSON array.
        """
        if not ai_response or not ai_response.strip():
            return []
        
        # Try to find JSON array in response
        json_start = ai_response.find('[')
        json_end = ai_response.rfind(']') + 1
        
        if json_start >= 0 and json_end > json_start:
            try:
                json_str = ai_response[json_start:json_end]
                parsed = json.loads(json_str)
                
                if isinstance(parsed, list):
                    return parsed
                elif isinstance(parsed, dict):
                    # Might be wrapped in object
                    if 'banks' in parsed:
                        return parsed['banks'] if isinstance(parsed['banks'], list) else []
                    return []
            except json.JSONDecodeError as e:
                if self.debug_mode:
                    self.logger.debug(f"JSON parse error for {chunk_info}: {str(e)[:100]}")
                return []
        
        # Fallback: try to find string array (backward compatibility)
        if '[' in ai_response and ']' in ai_response:
            try:
                # Try to extract and parse as simple string array
                json_start = ai_response.find('[')
                json_end = ai_response.rfind(']') + 1
                json_str = ai_response[json_start:json_end]
                banks = json.loads(json_str)
                
                if isinstance(banks, list) and all(isinstance(b, str) for b in banks):
                    # Convert string list to structured objects
                    return [
                        {
                            'raw_name': bank.strip(),
                            'role': 'Unknown',
                            'confidence': 0.75
                        }
                        for bank in banks if isinstance(bank, str) and len(bank.strip()) > 2
                    ]
            except json.JSONDecodeError:
                pass
        
        return []
    
    def _clean_and_validate_banks(self, banks: List[Any]) -> List[Dict[str, Any]]:
        """
        Clean and validate bank objects, ensuring they conform to schema.
        Handles both new structured format and legacy string lists.
        """
        cleaned = []
        
        for bank in banks:
            # Handle legacy string format
            if isinstance(bank, str):
                bank_name = bank.strip()
                if len(bank_name) > 2:
                    cleaned.append({
                        'raw_name': bank_name,
                        'role': 'Unknown',
                        'confidence': 0.75
                    })
                continue
            
            # Handle structured object format
            if isinstance(bank, dict):
                raw_name = bank.get('raw_name') or bank.get('name') or bank.get('bank_name')
                if not raw_name or not isinstance(raw_name, str):
                    continue
                
                raw_name = raw_name.strip()
                if len(raw_name) < 2:
                    continue
                
                role = bank.get('role', 'Unknown')
                if not isinstance(role, str):
                    role = 'Unknown'
                
                confidence = bank.get('confidence', 0.75)
                if not isinstance(confidence, (int, float)):
                    confidence = 0.75
                confidence = max(0.0, min(1.0, float(confidence)))
                
                cleaned.append({
                    'raw_name': raw_name,
                    'role': role,
                    'confidence': confidence
                })
        
        return cleaned
    
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
            
            # First chunk (expanded)
            first_chunk = text[:3000]
            banks = self.extract_banks_from_chunk(first_chunk, "beginning")
            all_banks.extend(banks)
            
            # Middle chunk (expanded)
            if len(text) > 6000:
                middle_start = len(text) // 2 - 1500
                middle_chunk = text[middle_start:middle_start + 3000]
                banks = self.extract_banks_from_chunk(middle_chunk, "middle")
                all_banks.extend(banks)
        
        # Deduplicate and merge banks found across multiple chunks
        merged_banks = {}
        for b in all_banks:
            raw_name = b.get('raw_name', '')
            role = b.get('role', 'Unknown')
            conf = b.get('confidence', 0.0)
            
            # Use lowercase for deduplication key
            key = raw_name.lower().strip()
            
            if key not in merged_banks:
                merged_banks[key] = b
            else:
                # Keep the higher confidence one
                if conf > merged_banks[key].get('confidence', 0.0):
                    merged_banks[key] = b
                    
        final_banks = list(merged_banks.values())
        
        return {
            'extracted_banks': final_banks,
            'bank_sections': {f'section_{i}': s['keyword'] for i, s in enumerate(bank_sections, 1)},
            'extraction_method': 'ai_ollama'
        }
 