"""
AI-based Bank Extractor using Ollama
-----------------------------------
Intelligent bank extraction using local Ollama models with smart chunking strategy.
Addresses the main issue: AI only seeing first 1500 characters by analyzing multiple document sections.
"""

import json
import re
import time
import logging
import os
import requests
import hashlib
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
from ...utils.decorators import retry, NETWORK_ERRORS

_DEALER_TABLE_ANCHOR = re.compile(
    r"dealer\s*/\s*management group\s*\(specify\)|platzeur\s*/\s*bankenkonsortium\s*\(angeben\)"
    r"|(?:global coordinators and )?active bookrunners",
    re.IGNORECASE,
)
# Fallback only: ICMA "If syndicated … names of Managers/Dealers". Not compiled into
# the preferred anchor — Total/ESB hit "If syndicated, names of Managers" ~40 chars
# before "Active Bookrunners"; a combined regex would move the window start.
_DEALER_SYNDICATED_FALLBACK = re.compile(
    r"if syndicated\s*[:.,]?\s*(?:.{0,80}?)names(?: of(?: the)? (?:managers|dealers))?",
    re.IGNORECASE | re.DOTALL,
)
_BANK_LEGAL_SUFFIX = (
    r"Bank Ireland PLC|Bank AG|Bank GmbH|Bank Europe GmbH|Bank International AG|"
    r"Group Bank AG|Securities Europe GmbH|Soci[eé]t[eé]\s+G[eé]n[eé]rale|Socit Gnrale"
)
_FTWS_DEALER_LEGAL_NAMES = (
    "Barclays Bank Ireland PLC",
    "Erste Group Bank AG",
    "Mizuho Securities Europe GmbH",
    "Raiffeisen Bank International AG",
    "UniCredit Bank GmbH",
    "Goldman Sachs Bank Europe SE",
    "BofA Securities Europe SA",
    "HSBC Continental Europe",
    "HSBC Bank plc",
    "Natixis",
    "SMBC Bank EU AG",
    "ABN AMRO Bank N.V.",
    "Nordea Bank Abp",
    "Skandinaviska Enskilda Banken AB (publ)",
    "Wells Fargo Securities Europe S.A.",
    "Coöperatieve Rabobank U.A.",
    "Crédit Agricole Corporate and Investment Bank",
    "Deutsche Bank Aktiengesellschaft",
    "NatWest Markets N.V.",
    "Crédit Industriel et Commercial S.A.",
    "Banco Santander, S.A.",
    "Commerzbank Aktiengesellschaft",
    "ING Bank N.V.",
    "J.P. Morgan SE",
    "MUFG Securities (Europe) N.V.",
)
_SOC_GEN_RE = re.compile(r"Soci[eé]t[eé]\s+G[eé]n[eé]rale|Socit\s+Gnrale", re.IGNORECASE)
_COVER_AS_BOOKRUNNERS_PREFIX = re.compile(
    r"as\s+(?:global\s+coordinators\s+and\s+)?$",
    re.IGNORECASE,
)


def _is_cover_as_bookrunners_match(text: str, match: re.Match) -> bool:
    """Cover 'as Active Bookrunners' / 'as Global Coordinators and Active Bookrunners'."""
    if not re.search(r"active\s+bookrunners", match.group(0), re.IGNORECASE):
        return False
    return bool(_COVER_AS_BOOKRUNNERS_PREFIX.search(text[: match.start()]))


def _whitelist_name_in_block(legal_name: str, block_cf: str) -> bool:
    """True if legal_name is a token in block_cf, not a prefix (J.P. Morgan SE vs Securities)."""
    needle = legal_name.casefold()
    start = 0
    while True:
        i = block_cf.find(needle, start)
        if i < 0:
            return False
        before_ok = i == 0 or not block_cf[i - 1].isalnum()
        after_i = i + len(needle)
        after_ok = after_i >= len(block_cf) or not block_cf[after_i].isalnum()
        if before_ok and after_ok:
            return True
        start = i + 1

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
        
        self.request_timeout = int(os.environ.get("OLLAMA_TIMEOUT", "120"))
        
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
    
    def extract_dealer_management_banks(self, text: str) -> List[Dict[str, Any]]:
        """Regex extraction for FTWS dealer/management tables (OMV-style final terms)."""
        preferred = None
        for candidate in _DEALER_TABLE_ANCHOR.finditer(text):
            if _is_cover_as_bookrunners_match(text, candidate):
                continue
            preferred = candidate
            break

        if preferred is not None:
            banks = self._collect_dealer_banks(text, preferred)
            if banks:
                return banks

        fallback = _DEALER_SYNDICATED_FALLBACK.search(text)
        if fallback is None:
            return []
        return self._collect_dealer_banks(text, fallback)

    def _collect_dealer_banks(self, text: str, match: re.Match) -> List[Dict[str, Any]]:
        start = match.end()
        text_l = text.lower()
        end = min(len(text), start + 6000)
        for marker in (
            "platzeur/bankenkonsortium",
            "subscription agreement",
            "firm commitment",
            "management/underwriting commission",
            "stabilisation manager",
            "if non-syndicated",
            "date of syndication agreement",
            "u.s. selling restrictions",
        ):
            pos = text_l.find(marker, start)
            if pos != -1:
                end = min(end, pos)

        block = text[start:end]
        block_cf = block.casefold()
        seen: set[str] = set()
        banks: List[Dict[str, Any]] = []

        def _add(name: str) -> None:
            key = re.sub(r"\s+", " ", name.lower())
            if key in seen:
                return
            seen.add(key)
            banks.append({"raw_name": name, "role": "Dealer", "confidence": 0.92})

        for legal_name in _FTWS_DEALER_LEGAL_NAMES:
            if _whitelist_name_in_block(legal_name, block_cf):
                _add(legal_name)

        if _SOC_GEN_RE.search(block):
            _add("Société Générale")

        if self.known_banks:
            extra: List[str] = []
            for info in self.known_banks.values():
                std = info.get("standard_name") or ""
                if len(std) >= 12 and std not in _FTWS_DEALER_LEGAL_NAMES:
                    extra.append(std)
                for alias in info.get("aliases", []):
                    if len(alias) >= 14:
                        extra.append(alias)
            for name in sorted(set(extra), key=len, reverse=True):
                if name in block:
                    _add(name)

        # Drop shorter names that are substrings of a longer match (e.g. "Goldman Sachs").
        pruned: List[Dict[str, Any]] = []
        for b in sorted(banks, key=lambda x: len(x["raw_name"]), reverse=True):
            key = b["raw_name"].lower()
            if any(
                key != other["raw_name"].lower() and key in other["raw_name"].lower()
                for other in pruned
            ):
                continue
            pruned.append(b)
        return pruned

    def find_bank_sections(self, text: str, syndicate_only: bool = False) -> List[Dict[str, Any]]:
        """Find sections likely to contain bank information."""
        if syndicate_only:
            bank_section_keywords = [
                "dealer/management group",
                "platzeur/bankenkonsortium",
                "joint lead manager", "lead manager", "bookrunner", "book runner",
                "active bookrunner", "global coordinator", "underwriter", "syndicate",
                "joint lead", "co-lead", "management and underwriting",
            ]
        else:
            bank_section_keywords = [
                "bookrunner", "book runner", "joint lead manager", "lead manager",
                "global coordinator", "active bookrunner", "underwriter", "syndicate",
                "joint lead", "co-lead", "manager", "dealer", "arranger", "co-manager", "agent",
            ]
        
        sections = []
        text_lower = text.lower()
        
        for keyword in bank_section_keywords:
            pos = text_lower.find(keyword)
            if pos != -1:
                if keyword == "syndicate" and syndicate_only:
                    ctx = text_lower[max(0, pos - 250): pos + 250]
                    if any(
                        x in ctx
                        for x in (
                            "shareholder",
                            "change of control",
                            "core shareholder",
                            "beteiligungs",
                        )
                    ):
                        continue
                # Extract context around the keyword (expanded for better coverage)
                context_start = max(0, pos - 750)
                context_end = min(len(text), pos + 2250)
                context = text[context_start:context_end]
                
                sections.append({
                    'keyword': keyword,
                    'position': pos,
                    'context': context
                })
        
        sections.sort(key=lambda x: x['position'])
        return sections[:5]
    
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
                timeout=self.request_timeout
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
                        timeout=self.request_timeout
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
        blocklist = {
            "fiscal agent", "paying agent", "clearing system", "clearing",
            "registrar", "calculation agent", "any leading bank", "the managers",
        }
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
                if len(raw_name) < 2 or raw_name.lower() in blocklist:
                    continue

                role = bank.get('role', 'Unknown')
                rl = role.lower()
                if any(x in rl for x in ("fiscal agent", "paying agent", "clearing", "registrar")):
                    continue
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
    
    def extract(self, text: str, section_only: bool = False, max_pdf_chars: int = 80000) -> Dict[str, Any]:
        """
        Extract bank information using AI with smart chunking.

        For large documents (FTWS), syndicate sections only — no full-document fallback.
        """
        if self.debug_mode:
            self.logger.info(f"AI extraction for text ({len(text)} chars), section_only={section_only}")

        if not self.test_connection():
            return {
                'extracted_banks': [],
                'bank_sections': {},
                'error': 'Ollama not available',
                'extraction_method': 'ai_failed',
            }

        large_doc = len(text) > max_pdf_chars
        syndicate_only = section_only or large_doc

        if syndicate_only:
            dealer_banks = self.extract_dealer_management_banks(text)
            if len(dealer_banks) >= 3:
                return {
                    "extracted_banks": dealer_banks,
                    "bank_sections": {"dealer_table": "regex"},
                    "extraction_method": "dealer_table_regex",
                }

        bank_sections = self.find_bank_sections(text, syndicate_only=syndicate_only)
        all_banks = []

        if self.debug_mode:
            self.logger.info(f"Found {len(bank_sections)} potential bank sections")

        for i, section in enumerate(bank_sections, 1):
            chunk_info = f"section {i} ({section['keyword']})"
            banks = self.extract_banks_from_chunk(section['context'], chunk_info)
            all_banks.extend(banks)

        if not all_banks and not syndicate_only:
            first_chunk = text[:3000]
            all_banks.extend(self.extract_banks_from_chunk(first_chunk, "beginning"))
            if len(text) > 6000:
                middle_start = len(text) // 2 - 1500
                all_banks.extend(
                    self.extract_banks_from_chunk(
                        text[middle_start:middle_start + 3000], "middle"
                    )
                )
        elif not all_banks and syndicate_only:
            return {
                'extracted_banks': [],
                'bank_sections': {},
                'extraction_method': 'ftws_section_not_found',
                'error': 'No syndicate section found in large document',
            }
        
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
 