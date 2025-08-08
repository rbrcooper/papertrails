import re
from typing import Dict, Any, Optional, Tuple, List
from ..utils.pattern_registry import PatternRegistry
from .base_extractor import BaseExtractor

class CouponExtractor(BaseExtractor):
    """Extracts coupon rate and type information."""
    
    def __init__(self, debug_mode=False):
        """Initialize the coupon extractor."""
        self.patterns = PatternRegistry.get_coupon_patterns()
        self.debug_mode = debug_mode
        
    def extract(self, text: str) -> Dict[str, Any]:
        """
        Extract coupon information from text.
        
        Args:
            text: The text to extract coupon information from
            
        Returns:
            Dictionary with coupon_rate, coupon_type and reference_rate keys
        """
        coupon_info = {
            'coupon_rate': None,
            'coupon_type': None,
            'reference_rate': None,
            'step_details': None,
            'details': None,
            'confidence': 'medium'  # Default confidence
        }
        
        if not text:
            return coupon_info
            
        if self.debug_mode:
            print(f"CouponExtractor: Processing {len(text)} characters of text")
            
        # Normalize text for easier processing
        normalized_text = self._normalize_text(text)
        
        if self.debug_mode:
            print(f"CouponExtractor: Processing {len(normalized_text)} characters of normalized text")
            
        # Extract coupon rate and type
        results = self._extract_coupon(normalized_text)
        
        if results['coupon_rate']:
            coupon_info['coupon_rate'] = results['coupon_rate']
            if self.debug_mode:
                print(f"CouponExtractor: Found coupon rate: {results['coupon_rate']}")
            
        if results['coupon_type']:
            coupon_info['coupon_type'] = results['coupon_type']
            if self.debug_mode:
                print(f"CouponExtractor: Found coupon type: {results['coupon_type']}")
            
        if results['reference_rate']:
            coupon_info['reference_rate'] = results['reference_rate']
            if self.debug_mode:
                print(f"CouponExtractor: Found reference rate: {results['reference_rate']}")
            
        if results['step_details']:
            coupon_info['step_details'] = results['step_details']
            if self.debug_mode:
                print(f"CouponExtractor: Found step details: {results['step_details']}")
            
        if results['details']:
            coupon_info['details'] = results['details']
            if self.debug_mode:
                print(f"CouponExtractor: Found additional details: {results['details']}")
            
        # Determine confidence level
        if coupon_info['coupon_rate'] and coupon_info['coupon_type']:
            coupon_info['confidence'] = 'high'
        elif coupon_info['coupon_rate'] or coupon_info['coupon_type']:
            coupon_info['confidence'] = 'medium'
        else:
            coupon_info['confidence'] = 'low'
            
        if self.debug_mode:
            print(f"CouponExtractor: Final results - coupon_rate: {coupon_info['coupon_rate']}, coupon_type: {coupon_info['coupon_type']}, confidence: {coupon_info['confidence']}")
            
        return coupon_info
        
    def _extract_coupon(self, text: str) -> Dict[str, Any]:
        """
        Extract coupon rate and type from text.
        
        Args:
            text: The text to extract from
            
        Returns:
            Dictionary with extracted coupon information
        """
        results = {
            'coupon_rate': None,
            'coupon_type': None,
            'reference_rate': None,
            'step_details': None,
            'details': None
        }
        
        if not text:
            return results
            
        # Check for zero coupon first as it's a special case
        if re.search(r'zero\s+coupon|discount|no\s+(?:periodic\s+)?(?:interest|coupon)', text, re.IGNORECASE):
            results['coupon_rate'] = '0'
            results['coupon_type'] = 'zero coupon'
            if self.debug_mode:
                print("CouponExtractor: Detected zero coupon bond")
            return results
            
        # Check for floating rate / reference rate patterns
        reference_rate_match = self._extract_reference_rate(text)
        if reference_rate_match:
            results['coupon_type'] = 'floating rate'
            results['reference_rate'] = reference_rate_match['reference_rate']
            if reference_rate_match['spread']:
                results['coupon_rate'] = reference_rate_match['spread']
            results['details'] = reference_rate_match['details']
            if self.debug_mode:
                print(f"CouponExtractor: Detected floating rate with reference rate: {reference_rate_match['reference_rate']}, spread: {reference_rate_match['spread']}")
            return results
            
        # Check for step-up/step-down coupon
        step_match = self._extract_step_coupon(text)
        if step_match:
            results['coupon_type'] = step_match['type']  # 'step-up' or 'step-down'
            results['coupon_rate'] = step_match['initial_rate']
            results['step_details'] = step_match['steps']
            if self.debug_mode:
                print(f"CouponExtractor: Detected {step_match['type']} coupon with initial rate: {step_match['initial_rate']}")
            return results
            
        # Try to find a fixed rate coupon
        fixed_rate_match = self._extract_fixed_rate(text)
        if fixed_rate_match:
            results['coupon_rate'] = fixed_rate_match['rate']
            results['coupon_type'] = 'fixed rate'
            if self.debug_mode:
                print(f"CouponExtractor: Detected fixed rate coupon with rate: {fixed_rate_match['rate']}")
            return results
            
        # If we still don't have a rate or type, look for any rate mention
        # This is a fallback method
        for i, pattern in enumerate(self.patterns['coupon_rate']):
            if self.debug_mode:
                print(f"CouponExtractor: Trying coupon rate pattern {i+1}")
                
            matches = re.finditer(pattern, text, re.IGNORECASE)
            match_count = 0
            
            for match in matches:
                match_count += 1
                rate_str = match.group(1)
                
                if self.debug_mode:
                    context = text[max(0, match.start() - 30):min(len(text), match.end() + 30)]
                    print(f"CouponExtractor: Found rate match using pattern {i+1}: '{rate_str}' in '...{context}...'")
                
                try:
                    # Validate that we have a proper rate
                    rate = float(rate_str)
                    if 0 <= rate <= 20:  # Reasonable rate range
                        results['coupon_rate'] = rate_str
                        if self.debug_mode:
                            print(f"CouponExtractor: Valid coupon rate found: {rate_str}%")
                        break
                    else:
                        if self.debug_mode:
                            print(f"CouponExtractor: Rate out of reasonable range: {rate}%")
                except ValueError:
                    if self.debug_mode:
                        print(f"CouponExtractor: Could not convert rate to float: {rate_str}")
                    continue
            
            if self.debug_mode and match_count == 0:
                print(f"CouponExtractor: No matches for coupon rate pattern {i+1}")
                
            if results['coupon_rate']:
                break
                
        # If we still don't have a type but found a rate, check for type mentions
        if results['coupon_rate'] and not results['coupon_type']:
            if self.debug_mode:
                print("CouponExtractor: Found rate but no type, searching for coupon type")
                
            # Find coupon type
            for i, pattern in enumerate(self.patterns['coupon_types']):
                if self.debug_mode:
                    print(f"CouponExtractor: Trying coupon type pattern {i+1}")
                    
                matches = re.finditer(pattern, text, re.IGNORECASE)
                match_count = 0
                
                for match in matches:
                    match_count += 1
                    type_str = match.group(0).strip().lower()
                    
                    if self.debug_mode:
                        context = text[max(0, match.start() - 30):min(len(text), match.end() + 30)]
                        print(f"CouponExtractor: Found type match: '{type_str}' in '...{context}...'")
                    
                    # Standardize type format
                    type_str = re.sub(r'\s+', ' ', type_str)
                    results['coupon_type'] = type_str
                    break
                
                if self.debug_mode and match_count == 0:
                    print(f"CouponExtractor: No matches for coupon type pattern {i+1}")
                    
                if results['coupon_type']:
                    break
            
            # If we found a rate but no type, assume it's fixed rate
            if not results['coupon_type']:
                results['coupon_type'] = "fixed rate"
                if self.debug_mode:
                    print("CouponExtractor: No type found, assuming fixed rate")
                
        return results
    
    def _extract_fixed_rate(self, text: str) -> Optional[Dict[str, str]]:
        """
        Extract a fixed interest rate from text.
        
        Args:
            text: The text to extract from
            
        Returns:
            Dictionary with rate if found, None otherwise
        """
        fixed_patterns = [
            r'(?:fixed|coupon)\s+(?:interest\s+)?rate\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
            r'(?:interest\s+(?:is|shall\s+be)\s+payable\s+at|bears\s+interest\s+at|pays\s+a\s+coupon\s+of)\s+(?:a\s+(?:fixed\s+)?rate\s+of\s+)?(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
            r'(?:interest\s+rate|rate\s+of\s+interest)\s*[:\-]?\s*(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
            r'(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)(?:\s+(?:fixed\s+)?(?:rate\s+)?(?:interest|coupon))',
            r'(?:bear\s+interest\s+at|pays|with|carries|offering|bearing)(?:\s+a)?\s*(?:fixed\s+)?(?:rate\s+)?(?:coupon\s+)?(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
            r'fixed\s+(?:rate\s+)?notes?\s+(?:due\s+\d{4}\s+)?(?:with|paying|at|of|bearing)\s+(?:a\s+(?:coupon|interest)\s+(?:rate\s+)?(?:of\s+)?)?(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)'
        ]
        
        for i, pattern in enumerate(fixed_patterns):
            if self.debug_mode:
                print(f"CouponExtractor: Trying fixed rate pattern {i+1}")
                
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                rate = match.group(1)
                
                if self.debug_mode:
                    context = text[max(0, match.start() - 30):min(len(text), match.end() + 30)]
                    print(f"CouponExtractor: Found fixed rate match using pattern {i+1}: '{rate}' in '...{context}...'")
                
                try:
                    # Validate the rate is reasonable
                    float_rate = float(rate)
                    if 0 <= float_rate <= 20:
                        if self.debug_mode:
                            print(f"CouponExtractor: Valid fixed rate found: {rate}%")
                        return {'rate': rate}
                    else:
                        if self.debug_mode:
                            print(f"CouponExtractor: Fixed rate out of reasonable range: {float_rate}%")
                except ValueError:
                    if self.debug_mode:
                        print(f"CouponExtractor: Could not convert fixed rate to float: {rate}")
                    continue
            elif self.debug_mode:
                print(f"CouponExtractor: No matches for fixed rate pattern {i+1}")
                    
        return None
        
    def _extract_reference_rate(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract reference rate information for floating rate bonds.
        
        Args:
            text: The text to extract from
            
        Returns:
            Dictionary with reference rate details if found, None otherwise
        """
        # Common reference rates
        reference_rates = [
            'EURIBOR', 'LIBOR', 'SOFR', 'SONIA', 'EONIA', 'ESTER', '€STR', 
            'TIBOR', 'HIBOR', 'BBSW', 'CDOR', 'STIBOR', 'NIBOR', 'WIBOR',
            'PRIBOR', 'ROBOR', 'BUBOR', 'CIBOR', 'JIBAR', 'SAIBOR', 'SHIBOR',
            'T-Bill', 'Treasury', 'CMS', 'Fed Funds', 'TONAR', 'CORRA',
            'OIS', 'MSFR', 'TONA', 'SWESTR', 'THOR', 'HONIA', 'SABOR'
        ]
        
        # Pattern to match floating rate descriptions
        floating_patterns = [
            # Rate + spread format
            r'(?:floating|variable)\s+(?:interest\s+)?rate\s+(?:of\s+)?(\w+(?:[-\s]\w+)*)\s*(?:\d+[mdy]|\d+[- ]month|\d+[- ]year|\d+[- ]day)?\s*(?:\+|-)\s*(\d+(?:\.\d+)?)\s*(?:bps|basis\s+points|per\s*(?:cent\.?|%)|%)',
            r'(\w+(?:[-\s]\w+)*)\s*(?:\d+[mdy]|\d+[- ]month|\d+[- ]year|\d+[- ]day)?\s*(?:\+|-)\s*(\d+(?:\.\d+)?)\s*(?:bps|basis\s+points|per\s*(?:cent\.?|%)|%)',
            
            # Enhanced floating rate patterns
            r'(?:floating|variable)\s+(?:rate\s+of\s+)?(?:interest\s+at\s+)?(\w+(?:[-\s]\w+)*)\s*(?:\d+[mdy]|\d+[- ]month|\d+[- ]year|\d+[- ]day)?\s*(?:\+|-)\s*(\d+(?:\.\d+)?)\s*(?:bps|basis\s+points|per\s*(?:cent\.?|%)|%)',
            r'(?:interest\s+at\s+)(?:the\s+)?(?:rate\s+(?:of|equal\s+to)\s+)?(\w+(?:[-\s]\w+)*)\s*(?:\d+[mdy]|\d+[- ]month|\d+[- ]year|\d+[- ]day)?\s*(?:\+|-)\s*(\d+(?:\.\d+)?)\s*(?:bps|basis\s+points|per\s*(?:cent\.?|%)|%)',
            r'(?:interest\s+(?:rate\s+)?calculated\s+by\s+reference\s+to\s+)(\w+(?:[-\s]\w+)*)\s*(?:\d+[mdy]|\d+[- ]month|\d+[- ]year|\d+[- ]day)?\s*(?:\+|-)\s*(\d+(?:\.\d+)?)\s*(?:bps|basis\s+points|per\s*(?:cent\.?|%)|%)',
            r'(?:reference\s+rate\s+of\s+)(\w+(?:[-\s]\w+)*)\s*(?:\d+[mdy]|\d+[- ]month|\d+[- ]year|\d+[- ]day)?\s*(?:\+|-)\s*(\d+(?:\.\d+)?)\s*(?:bps|basis\s+points|per\s*(?:cent\.?|%)|%)',
            
            # General floating rate mentions
            r'(?:floating|variable)\s+(?:interest\s+)?rate\s+notes?',
            r'interest\s+(?:is|shall\s+be)\s+(?:calculated|determined|based)\s+(?:by\s+reference\s+)?(?:to|on)\s+(\w+(?:[-\s]\w+)*)',
            r'(?:bears|paying)\s+interest\s+at\s+a\s+(?:floating|variable)\s+rate',
            r'(?:margin|spread)\s+of\s+(\d+(?:\.\d+)?)\s*(?:bps|basis\s+points|per\s*(?:cent\.?|%)|%)',
            
            # Additional patterns
            r'interest\s+(?:rate\s+)?linked\s+to\s+(?:the\s+)?(\w+(?:[-\s]\w+)*)',
            r'(?:floating|variable)\s+(?:rate\s+)?notes?\s+with\s+(?:interest\s+)?(?:based\s+on|calculated\s+from)\s+(\w+(?:[-\s]\w+)*)',
            r'interest\s+(?:rate\s+)?equal\s+to\s+(\w+(?:[-\s]\w+)*)\s*(?:\d+[mdy]|\d+[- ]month|\d+[- ]year|\d+[- ]day)?\s*(?:\+|-)\s*(\d+(?:\.\d+)?)\s*(?:bps|basis\s+points|per\s*(?:cent\.?|%)|%)',
            r'notes\s+paying\s+(?:a\s+)?(\w+(?:[-\s]\w+)*)\s*(?:\d+[mdy]|\d+[- ]month|\d+[- ]year|\d+[- ]day)?\s*(?:\+|-)\s*(\d+(?:\.\d+)?)\s*(?:bps|basis\s+points|per\s*(?:cent\.?|%)|%)',
            r'the\s+applicable\s+reference\s+rate\s+(?:is|will\s+be)\s+(\w+(?:[-\s]\w+)*)'
        ]
        
        # Tenor patterns to capture rate period (e.g., 3-month EURIBOR)
        tenor_pattern = r'(\d+)[\-\s]?(?:month|year|day|week|m|y|d|w)'
        
        # Try to find a reference rate with spread
        for pattern in floating_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.group(0).lower().startswith(('floating', 'variable')) and len(match.groups()) < 2:
                    # Just found "floating rate notes" without specifics
                    return {
                        'reference_rate': None,
                        'spread': None,
                        'tenor': None,
                        'details': 'floating rate'
                    }
                    
                if len(match.groups()) >= 1:
                    ref_rate_match = match.group(1)
                    
                    # Extract tenor if present (e.g., 3-month)
                    tenor = None
                    tenor_match = re.search(tenor_pattern, ref_rate_match)
                    if tenor_match:
                        tenor = tenor_match.group(0)
                    else:
                        # Look for tenor in surrounding context
                        context_start = max(0, match.start() - 50)
                        context_end = min(len(text), match.end() + 50)
                        context = text[context_start:context_end]
                        tenor_context_match = re.search(tenor_pattern, context)
                        if tenor_context_match:
                            tenor = tenor_context_match.group(0)
                    
                    # Validate it's a known reference rate
                    ref_rate = None
                    for known_rate in reference_rates:
                        if known_rate.lower() in ref_rate_match.lower():
                            ref_rate = known_rate
                            break
                            
                    # Extract spread if available
                    spread = None
                    if len(match.groups()) >= 2 and match.group(2):
                        spread = match.group(2)
                    else:
                        # Look for spread in nearby context
                        spread_pattern = r'(?:margin|spread)(?:\s+of)?\s+(\d+(?:\.\d+)?)\s*(?:bps|basis\s+points|per\s*(?:cent\.?|%)|%)'
                        context_start = max(0, match.start() - 100)
                        context_end = min(len(text), match.end() + 100)
                        context = text[context_start:context_end]
                        spread_match = re.search(spread_pattern, context, re.IGNORECASE)
                        if spread_match:
                            spread = spread_match.group(1)
                            
                    # If found a reference rate, return the details
                    if ref_rate or 'floating' in match.group(0).lower() or 'variable' in match.group(0).lower():
                        return {
                            'reference_rate': ref_rate,
                            'spread': spread,
                            'tenor': tenor,
                            'details': match.group(0).strip()
                        }
        
        # Check for reference rate mentions without explicit formatting
        for rate in reference_rates:
            rate_match = re.search(r'\b' + rate + r'\b', text, re.IGNORECASE)
            if rate_match:
                # Look for spread in nearby context
                context_start = max(0, rate_match.start() - 50)
                context_end = min(len(text), rate_match.end() + 50)
                context = text[context_start:context_end]
                
                # Try to find a spread value
                spread_pattern = r'(?:margin|spread)(?:\s+of)?\s+(\d+(?:\.\d+)?)\s*(?:bps|basis\s+points|per\s*(?:cent\.?|%)|%)'
                spread_match = re.search(spread_pattern, context, re.IGNORECASE)
                
                # Also try to find plus/minus notation
                plus_minus_pattern = r'(?:\+|-)\s*(\d+(?:\.\d+)?)\s*(?:bps|basis\s+points|per\s*(?:cent\.?|%)|%)'
                plus_minus_match = re.search(plus_minus_pattern, context, re.IGNORECASE)
                
                spread = None
                if spread_match:
                    spread = spread_match.group(1)
                elif plus_minus_match:
                    spread = plus_minus_match.group(1)
                    
                # Look for tenor
                tenor = None
                tenor_match = re.search(tenor_pattern, context)
                if tenor_match:
                    tenor = tenor_match.group(0)
                    
                return {
                    'reference_rate': rate,
                    'spread': spread,
                    'tenor': tenor,
                    'details': f"{rate} {tenor if tenor else ''} {'+' + spread + '%' if spread else ''}"
                }
                
        # Check for general floating rate mentions
        if re.search(r'floating|variable', text, re.IGNORECASE):
            return {
                'reference_rate': None,
                'spread': None,
                'tenor': None,
                'details': 'floating rate'
            }
            
        return None
        
    def _extract_step_coupon(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract step-up or step-down coupon information.
        
        Args:
            text: The text to extract from
            
        Returns:
            Dictionary with step coupon details if found, None otherwise
        """
        # Check if this is likely a step-up or step-down coupon
        step_up_match = re.search(r'step[-\s]?up|increasing', text, re.IGNORECASE)
        step_down_match = re.search(r'step[-\s]?down|decreasing', text, re.IGNORECASE)
        
        if not (step_up_match or step_down_match):
            return None
            
        # Determine step type
        step_type = 'step-up' if step_up_match else 'step-down'
        
        # Look for initial rate
        initial_rate_match = re.search(r'(?:initial|first)(?:\s+(?:interest|coupon))?\s+rate\s*(?:of|is|:)?\s*(\d+(?:\.\d+)?)\s*(?:%|per\s*cent)', text, re.IGNORECASE)
        initial_rate = initial_rate_match.group(1) if initial_rate_match else None
        
        if not initial_rate:
            # Try alternative patterns for initial rate
            initial_rate_alt_match = re.search(r'(?:interest|coupon)\s+rate\s*(?:of|is|:)?\s*(\d+(?:\.\d+)?)\s*(?:%|per\s*cent).*?(?:for\s+the\s+(?:first|initial))', text, re.IGNORECASE)
            initial_rate = initial_rate_alt_match.group(1) if initial_rate_alt_match else None
            
            if not initial_rate:
                # Look for any rate mentioned before step-up/step-down
                before_step = text[:step_up_match.start() if step_up_match else step_down_match.start()]
                any_rate_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:%|per\s*cent)', before_step, re.IGNORECASE)
                initial_rate = any_rate_match.group(1) if any_rate_match else None
                
        # Extract all step information
        steps = []
        
        # Look for explicit step details
        # Pattern: [rate]% from [date], [rate]% from [date], etc.
        step_details_match = re.finditer(r'(\d+(?:\.\d+)?)\s*(?:%|per\s*cent).*?(?:from|on|after)\s+((?:\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{2,4}|\d{4}))', text, re.IGNORECASE)
        
        for match in step_details_match:
            rate = match.group(1)
            date_str = match.group(2)
            steps.append({
                'rate': rate,
                'date': date_str
            })
            
        # Look for "increases by X%" or "decreases by X%" patterns
        step_change_matches = re.finditer(r'(?:increases?|decreases?)\s+(?:by|to)\s+(\d+(?:\.\d+)?)\s*(?:%|per\s*cent|percentage\s+points?)', text, re.IGNORECASE)
        
        # If we found step changes but no specific steps
        if not steps:
            current_rate = float(initial_rate) if initial_rate else None
            for match in step_change_matches:
                change = float(match.group(1))
                
                # Look for a date or period in the nearby context
                context_start = max(0, match.start() - 50)
                context_end = min(len(text), match.end() + 50)
                context = text[context_start:context_end]
                
                # Try to find a date
                date_match = re.search(r'(?:from|on|after)\s+((?:\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{2,4}|\d{4}))', context, re.IGNORECASE)
                
                # Try to find a period or year
                period_match = re.search(r'(?:in|after|from)\s+(?:the\s+)?(?:year|period)\s+(\d+|first|second|third|fourth|fifth)', context, re.IGNORECASE)
                
                date_or_period = None
                if date_match:
                    date_or_period = date_match.group(1)
                elif period_match:
                    date_or_period = period_match.group(1)
                    
                # Calculate new rate
                if current_rate is not None:
                    if 'increase' in match.group(0).lower():
                        if 'to' in match.group(0).lower():
                            # Direct increase to a specific rate
                            new_rate = change
                        else:
                            # Increase by a percentage
                            new_rate = current_rate + change
                    else:  # decrease
                        if 'to' in match.group(0).lower():
                            # Direct decrease to a specific rate
                            new_rate = change
                        else:
                            # Decrease by a percentage
                            new_rate = current_rate - change
                            
                    steps.append({
                        'rate': str(new_rate),
                        'date_or_period': date_or_period
                    })
                    current_rate = new_rate
                
        # If we still don't have step details but have evidence of step-up/down
        if not steps and (step_up_match or step_down_match):
            # Look for multiple percentage mentions
            rate_mentions = re.findall(r'(\d+(?:\.\d+)?)\s*(?:%|per\s*cent)', text, re.IGNORECASE)
            
            if len(rate_mentions) >= 2:
                # Assume the first is initial and others are steps
                rates = [float(rate) for rate in rate_mentions]
                
                # Skip initial rate
                if initial_rate and rates[0] == float(initial_rate):
                    rates = rates[1:]
                    
                # Create generic steps
                for i, rate in enumerate(rates):
                    steps.append({
                        'rate': str(rate),
                        'step_number': i + 1
                    })
        
        # If we have initial rate and steps, return the full info
        if initial_rate or steps:
            result = {
                'type': step_type,
                'initial_rate': initial_rate,
                'steps': steps if steps else None
            }
            return result
            
        return None
        
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for coupon extraction.
        
        Args:
            text: The text to normalize
            
        Returns:
            Normalized text
        """
        # Replace variations in percentage notation
        normalized = re.sub(r'per\s*cent\.?', '%', text)
        normalized = re.sub(r'percent', '%', normalized)
        
        # Convert basis points to percentage format
        normalized = re.sub(r'(\d+)\s*(?:basis\s+points|bps)', lambda m: f"{float(m.group(1))/100}%", normalized)
        
        # Standardize spacing around percentage symbol
        normalized = re.sub(r'\s+%', '%', normalized)
        
        # Replace decimal separators if needed
        normalized = re.sub(r'(\d+),(\d+)', r'\1.\2', normalized)
        
        # Standardize step-up/step-down spelling
        normalized = re.sub(r'step\s+up', 'step-up', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'step\s+down', 'step-down', normalized, flags=re.IGNORECASE)
        
        return normalized 