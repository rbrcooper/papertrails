import re
from datetime import datetime
from typing import Dict, Optional, List, Tuple, Any
import dateutil.parser
from dateutil.parser import ParserError # Added for explicit exception handling
# from ..utils.pattern_registry import PatternRegistry # Commented out for now, patterns redefined
from .base_extractor import BaseExtractor

class DateExtractor(BaseExtractor):
    """Extracts issue date and maturity date information using confidence-based patterns."""
    
    def __init__(self, debug_mode=False):
        """Initialize the date extractor with confidence-based patterns."""
        self.debug_mode = debug_mode
        # Test variable for new structure
        self.new_structure_initialized = True 
        
        # Define patterns with confidence levels
        # These are illustrative patterns based on the prompt; they will need refinement
        self.patterns = {
            'high_confidence': [
                # Explicit date labels - using named groups 'label' and 'date_str'
                r'(?P<label>(?:Issue|Settlement|Dated)\s*(?:Date)?|Effective\s*Date|Date\s*of\s*Issue|First\s*Settlement\s*Date)\s*:\s*(?P<date_str>\d{1,2}[\s./-]\w+[\s./-]\d{2,4}|\w+\s*\d{1,2}(?:st|nd|rd|th)?,?\s*\d{2,4})',
                r'(?P<label>Maturity\s*(?:Date)?|Due\s*Date|Redemption\s*Date|Final\s*Maturity\s*Date)\s*:\s*(?P<date_str>\d{1,2}[\s./-]\w+[\s./-]\d{2,4}|\w+\s*\d{1,2}(?:st|nd|rd|th)?,?\s*\d{2,4})'
            ],
            'medium_confidence': [
                # Date formats without explicit labels, but near keywords
                # These require more sophisticated context checking in _resolve_conflicts
                r'(?i)(?:issue|settlement|dated)\s*(?:date)?\s*(?:on\s*or\s*about\s*)?(?P<date_str>\d{1,2}[\s./-]\w+[\s./-]\d{2,4}|\w+\s*\d{1,2}(?:st|nd|rd|th)?,?\s*\d{2,4})',
                r'(?i)(?:maturity|due|redemption)\s*(?:date)?\s*(?:on\s*or\s*about\s*)?(?P<date_str>\d{1,2}[\s./-]\w+[\s./-]\d{2,4}|\w+\s*\d{1,2}(?:st|nd|rd|th)?,?\s*\d{2,4})',
                # General date patterns
                r'\b(?P<date_str>\d{1,2}[\s./-]\w+[\s./-]\d{2,4})\b', # e.g., 20 July 2023, 20/07/2023
                r'\b(?P<date_str>\w+\s*\d{1,2}(?:st|nd|rd|th)?,?\s*\d{2,4})\b' # e.g., July 20, 2023
            ],
            'low_confidence': [
                # More ambiguous patterns, rely heavily on context or relative position
                # Example: A date found in a table header or footer
                # For now, this can be a placeholder for fuzzy logic if other methods fail
            ]
        }
        self.date_parser_settings = {
            'fuzzy': False, # Exact matches preferred for high/medium confidence patterns
            # 'PREFER_DAY_OF_MONTH': True, # This is a dateparser library setting, not dateutil
            # 'STRICT_PARSING': False # This is a dateparser library setting
        }
        # For dateutil.parser, dayfirst=True can be useful for European dates,
        # but it's better to have robust regex or try both.
        # Let _parse_date_string handle ambiguitiy.

    def extract(self, text: str) -> Dict[str, Optional[str]]:
        """
        Main extraction method. Replaces the old extract method.
        Uses extract_with_confidence and processes its results.
        Args:
            text: The text to extract dates from
        Returns:
            Dictionary with 'issue_date', 'maturity_date', and 'confidence_levels'
        """
        if not text:
            return {'issue_date': None, 'maturity_date': None, 'confidence_levels': {}}

        normalized_text = self._normalize_text(text)
        
        if self.debug_mode:
            print(f"DateExtractor: Processing {len(normalized_text)} characters of normalized text")

        extracted_candidates = self.extract_with_confidence(normalized_text)
        resolved_dates = self._resolve_conflicts(extracted_candidates, normalized_text)

        # Ensure 'confidence_levels' key exists
        if 'confidence_levels' not in resolved_dates:
            resolved_dates['confidence_levels'] = {}
            
        if self.debug_mode:
            print(f"DateExtractor: Final resolved dates - {resolved_dates}")
            
        return resolved_dates

    def extract_with_confidence(self, text: str) -> List[Dict[str, Any]]:
        """
        Extracts all potential date candidates with their confidence levels.
        Args:
            text: The normalized text to extract dates from.
        Returns:
            A list of dictionaries, each containing 'date_str', 'parsed_date', 'confidence', 
            'label' (optional), 'pattern_type', and 'context'.
        """
        results = []
        for confidence, patterns in self.patterns.items():
            if not patterns: # Skip empty confidence levels (e.g. low_confidence if not defined)
                continue
            for i, pattern_regex in enumerate(patterns):
                if self.debug_mode:
                    print(f"DateExtractor: Trying pattern with confidence '{confidence}': {pattern_regex}")
                
                try:
                    compiled_pattern = re.compile(pattern_regex, re.IGNORECASE)
                except re.error as e:
                    if self.debug_mode:
                        print(f"DateExtractor: Regex compilation error for pattern '{pattern_regex}': {e}")
                    continue

                for match in compiled_pattern.finditer(text):
                    try:
                        date_str = match.group('date_str').strip()
                        label = match.groupdict().get('label', '').strip()
                        
                        parsed_date = self._parse_date_string(date_str)
                        
                        if parsed_date:
                            context = self._get_context(text, match)
                            candidate = {
                                'date_str': date_str,
                                'parsed_date': parsed_date,
                                'confidence': confidence,
                                'label': label.lower() if label else None,
                                'pattern_type': 'explicit_label' if label else 'general_date',
                                'context': context,
                                'match_start': match.start(),
                                'match_end': match.end()
                            }
                            results.append(candidate)
                            if self.debug_mode:
                                print(f"DateExtractor: Found candidate: {candidate['parsed_date'].strftime('%Y-%m-%d')} with label '{candidate['label']}' via '{confidence}' pattern.")
                        elif self.debug_mode:
                            print(f"DateExtractor: Failed to parse date_str: '{date_str}' from pattern '{pattern_regex}'")
                            
                    except IndexError: # Mismatch in regex group names or number
                         if self.debug_mode:
                            print(f"DateExtractor: Regex group error with pattern '{pattern_regex}' and match '{match.group(0)}'")
                    except Exception as e: # Catch any other unexpected error during match processing
                        if self.debug_mode:
                            print(f"DateExtractor: Unexpected error processing match for pattern '{pattern_regex}': {e}")

        # Sort results by match position to help in resolving conflicts
        results.sort(key=lambda x: x['match_start'])
        return results

    def _get_context(self, text: str, match: re.Match, window: int = 50) -> str:
        """
        Get context around a regex match.
        Args:
            text: The original text.
            match: The regex match object.
            window: Number of characters to include on each side of the match.
        Returns:
            A string containing the context.
        """
        start = max(0, match.start() - window)
        end = min(len(text), match.end() + window)
        return text[start:end].replace("\n", " ") # Replace newlines for cleaner context

    def _resolve_conflicts(self, candidates: List[Dict[str, Any]], original_text: str) -> Dict[str, Optional[Any]]:
        """
        Resolves conflicts among extracted date candidates to determine
        the most likely issue_date and maturity_date.
        Args:
            candidates: A list of date candidates from extract_with_confidence.
            original_text: The original (normalized) text, for further analysis if needed.
        Returns:
            A dictionary with 'issue_date', 'maturity_date', and 'confidence_levels'.
        """
        issue_date: Optional[datetime] = None
        maturity_date: Optional[datetime] = None
        issue_date_confidence: Optional[str] = None
        maturity_date_confidence: Optional[str] = None
        
        # Sort candidates by confidence: high > medium > low, then by match position
        confidence_order = {'high_confidence': 0, 'medium_confidence': 1, 'low_confidence': 2}
        candidates.sort(key=lambda c: (confidence_order.get(c['confidence'], 99), c['match_start']))

        potential_issue_dates = []
        potential_maturity_dates = []

        for cand in candidates:
            date_val = cand['parsed_date']
            label = cand['label']
            confidence = cand['confidence']

            # Direct assignment from high-confidence labels
            if 'issue' in (label or '') or 'settlement' in (label or '') or 'dated' in (label or ''):
                potential_issue_dates.append({'date': date_val, 'confidence': confidence, 'candidate_info': cand})
            elif 'maturity' in (label or '') or 'due' in (label or '') or 'redemption' in (label or ''):
                potential_maturity_dates.append({'date': date_val, 'confidence': confidence, 'candidate_info': cand})
            else:
                # For medium/low confidence without specific labels, or general patterns
                # We might need more sophisticated logic here, e.g. proximity to keywords
                # For now, add to both if no label, or decide based on context later
                # This part can use older heuristics if needed
                pass # Or add to a general pool

        # Prioritize higher confidence matches for issue date
        if potential_issue_dates:
            potential_issue_dates.sort(key=lambda x: confidence_order.get(x['confidence'], 99))
            best_issue = potential_issue_dates[0]
            issue_date = best_issue['date']
            issue_date_confidence = best_issue['confidence']
            if self.debug_mode:
                 print(f"DateExtractor: Selected issue date {issue_date.strftime('%Y-%m-%d')} with confidence {issue_date_confidence} from candidate: {best_issue['candidate_info']}")


        # Prioritize higher confidence matches for maturity date
        if potential_maturity_dates:
            potential_maturity_dates.sort(key=lambda x: confidence_order.get(x['confidence'], 99))
            best_maturity = potential_maturity_dates[0]
            maturity_date = best_maturity['date']
            maturity_date_confidence = best_maturity['confidence']
            if self.debug_mode:
                 print(f"DateExtractor: Selected maturity date {maturity_date.strftime('%Y-%m-%d')} with confidence {maturity_date_confidence} from candidate: {best_maturity['candidate_info']}")

        # Basic validation: maturity date should be after issue date
        if issue_date and maturity_date and maturity_date < issue_date:
            if self.debug_mode:
                print(f"DateExtractor: Conflict - Maturity date {maturity_date.strftime('%Y-%m-%d')} is before issue date {issue_date.strftime('%Y-%m-%d')}. Invalidating.")
            # This is a conflict. More complex resolution might be needed.
            # For now, we might discard one or both, or flag for review.
            # If confidences are different, prefer the one with higher confidence.
            # This simplified logic just nils them for now if they conflict directly and were both found.
            # A more advanced strategy would re-evaluate other candidates.
            
            # Simple approach: if one is high confidence and the other isn't, keep high confidence one.
            issue_conf_val = confidence_order.get(issue_date_confidence, 99)
            mat_conf_val = confidence_order.get(maturity_date_confidence, 99)

            if issue_conf_val < mat_conf_val: # Issue date has higher confidence
                maturity_date = None
                maturity_date_confidence = None
                if self.debug_mode: print("DateExtractor: Invalidated maturity date due to conflict and lower confidence.")
            elif mat_conf_val < issue_conf_val: # Maturity date has higher confidence
                issue_date = None
                issue_date_confidence = None
                if self.debug_mode: print("DateExtractor: Invalidated issue date due to conflict and lower confidence.")
            else: # Same confidence or uncomparable, invalidate both for now
                # This could be a place to try and find other candidates
                # For example, if multiple maturity dates were found, try the next best one.
                # Or if the conflicting dates were very close to each other in the text.
                issue_date = None 
                maturity_date = None
                issue_date_confidence = None
                maturity_date_confidence = None
                if self.debug_mode: print("DateExtractor: Invalidated both dates due to conflict and similar confidence.")

        # Fallback: if key dates are missing, try fuzzy extraction (adapted from old logic)
        if not issue_date or not maturity_date:
            if self.debug_mode:
                print("DateExtractor: One or more key dates missing, attempting fuzzy extraction.")
            fuzzy_results = self._extract_dates_fuzzy(original_text) # Expects normalized text
            if not issue_date and fuzzy_results.get('issue_date'):
                parsed_fuzzy_issue = self._parse_date_string(fuzzy_results['issue_date'])
                if parsed_fuzzy_issue:
                    # Check against existing maturity_date if any
                    if maturity_date and parsed_fuzzy_issue > maturity_date:
                         if self.debug_mode: print(f"DateExtractor: Fuzzy issue date {parsed_fuzzy_issue.strftime('%Y-%m-%d')} is after maturity date {maturity_date.strftime('%Y-%m-%d')}, discarding.")
                    else:
                        issue_date = parsed_fuzzy_issue
                        issue_date_confidence = 'low_fuzzy'
                        if self.debug_mode: print(f"DateExtractor: Set issue date from fuzzy: {issue_date.strftime('%Y-%m-%d')}")
            
            if not maturity_date and fuzzy_results.get('maturity_date'):
                parsed_fuzzy_maturity = self._parse_date_string(fuzzy_results['maturity_date'])
                if parsed_fuzzy_maturity:
                     # Check against existing issue_date if any
                    if issue_date and parsed_fuzzy_maturity < issue_date:
                        if self.debug_mode: print(f"DateExtractor: Fuzzy maturity date {parsed_fuzzy_maturity.strftime('%Y-%m-%d')} is before issue date {issue_date.strftime('%Y-%m-%d')}, discarding.")
                    else:
                        maturity_date = parsed_fuzzy_maturity
                        maturity_date_confidence = 'low_fuzzy'
                        if self.debug_mode: print(f"DateExtractor: Set maturity date from fuzzy: {maturity_date.strftime('%Y-%m-%d')}")

        return {
            'issue_date': issue_date.strftime('%Y-%m-%d') if issue_date else None,
            'maturity_date': maturity_date.strftime('%Y-%m-%d') if maturity_date else None,
            'confidence_levels': {
                'issue_date': issue_date_confidence,
                'maturity_date': maturity_date_confidence
            }
        }

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for date extraction.
        Args:
            text: The text to normalize
        Returns:
            Normalized text
        """
        # Replace various separator characters with a standard one (e.g. space or hyphen)
        # Using space to avoid issues with dateutil.parser expecting separators sometimes
        normalized = text.lower() # Convert to lowercase for easier regex
        normalized = re.sub(r'[\/\.\-]', '-', normalized) # Standardize separators to hyphen
        
        # Remove ordinal indicators (1st, 2nd, 3rd, 4th)
        normalized = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', normalized)
        
        # Standardize month abbreviations to full names (lowercase)
        # This helps dateutil.parser and custom regex
        month_abbrevs = {
            'jan': 'january', 'feb': 'february', 'mar': 'march', 'apr': 'april',
            # 'may' is already full
            'jun': 'june', 'jul': 'july', 'aug': 'august',
            'sep': 'september', 'sept': 'september', 'oct': 'october', 
            'nov': 'november', 'dec': 'december'
        }
        for abbrev, full in month_abbrevs.items():
            normalized = re.sub(rf'\b{abbrev}\b', full, normalized, flags=re.IGNORECASE)
        
        # Replace "on or about" with a simpler marker or remove if it confuses parser
        normalized = re.sub(r'on\s+or\s+about', 'about', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'approx(?:imately)?', 'about', normalized, flags=re.IGNORECASE)

        # Add spaces around hyphens if they connect words/numbers, to help parsing
        # e.g. "word-1" -> "word - 1", but "20-July" should remain "20-July"
        # This is tricky; for now, we assume dateutil handles it or regex are specific.
        # normalized = re.sub(r'(\w)-(\w)', r'\1 - \2', normalized)

        if self.debug_mode:
            # print(f"DateExtractor: Normalized text sample: {normalized[:200]}") # careful with large text
            pass

        return normalized
    
    def _split_into_sections(self, text: str) -> List[Tuple[str, str]]:
        """
        Split the text into sections based on headings. (Potentially useful for context)
        Args:
            text: The text to split
        Returns:
            List of (section_title, section_text) tuples
        """
        # This is a simplified version. Real section splitting can be complex.
        # The original patterns were too broad and might not work well with re.DOTALL
        # For now, this is not directly used by the core extract_with_confidence logic
        # but could be used by _resolve_conflicts or other heuristics.
        sections = []
        # A very basic pattern looking for lines that look like titles (e.g., all caps, or start with number)
        # This needs significant improvement for real-world documents.
        # Example: Try to find lines that are mostly uppercase or start with "1. ", "A. " etc.
        # For the purpose of this refactor, this method is kept but not central.
        # Consider using layout information if available from PDF extraction.

        # Fallback: return the whole text as one section if no specific splitting logic is effective
        if not sections:
            sections = [('Document', text)] # Use normalized text
            
        return sections

    def _extract_dates_fuzzy(self, text: str) -> Dict[str, str]:
        """
        Use a fuzzy approach to extract dates when specific patterns fail.
        This is a fallback mechanism.
        Args:
            text: The NORMALIZED text to extract dates from
        Returns:
            Dictionary with potential 'issue_date' and 'maturity_date' (as strings).
        """
        result = {}
        if self.debug_mode:
            print(f"DateExtractor: Starting fuzzy date extraction.")

        # Simpler fuzzy extraction: find all dates, then try to assign them.
        # This uses dateutil.parser.parse with fuzzy=True on segments of text.
        # We rely on _parse_date_string which itself uses dateutil.parser.
        
        # Heuristic: Look for "issue date" and "maturity date" keywords and parse nearby text.
        # Keywords should be in lowercase as text is normalized.
        issue_keywords = ['issue date', 'settlement date', 'dated date', 'issuance date']
        maturity_keywords = ['maturity date', 'redemption date', 'due date', 'final maturity']

        found_dates_with_context = [] # Store (datetime_obj, keyword_proximity_score, original_str)

        # A simple way to get date strings: find any plausible date string in text
        # This pattern is very general.
        generic_date_like_pattern = r'(?:(?:\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})|(?:(?:january|february|march|april|may|june|july|august|september|october|november|december)[\s-]+\d{1,2}[,\s-]+\d{2,4})|(?:\d{1,2}[\s-]+(?:january|february|march|april|may|june|july|august|september|october|november|december)[\s-]+\d{2,4}))'
        
        for match in re.finditer(generic_date_like_pattern, text, re.IGNORECASE):
            date_str = match.group(0)
            parsed_dt = self._parse_date_string(date_str, fuzzy_parse=True) # Use fuzzy for this
            if parsed_dt:
                # Check proximity to keywords
                context_window = text[max(0, match.start() - 100):min(len(text), match.end() + 100)]
                is_issue = any(kw in context_window for kw in issue_keywords)
                is_maturity = any(kw in context_window for kw in maturity_keywords)
                
                if is_issue and not is_maturity:
                    found_dates_with_context.append({'type': 'issue', 'date': parsed_dt, 'original_str': date_str, 'pos':match.start()})
                elif is_maturity and not is_issue:
                    found_dates_with_context.append({'type': 'maturity', 'date': parsed_dt, 'original_str': date_str, 'pos':match.start()})
                # If both or neither, it's ambiguous for this simple fuzzy logic.

        if self.debug_mode and found_dates_with_context:
            print(f"DateExtractor (fuzzy): Found {len(found_dates_with_context)} potential dates with context.")

        potential_issue_dates = sorted([fd['date'] for fd in found_dates_with_context if fd['type'] == 'issue'], key=lambda d: d)
        potential_maturity_dates = sorted([fd['date'] for fd in found_dates_with_context if fd['type'] == 'maturity'], key=lambda d: d, reverse=True) # often last one

        if potential_issue_dates:
            result['issue_date'] = potential_issue_dates[0].strftime('%Y-%m-%d') # typically the earliest
            if self.debug_mode: print(f"DateExtractor (fuzzy): Tentative issue date: {result['issue_date']}")
        
        if potential_maturity_dates:
            result['maturity_date'] = potential_maturity_dates[0].strftime('%Y-%m-%d') # typically the latest reasonable
            if self.debug_mode: print(f"DateExtractor (fuzzy): Tentative maturity date: {result['maturity_date']}")

        # Simple validation
        if result.get('issue_date') and result.get('maturity_date'):
            iss_dt = datetime.strptime(result['issue_date'], '%Y-%m-%d')
            mat_dt = datetime.strptime(result['maturity_date'], '%Y-%m-%d')
            if mat_dt < iss_dt:
                if self.debug_mode: print(f"DateExtractor (fuzzy): Maturity {result['maturity_date']} before issue {result['issue_date']}. Invalidating fuzzy maturity.")
                del result['maturity_date'] # Or issue, depending on other heuristics not implemented here

        return result

    def _extract_dates_from_text(self, text: str) -> List[datetime]:
        """
        Extract all dates from text without context. (Kept for potential use, but less central now)
        Args:
            text: The text to extract dates from (expects normalized text)
        Returns:
            List of datetime objects
        """
        dates = []
        # The patterns here should be robust.
        # This method is less used now that extract_with_confidence is primary.
        # It can be a utility if needed.
        
        # Example: find all date-like strings and parse them
        # This is largely superseded by the main extraction logic and _parse_date_string
        generic_date_patterns_for_bulk = [
            # DD-MM-YYYY or MM-DD-YYYY like patterns
            r'\b(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})\b',
            # YYYY-MM-DD like patterns
            r'\b(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})\b',
            # Month Day, Year (e.g., January 1, 2020 or Jan 1, 2020)
            r'\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[.]?\s+\d{1,2}(?:st|nd|rd|th)?[,.]?\s+\d{2,4})\b',
            # Day Month Year (e.g., 1 January 2020 or 1 Jan 2020)
            r'\b(\d{1,2}(?:st|nd|rd|th)?[\s-]+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[.]?[\s-]+\d{2,4})\b'
        ]

        for pattern_str in generic_date_patterns_for_bulk:
            try:
                compiled_pattern = re.compile(pattern_str, re.IGNORECASE)
                for match in compiled_pattern.finditer(text):
                    date_str = match.group(1)
                    parsed_date = self._parse_date_string(date_str, fuzzy_parse=True) # Try fuzzy for these general ones
                    if parsed_date:
                        # Basic sanity check for year range
                        if 1980 <= parsed_date.year <= 2100:
                             if parsed_date not in dates: # Avoid duplicates
                                dates.append(parsed_date)
            except re.error as e:
                if self.debug_mode:
                    print(f"DateExtractor (_extract_dates_from_text): Regex error {e} for pattern {pattern_str}")
        
        dates.sort() # Sort chronologically
        if self.debug_mode:
            print(f"DateExtractor (_extract_dates_from_text): Extracted {len(dates)} dates: {[d.strftime('%Y-%m-%d') for d in dates]}")
        return dates
    
    def _parse_date_string(self, date_str: str, fuzzy_parse: bool = False) -> Optional[datetime]:
        """
        Parse a date string into a datetime object.
        Uses dateutil.parser.parse with specific settings.
        Prioritizes common European and US formats.
        Args:
            date_str: The date string to parse.
            fuzzy_parse: Whether to allow fuzzy parsing by dateutil.
        Returns:
            Parsed datetime object or None if parsing failed.
        """
        if not date_str:
            return None
            
        # Clean common OCR errors or non-standard parts if possible
        # e.g., "20th July, 2023" -> "20 July, 2023" (already handled by normalize)
        
        try:
            # Try parsing with dayfirst=True (common in Europe)
            # The fuzzy setting from self.date_parser_settings is used by default
            # but can be overridden by the fuzzy_parse argument.
            parser_kwargs = self.date_parser_settings.copy()
            if fuzzy_parse: # Override if explicitly requested
                parser_kwargs['fuzzy'] = True

            parsed_dt = dateutil.parser.parse(date_str, dayfirst=True, **parser_kwargs)
            if 1980 <= parsed_dt.year <= 2100: # Sanity check year
                 return parsed_dt
        except (ParserError, ValueError, OverflowError): # Catch specific parser errors
            pass # Try next format

        try:
            # Try parsing with dayfirst=False (common in US)
            parser_kwargs = self.date_parser_settings.copy()
            if fuzzy_parse:
                parser_kwargs['fuzzy'] = True
            parsed_dt = dateutil.parser.parse(date_str, dayfirst=False, **parser_kwargs)
            if 1980 <= parsed_dt.year <= 2100:
                return parsed_dt
        except (ParserError, ValueError, OverflowError):
            pass

        # If strict parsing failed, and fuzzy is allowed by caller, try a generic fuzzy parse
        if fuzzy_parse and 'fuzzy' not in self.date_parser_settings : # Ensure we are not re-trying same if already fuzzy by default
            try:
                # A more general fuzzy parse if specific ones fail
                parsed_dt = dateutil.parser.parse(date_str, fuzzy=True)
                if 1980 <= parsed_dt.year <= 2100:
                    return parsed_dt
            except (ParserError, ValueError, OverflowError):
                pass # Truly unparseable

        if self.debug_mode:
            print(f"DateExtractor: Failed to parse date string: '{date_str}' with available methods.")
        return None
    
    def _month_to_number(self, month_name: str) -> int:
        """
        Convert month name to month number. (Kept for direct use if needed by regex)
        Args:
            month_name: The name of the month (expected to be full and lowercase from _normalize_text)
        Returns:
            Month number (1-12), or 0 if not found.
        """
        month_map = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }
        return month_map.get(month_name.lower(), 0) # Return 0 for error, easier to check