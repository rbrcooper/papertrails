"""
AI Metadata Extractor using Ollama
-----------------------------------
Fallback extractor for coupon rates and currency/issue size when regex fails.
Mirrors the AIBankExtractor pattern: only called when regex extraction returns
low confidence.
"""

import json
import logging
import requests
import hashlib
from typing import Dict, Optional, Any
from pathlib import Path
from datetime import datetime


class AIMetadataExtractor:
    """
    AI-based metadata extractor using Ollama for coupon rate and currency extraction.
    Used as a fallback when regex-based extraction fails or returns low confidence.
    """

    def __init__(self, model_name: str = "llama3.1:8b", base_url: str = "http://localhost:11434", debug_mode: bool = False):
        self.model_name = model_name
        self.base_url = base_url
        self.api_url = f"{base_url}/api/generate"
        self.debug_mode = debug_mode
        self.logger = logging.getLogger(__name__)

        # Simple file-based cache
        self.cache_dir = Path("data/test_cache/ai_metadata")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def test_connection(self) -> bool:
        """Check if Ollama is running and the model is available."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]
                return self.model_name in model_names
            return False
        except Exception:
            return False

    def _query_llm(self, prompt: str, cache_key: str) -> Optional[str]:
        """Send a prompt to Ollama and return the raw response, with caching."""
        # Check cache
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                    if self.debug_mode:
                        self.logger.info(f"AIMetadata: Cache hit for {cache_key[:12]}")
                    return cached.get('response')
            except Exception:
                pass

        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.05, "num_ctx": 4096}
                },
                timeout=120
            )

            if response.status_code == 200:
                result = response.json().get('response', '')

                # Cache the result
                try:
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            'response': result,
                            'cached_at': datetime.now().isoformat(),
                            'model': self.model_name
                        }, f, indent=2)
                except Exception:
                    pass

                return result

        except Exception as e:
            self.logger.error(f"AIMetadata: LLM query failed: {e}")

        return None

    def _find_relevant_section(self, text: str, keywords: list, window: int = 2000) -> str:
        """Find a section of text near keywords, for sending to the LLM."""
        text_lower = text.lower()
        for kw in keywords:
            pos = text_lower.find(kw.lower())
            if pos != -1:
                start = max(0, pos - 300)
                end = min(len(text), pos + window)
                return text[start:end]
        # Fallback: return first chunk
        return text[:window]

    def extract_coupon(self, text: str) -> Dict[str, Any]:
        """
        Extract coupon rate and type using LLM.

        Returns dict with 'coupon_rate' and 'coupon_type' keys.
        """
        section = self._find_relevant_section(
            text,
            ['interest', 'coupon', 'zinssatz', 'rate of interest', 'fixed rate',
             'floating rate', 'interest basis', 'zinsen']
        )

        cache_key = hashlib.sha256(
            f"coupon:{self.model_name}:{section[:1500]}".encode()
        ).hexdigest()

        prompt = f"""You are extracting bond coupon information from a prospectus document.
The document may be in English or German.

Extract:
1. The coupon rate (annual interest rate as a number, e.g. "3.250")
2. The coupon type ("fixed rate", "floating rate", or "zero coupon")

Return ONLY a JSON object like this, nothing else:
{{"coupon_rate": "3.250", "coupon_type": "fixed rate"}}

If you cannot find the information, return:
{{"coupon_rate": null, "coupon_type": null}}

Text to extract from:
{section[:2000]}

Return ONLY the JSON object."""

        raw = self._query_llm(prompt, cache_key)
        if not raw:
            return {'coupon_rate': None, 'coupon_type': None}

        return self._parse_json_response(raw, ['coupon_rate', 'coupon_type'])

    def extract_currency(self, text: str) -> Dict[str, Any]:
        """
        Extract currency and issue size using LLM.

        Returns dict with 'currency' and 'issue_size' keys.
        """
        section = self._find_relevant_section(
            text,
            ['aggregate nominal amount', 'issue size', 'principal amount',
             'nominal amount', 'gesamtnennbetrag', 'currency', 'EUR', 'USD', 'GBP']
        )

        cache_key = hashlib.sha256(
            f"currency:{self.model_name}:{section[:1500]}".encode()
        ).hexdigest()

        prompt = f"""You are extracting bond issue information from a prospectus document.
The document may be in English or German.

Extract:
1. The currency (ISO code like "EUR", "USD", "GBP")
2. The issue size / aggregate nominal amount (as a plain number, e.g. "500000000")

IMPORTANT: Extract the SERIES or TRANCHE amount, NOT the programme limit.
For example, if you see "EUR 14,000,000,000 Programme" and "EUR 500,000,000 Notes",
extract 500000000 as the issue size.

Return ONLY a JSON object like this, nothing else:
{{"currency": "EUR", "issue_size": "500000000"}}

If you cannot find the information, return:
{{"currency": null, "issue_size": null}}

Text to extract from:
{section[:2000]}

Return ONLY the JSON object."""

        raw = self._query_llm(prompt, cache_key)
        if not raw:
            return {'currency': None, 'issue_size': None}

        return self._parse_json_response(raw, ['currency', 'issue_size'])

    def _parse_json_response(self, raw: str, expected_keys: list) -> Dict[str, Any]:
        """Parse a JSON response from the LLM, handling common formatting issues."""
        result = {k: None for k in expected_keys}

        if not raw:
            return result

        # Find JSON object in response
        json_start = raw.find('{')
        json_end = raw.rfind('}') + 1

        if json_start >= 0 and json_end > json_start:
            try:
                parsed = json.loads(raw[json_start:json_end])
                if isinstance(parsed, dict):
                    for key in expected_keys:
                        val = parsed.get(key)
                        if val is not None and str(val).lower() not in ('null', 'none', 'n/a', ''):
                            result[key] = str(val)
                    if self.debug_mode:
                        self.logger.info(f"AIMetadata: Parsed result: {result}")
                    return result
            except json.JSONDecodeError as e:
                if self.debug_mode:
                    self.logger.warning(f"AIMetadata: JSON parse error: {e}")

        return result
