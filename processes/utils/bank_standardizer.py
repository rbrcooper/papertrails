import json
import re
from typing import Dict, List, Tuple, Optional, Set, Any
from fuzzywuzzy import fuzz, process

class BankStandardizer:
    """
    Utility for standardizing bank names using exact and fuzzy matching against 
    a dictionary of known bank names and their variations.
    """
    def __init__(self, bank_names_file: str = "data/bank_names.json", debug_mode: bool = False):
        """
        Initialize the bank standardizer.
        
        Args:
            bank_names_file: Path to the JSON file containing bank name standards
            debug_mode: Enable debug prints
        """
        self.bank_names_file = bank_names_file
        self.debug_mode = debug_mode
        self.bank_data: Dict[str, Dict[str, Any]] = self._load_bank_data(bank_names_file)
        self.all_aliases: Dict[str, str] = self._prepare_aliases()
        # For fuzzy matching against canonical forms if needed later, though current fuzzy matches aliases
        self.canonical_bank_keys: List[str] = list(self.bank_data.keys()) if self.bank_data else []
        
    def _load_bank_data(self, bank_names_file: str) -> Dict[str, Dict[str, Any]]:
        """
        Load bank aliases from JSON file. Keys are lowercased.
        """
        try:
            with open(bank_names_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Ensure all keys in bank_data are lowercase for consistency
                return {k.lower(): v for k, v in data.items()}
        except FileNotFoundError:
            if self.debug_mode:
                print(f"BankStandardizer Warning: Bank names file {bank_names_file} not found. Creating empty standardizer.")
            return {}
        except json.JSONDecodeError:
            if self.debug_mode:
                print(f"BankStandardizer Error: Bank names file {bank_names_file} contains invalid JSON. Using empty standardizer.")
            return {}
        except Exception as e: # Catch other potential errors during loading
            if self.debug_mode:
                print(f"BankStandardizer Error: Unexpected error loading {bank_names_file}: {e}")
            return {}
                
    def _prepare_aliases(self) -> Dict[str, str]:
        """
        Create lookup dictionary of all aliases (in lowercase) to their parent canonical bank keys (also lowercase).
        """
        alias_map = {}
        if not isinstance(self.bank_data, dict): 
            if self.debug_mode:
                print("BankStandardizer Error: self.bank_data is not a dictionary in _prepare_aliases.")
            return {}

        for bank_key, bank_info in self.bank_data.items():
            # bank_key is already lowercased from _load_bank_data
            alias_map[bank_key] = bank_key 
            
            std_name = bank_info.get("standard_name", "").lower()
            if std_name:
                alias_map[std_name] = bank_key

            for alias in bank_info.get("aliases", []):
                if isinstance(alias, str):
                    alias_map[alias.lower()] = bank_key
                elif self.debug_mode:
                    print(f"BankStandardizer Warning: Non-string alias '{alias}' found for bank key '{bank_key}'")
        return alias_map
            
    def _clean_name(self, name: str) -> str:
        """
        Clean bank name by removing common suffixes, legal entity types, 
        standardizing spacing, and punctuation.
        Args:
            name: The bank name to clean
        Returns:
            Cleaned bank name in lowercase
        """
        if not name or not isinstance(name, str):
            return ""
                
        cleaned_name = name.lower()
        
        suffixes_to_remove = [
            r'\s+s\.a\.s\.?$', r'\s+s\.p\.a\.?$', r'\s+s\.r\.l\.?$',
            r'\s+a\.s\.?$', r'\s+o\.y\.j\.?$',r'\s+k\.k\.?$',
            r'\s+gmbh\s*&\s*co\.?\s*kg\.?$', r'\s+aktiengesellschaft$',
            r'\s+(?:ag|a\.g\.|plc|p\.l\.c\.|ltd|l\.t\.d\.|limited|inc|incorporated|corp|corporation|llc|l\.l\.c\.|gmbh|s\.a\.|s\.r\.o\.|s\.a\.r\.l\.|s\.c\.a\.|b\.v\.|n\.v\.|oü|pty|kft|spolka z ograniczona odpowiedzialnoscia|sp z o o|sp\. z o\.o\.)\.?$',
            r'\s+(?:group|holding|company|co\.?|and company|& co\.?)$',
            r'\s+(?:bank|banc|banque|banca|banco)$', 
            r'\s+(?:asset management|capital|financial services|financial|investments|investment bank|investment banking|leasing|markets|securities|trust)$'
        ]
        
        for suffix_pattern in suffixes_to_remove:
            cleaned_name = re.sub(suffix_pattern, '', cleaned_name, flags=re.IGNORECASE)

        cleaned_name = re.sub(r'\s*\([^)]*\)', '', cleaned_name)
        cleaned_name = re.sub(r'[\(\)\[\]{}.,;:\'"`´’‘–—]', ' ', cleaned_name) 
        cleaned_name = re.sub(r'[-/&]', ' ', cleaned_name)
        cleaned_name = re.sub(r'\s+', ' ', cleaned_name).strip()
        
        abbreviations = {
            "db": "deutsche bank",
            "socgen": "societe generale",
            "bnp": "bnp paribas",
            "jpm": "jp morgan"
        }
        words = cleaned_name.split()
        cleaned_words = [abbreviations.get(word, word) for word in words]
        cleaned_name = " ".join(cleaned_words)
        cleaned_name = re.sub(r'\s+', ' ', cleaned_name).strip()

        if self.debug_mode and name.lower() != cleaned_name: # Compare with name.lower()
            print(f"BankStandardizer: Cleaned '{name}' to '{cleaned_name}'")
        return cleaned_name
            
    def standardize_name(self, raw_name: str) -> Dict[str, Any]:
        """
        Standardize a bank name using exact and fuzzy matching.
        
        Args:
            raw_name: The extracted bank name to standardize
                
        Returns:
            Dictionary with 'standardized_name', 'confidence', and 'method'.
            If no match, 'standardized_name' is the raw_name, confidence is 0.0.
        """
        original_raw_name = raw_name 
        if not raw_name or not isinstance(raw_name, str) or len(raw_name.strip()) < 2:
            return {
                'standardized_name': original_raw_name, 
                'confidence': 0.0, 
                'method': 'no_match_too_short'
            }
        
        raw_name_lower = raw_name.lower()
        if raw_name_lower in self.all_aliases:
            bank_key = self.all_aliases[raw_name_lower]
            standard_name = self.bank_data.get(bank_key, {}).get("standard_name", original_raw_name)
            if self.debug_mode: print(f"BankStandardizer: Direct match (raw_lower) for '{raw_name}' -> '{standard_name}'")
            return {
                'standardized_name': standard_name, 
                'confidence': 1.0, 
                'method': 'direct_match_raw_lower'
            }

        cleaned_name = self._clean_name(raw_name)
        
        if not cleaned_name:
             return {
                'standardized_name': original_raw_name, 
                'confidence': 0.0, 
                'method': 'no_match_empty_after_clean'
            }

        if cleaned_name in self.all_aliases:
            bank_key = self.all_aliases[cleaned_name]
            standard_name = self.bank_data.get(bank_key, {}).get("standard_name", original_raw_name)
            if self.debug_mode: print(f"BankStandardizer: Direct match (cleaned) for '{raw_name}' (cleaned: '{cleaned_name}') -> '{standard_name}'")
            return {
                'standardized_name': standard_name, 
                'confidence': 0.98, 
                'method': 'direct_match_cleaned'
            }
        
        best_match_bank_key = None
        highest_score = 0
        fuzzy_threshold = 85 

        candidate_aliases = list(self.all_aliases.keys())
        if not candidate_aliases:
            if self.debug_mode: print(f"BankStandardizer: No aliases for fuzzy matching for '{raw_name}' (cleaned: '{cleaned_name}')")
            return {'standardized_name': original_raw_name, 'confidence': 0.0, 'method': 'no_match_no_aliases'}

        # Use process.extractOne for potentially better performance and cleaner code for fuzzy matching
        # It finds the best match from a list of choices.
        # choices = self.all_aliases.keys() -> this might be too many if aliases are very numerous.
        # Let's refine to match against standard names or a curated list of variants for fuzzy matching.
        # The current self.all_aliases.keys() are all lowercased aliases.
        # The prompt for FuzzyMatcher implies matching against canonical_names.keys().
        # Let's use self.canonical_bank_keys which are the primary keys from bank_data (assumed canonical).
        
        choices_for_fuzzy = [self.bank_data[key].get("standard_name", key).lower() for key in self.canonical_bank_keys]
        choices_for_fuzzy = list(set(c for c in choices_for_fuzzy if c)) # Unique, non-empty choices

        if choices_for_fuzzy:
            # result_fuzzy is (choice, score, key_if_dict_choices)
            # Here, choices_for_fuzzy is a list of strings (standard names, lowercased).
            match_tuple = process.extractOne(cleaned_name, choices_for_fuzzy, scorer=fuzz.WRatio, score_cutoff=fuzzy_threshold)
            if match_tuple:
                matched_std_name_lower, score = match_tuple[0], match_tuple[1]
                # Now find which bank_key corresponds to this matched_std_name_lower
                # This is a bit indirect. Original iteration over all_aliases might be more direct for getting bank_key.
                # Let's revert to iterating over self.all_aliases for fuzzy matching to directly get the bank_key, 
                # similar to the original logic but using WRatio and the new return structure.
                pass # Reverting this specific process.extractOne approach for now.

        # Re-instating iterating over all_aliases for fuzzy matching (similar to old logic but cleaner)
        for alias_variant, bank_key_for_alias in self.all_aliases.items():
            # Skip very short aliases for fuzzy matching unless cleaned_name is also very short
            if len(alias_variant) < 3 and len(cleaned_name) > len(alias_variant) + 2:
                continue

            score = fuzz.WRatio(cleaned_name, alias_variant) # Using WRatio as per prompt suggestion
            
            if score > highest_score and score >= fuzzy_threshold:
                highest_score = score
                best_match_bank_key = bank_key_for_alias
        
        if best_match_bank_key:
            standard_name = self.bank_data.get(best_match_bank_key, {}).get("standard_name", original_raw_name)
            final_confidence = min(highest_score / 100.0, 1.0)
            if self.debug_mode: print(f"BankStandardizer: Fuzzy match for '{raw_name}' (cleaned: '{cleaned_name}') with WRatio to alias '{self.all_aliases.get(best_match_bank_key)}' -> '{standard_name}' score {highest_score} (conf: {final_confidence})")
            return {
                'standardized_name': standard_name, 
                'confidence': final_confidence,
                'method': 'fuzzy_match'
            }
                
        if self.debug_mode: print(f"BankStandardizer: No match found for '{raw_name}' (cleaned: '{cleaned_name}')")
        return {
            'standardized_name': original_raw_name, 
            'confidence': 0.0, 
            'method': 'no_match'
        }
    
    def reload(self) -> None:
        """
        Reload the bank data from the JSON file.
        Useful when the JSON file has been updated.
        """
        self.bank_data = self._load_bank_data(self.bank_names_file)
        self.all_aliases = self._prepare_aliases()
    
    def add_bank(self, key: str, standard_name: str, aliases: List[str], 
                 country: Optional[str] = None, save: bool = True) -> bool:
        """
        Add a new bank to the standardizer.
        
        Args:
            key: The lowercase key for the bank
            standard_name: The standardized name to use for the bank
            aliases: List of aliases for the bank
            country: Optional country of the bank
            save: Whether to save changes to the JSON file
            
        Returns:
            True if successful, False otherwise
        """
        if not key or not standard_name:
            return False
        
        # Add to bank data
        bank_entry = {
            "standard_name": standard_name,
            "aliases": aliases
        }
        
        if country:
            bank_entry["country"] = country
            
        self.bank_data[key.lower()] = bank_entry
        
        # Update aliases
        for alias in aliases:
            self.all_aliases[alias.lower()] = key.lower()
        
        # Save to file if requested
        if save:
            return self._save_bank_data()
            
        return True
    
    def _save_bank_data(self) -> bool:
        """
        Save the current bank data to the JSON file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.bank_names_file, 'w', encoding='utf-8') as f:
                json.dump(self.bank_data, f, indent=2, sort_keys=True)
            return True
        except Exception as e:
            print(f"Error saving bank data: {str(e)}")
            return False
    
    @staticmethod
    def extract_bank_names_from_results(results_file: str) -> List[str]:
        """
        Extract unique bank names from previous extraction results.
        
        Args:
            results_file: Path to a JSON file containing extraction results
            
        Returns:
            List of unique bank names found
        """
        unique_banks = set()
        
        try:
            with open(results_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
                
            for result in results:
                for bank in result.get('extracted_banks', []):
                    if isinstance(bank, dict) and 'raw_name' in bank and bank['raw_name']:
                        unique_banks.add(bank['raw_name'])
                    elif isinstance(bank, str):
                        unique_banks.add(bank)
                        
            return sorted(list(unique_banks))
            
        except Exception as e:
            print(f"Error extracting bank names: {str(e)}")
            return []
    
    def build_bank_dictionary(self, raw_bank_names: List[str], min_fuzzy_threshold: int = 85,
                             common_banks: Optional[Dict[str, List[str]]] = None) -> Dict:
        """
        Build a dictionary of bank names from raw extracted names.
        This is a utility to help populate the bank_names.json file.
        
        Args:
            raw_bank_names: List of raw bank names extracted from documents
            min_fuzzy_threshold: Minimum threshold for fuzzy grouping
            common_banks: Optional dictionary of known bank names to start with
            
        Returns:
            Dictionary in the format needed for bank_names.json
        """
        result = common_banks or {}
        processed = set()
        
        # First pass: clean all names
        cleaned_names = []
        for name in raw_bank_names:
            cleaned = self._clean_name(name)
            if cleaned and len(cleaned) >= 3:
                cleaned_names.append((cleaned, name))
        
        # Second pass: group similar names
        for cleaned, original in cleaned_names:
            if cleaned in processed:
                continue
                
            # Create a group for this name
            group = [original]
            key = cleaned
            
            # Find similar names
            for other_cleaned, other_original in cleaned_names:
                if other_cleaned == cleaned or other_cleaned in processed:
                    continue
                    
                score = fuzz.token_set_ratio(cleaned, other_cleaned)
                if score >= min_fuzzy_threshold:
                    group.append(other_original)
                    processed.add(other_cleaned)
            
            # Add the group to the result
            if key not in result:
                # Determine the standard name (use the shortest non-abbreviated one)
                candidates = [name for name in group if len(name) > 4]
                if candidates:
                    standard_name = min(candidates, key=len)
                else:
                    standard_name = min(group, key=len)
                
                result[key] = {
                    "standard_name": standard_name,
                    "aliases": sorted(list(set(group)))
                }
            
            processed.add(cleaned)
            
        return result 