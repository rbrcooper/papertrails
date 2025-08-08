class PatternRegistry:
    """Central repository for regex patterns used in extraction."""
    
    @staticmethod
    def get_date_patterns():
        """Get patterns for date extraction."""
        return {
            'issue_date': [
                r'(?:issue\s+date|date\s+of\s+issue|issuance\s+date)\s*[:\-]?\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'(?:issue\s+date|date\s+of\s+issue|issuance\s+date)\s*[:\-]?\s*(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{2,4})',
                r'(?:issue\s+date|date\s+of\s+issue|issuance\s+date)\s*[:\-]?\s*(?:on\s+)?(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{2,4})',
                r'(?:date\s+of\s+)?(?:initial\s+)?issu(?:e|ance)\s*(?:of\s+the\s+notes)?\s*(?:is|will\s+be)\s*(?:on\s+)?(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{2,4})',
                r'(?:date\s+of\s+)?(?:initial\s+)?issu(?:e|ance)\s*(?:of\s+the\s+notes)?\s*(?:is|will\s+be)\s*(?:on\s+)?(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'(?:supplement|prospectus)\s+dated\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{2,4})',
                r'(?:supplement|prospectus)\s+dated\s+(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'issue\s+of\s+(?:[A-Z]{3}|\$|€|£|¥)[\d,.]+(?:million|billion|m|bn)?\s+[\d.]+\s*%.*?dated\s+(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'(?:issue\s+date|date\s+of\s+issue|issuance\s+date)\s*[:\-]?\s*(?:(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{2,4})',
                r'(?:FC\d+)_(\d{8})_',
                # New patterns
                r'(?:issue\s+date|date\s+of\s+issue|issuance\s+date)\s*[:\-]?\s*(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})',  # YYYY-MM-DD format
                r'(?:to\s+be\s+issued|issue\s+date|issuance)\s*(?:on|as\s+of)\s*(?:the)?\s*(\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                r'issue\s+date\s*[:\-]?\s*(?:expected\s+to\s+be)?\s*(?:on\s+or\s+about)?\s*(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{2,4})',
                r'(?:bond|note)s?\s+(?:dated|as\s+of)\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                r'settlement\s+date\s*[:\-]?\s*(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                r'(?:dated|as\s+of)\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                # Enhanced patterns
                r'(?:closing|settlement|payment)\s+date\s*[:\-]?\s*(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                r'(?:closing|settlement|payment)\s+date\s*[:\-]?\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'(?:closing|settlement|payment)\s+date\s*[:\-]?\s*(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})',
                r'(?:issue|issuance|settlement)\s+date\s*[:\-]?\s*(?:is|shall\s+be|will\s+be|expected\s+to\s+be)?\s*(?:on\s+or\s+about|on|about|approximately)?\s*(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                r'(?:issue|issuance|settlement)\s+date\s*[:\-]?\s*(?:is|shall\s+be|will\s+be|expected\s+to\s+be)?\s*(?:on\s+or\s+about|on|about|approximately)?\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'(?:issue|issuance|settlement)\s+date\s*[:\-]?\s*(?:is|shall\s+be|will\s+be|expected\s+to\s+be)?\s*(?:on\s+or\s+about|on|about|approximately)?\s*(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})',
                r'(?:dated|as\s+of|dated\s+as\s+of)\s+(?:the\s+)?\s*(\d{1,2}(?:st|nd|rd|th)?\s+(?:day\s+of\s+)?(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                r'(?:issue|issuance)\s+date\s*[:]\s*(?:\d{1,2}[A-Za-z]{3}\d{2,4})',  # Special format like 01JAN2023
                r'(?:value|settlement)\s+date\s*[:]\s*(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                r'(?:value|settlement)\s+date\s*[:]\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'(?:value|settlement)\s+date\s*[:]\s*(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})',
                r'(?:these\s+final\s+terms\s+are\s+dated|pricing\s+supplement\s+dated)\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                r'(?:these\s+final\s+terms\s+are\s+dated|pricing\s+supplement\s+dated)\s+(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'(?:these\s+final\s+terms\s+are\s+dated|pricing\s+supplement\s+dated)\s+(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})',
                r'issue\s+date\s*[:]\s*(?:on\s+or\s+about\s+)?(\d{1,2}[A-Za-z]{3}\d{2,4})'  # Format like 01JAN2023
            ],
            'maturity_date': [
                r'(?:maturity\s+date|final\s+maturity|redemption\s+date)\s*[:\-]?\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'(?:maturity\s+date|final\s+maturity|redemption\s+date)\s*[:\-]?\s*(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{2,4})',
                r'(?:maturity\s+date|final\s+maturity|redemption\s+date)\s*[:\-]?\s*(?:on\s+)?(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{2,4})',
                r'(?:will\s+mature|matures|to\s+mature)\s*(?:on|at)\s*(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{2,4})',
                r'(?:will\s+mature|matures|to\s+mature)\s*(?:on|at)\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'due\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{2,4})',
                r'due\s+(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'due\s+(?:in\s+)?(\d{4})',
                r'notes?\s+maturing\s+(?:in|on)\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{2,4})',
                r'notes?\s+maturing\s+(?:in|on)\s+(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'notes?\s+maturing\s+(?:in\s+)?(\d{4})',
                # New patterns
                r'(?:maturity\s+date|final\s+maturity|redemption\s+date)\s*[:\-]?\s*(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})',  # YYYY-MM-DD format
                r'(?:notes?|bonds?)\s+due\s+(?:on\s+)?(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                r'scheduled\s+(?:to\s+)?(?:maturity|mature|redemption)\s+(?:on|date)?\s*[:\-]?\s*(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                r'(?:final|legal)\s+maturity\s+date\s*[:\-]?\s*(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                r'(?:scheduled\s+to\s+)?mature\s+on\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                r'expected\s+maturity\s+date\s*[:\-]?\s*(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                r'bullet\s+maturity\s+(?:on|in)\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4}|\d{4})',
                r'repayable\s+on\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                r'redemption\s+on\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                # Enhanced patterns
                r'(?:maturity|maturity\s+date|final\s+maturity|redemption\s+date)\s*[:\-]?\s*(?:is|shall\s+be|will\s+be|expected\s+to\s+be)?\s*(?:on\s+or\s+about|on|about|approximately)?\s*(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                r'(?:maturity|maturity\s+date|final\s+maturity|redemption\s+date)\s*[:\-]?\s*(?:is|shall\s+be|will\s+be|expected\s+to\s+be)?\s*(?:on\s+or\s+about|on|about|approximately)?\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'(?:maturity|maturity\s+date|final\s+maturity|redemption\s+date)\s*[:\-]?\s*(?:is|shall\s+be|will\s+be|expected\s+to\s+be)?\s*(?:on\s+or\s+about|on|about|approximately)?\s*(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})',
                r'redeemable\s+on\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                r'redeemable\s+on\s+(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'redeemable\s+on\s+(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})',
                r'(?:bonds|notes)\s+maturing\s+(?:on|in)\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                r'(?:bonds|notes)\s+maturing\s+(?:on|in)\s+(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'(?:bonds|notes)\s+maturing\s+(?:on|in)\s+(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})',
                r'maturity\s+date\s*[:]\s*(?:on\s+or\s+about\s+)?(\d{1,2}[A-Za-z]{3}\d{2,4})',  # Format like 01JAN2023
                r'(?:principal\s+)?repayment\s+date\s*[:]\s*(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                r'(?:principal\s+)?repayment\s+date\s*[:]\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'(?:principal\s+)?repayment\s+date\s*[:]\s*(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})',
                r'(?:the\s+)?(?:notes|bonds)\s+(?:are\s+scheduled\s+to|shall|will)\s+mature\s+on\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                r'(?:the\s+)?(?:notes|bonds)\s+(?:are\s+scheduled\s+to|shall|will)\s+mature\s+on\s+(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'(?:the\s+)?(?:notes|bonds)\s+(?:are\s+scheduled\s+to|shall|will)\s+mature\s+on\s+(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})',
                r'term\s*[:]\s*(?:\d+\s+years?\s+)?(?:maturing\s+)?(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{2,4})',
                r'term\s*[:]\s*(?:\d+\s+years?\s+)?(?:maturing\s+)?(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'term\s*[:]\s*(?:\d+\s+years?\s+)?(?:maturing\s+)?(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})'
            ]
        }
    
    @staticmethod
    def get_bank_patterns():
        """Get patterns for bank extraction."""
        return {
            'bank_roles': [
                r'(?:joint\s+)?(?:lead\s+)?(?:book[\-\s]?runner|manager|arranger|dealer|coordinator)',
                r'(?:joint\s+)?(?:lead\s+)?(?:book[\-\s]?runner|manager|arranger|dealer|coordinator)s?',
                r'co[\-\s]?(?:lead\s+)?(?:book[\-\s]?runner|manager|arranger|dealer)',
                r'co[\-\s]?(?:lead\s+)?(?:book[\-\s]?runner|manager|arranger|dealer)s?',
                r'(?:global|principal|structuring)\s+coordinator',
                r'(?:global|principal|structuring)\s+coordinators?',
                r'structuring\s+(?:advisor|agent|bank)',
                r'structuring\s+(?:advisors?|agents?|banks?)',
                r'(?:billing\s+and\s+)?delivery\s+(?:bank|agent)',
                r'(?:billing\s+and\s+)?delivery\s+(?:banks?|agents?)',
                r'stabili[sz](?:ation|ing)\s+(?:manager|agent|bank)',
                r'stabili[sz](?:ation|ing)\s+(?:managers?|agents?|banks?)',
                r'calculation\s+(?:agent|bank)',
                r'calculation\s+(?:agents?|banks?)',
                r'(?:principal|fiscal|paying|issuing|transfer|registration)\s+(?:agent|bank)',
                r'(?:principal|fiscal|paying|issuing|transfer|registration)\s+(?:agents?|banks?)',
                r'(?:trustee|listing\s+agent|registrar)',
                r'(?:trustees?|listing\s+agents?|registrars?)',
                r'dealer\s+manager',
                r'dealer\s+managers?',
                r'placement\s+agent',
                r'placement\s+agents?',
                r'underwriter',
                r'underwriters?',
                r'initial\s+purchaser',
                r'initial\s+purchasers?'
            ],
            'common_banks': [
                r'J\.?P\.?\s*Morgan', r'JPMorgan', r'J\.?P\.?\s*Morgan\s+Chase',
                r'Goldman\s+Sachs', r'Morgan\s+Stanley', r'HSBC',
                r'Barclays', r'Deutsche\s+Bank', r'BNP\s+Paribas', 
                r'Credit\s+Agricole', r'Credit\s+Agricole\s+CIB',
                r'Citi(?:group)?', r'Bank\s+of\s+America', r'BofA\s+Securities',
                r'Merrill\s+Lynch', r'UBS', r'RBC', r'Royal\s+Bank\s+of\s+Canada',
                r'Soci[eé]t[eé]\s+G[eé]n[eé]rale', r'SG', r'SocGen',
                r'Wells\s+Fargo', r'Credit\s+Suisse', r'Nomura',
                r'Mizuho', r'Santander', r'BBVA', r'UniCredit',
                r'Standard\s+Chartered', r'Scotiabank', r'ING',
                r'DNB', r'Natixis', r'SMBC', r'Sumitomo\s+Mitsui',
                r'NatWest', r'RBS', r'Royal\s+Bank\s+of\s+Scotland',
                r'Banco\s+Bilbao', r'Commerzbank', r'Danske\s+Bank',
                r'LBBW', r'Nord/LB', r'BayernLB', r'DZ\s+Bank',
                r'CIBC', r'ABN\s+AMRO', r'Rabobank', r'Intesa\s+Sanpaolo',
                r'Natwest\s+Markets', r'Lloyds', r'BNY\s+Mellon',
                r'Nordea', r'BMO', r'Bank\s+of\s+Montreal', r'TD\s+Securities',
                r'Handelsbanken', r'SEB', r'Swedbank', r'Citibank',
                r'PNC', r'US\s+Bancorp', r'Jefferies', r'Mitsubishi\s+UFJ',
                r'MUFG', r'Bank\s+of\s+China', r'Commonwealth\s+Bank',
                r'China\s+Construction\s+Bank', r'ICBC', r'ANZ',
                r'Westpac', r'NAB', r'National\s+Australia\s+Bank',
                r'Standard\s+Bank', r'First\s+Abu\s+Dhabi\s+Bank', r'FAB',
                r'Emirates\s+NBD', r'Qatar\s+National\s+Bank', r'QNB',
                r'Samba', r'KfW', r'La\s+Caixa', r'CaixaBank',
                r'Landesbank', r'Helaba', r'WestLB', r'Belfius',
                r'Fortis', r'Mediobanca', r'BayernLB'
            ]
        }
    
    @staticmethod
    def get_currency_patterns():
        """Get patterns for currency and issue size extraction."""
        return {
            'currency_codes': [
                r'USD', r'EUR', r'GBP', r'JPY', r'CHF', r'AUD', r'CAD', 
                r'NZD', r'HKD', r'SGD', r'CNY', r'CNH', r'SEK', r'NOK', 
                r'DKK', r'CZK', r'HUF', r'PLN', r'RUB', r'TRY', r'ZAR',
                r'MXN', r'BRL', r'AED', r'SAR', r'QAR', r'KWD', r'INR',
                # Additional currency codes
                r'IDR', r'THB', r'VND', r'MYR', r'PHP', r'ILS', r'CLP',
                r'COP', r'PEN', r'ARS', r'UYU', r'RON', r'BGN', r'HRK',
                r'ISK', r'NGN', r'KES', r'UAH', r'KZT', r'MAD', r'EGP'
            ],
            'currency_symbols': [
                r'\$', r'€', r'£', r'¥', r'Fr', r'kr', r'₽', r'₺', r'R\s', r'₹',
                # Additional currency symbols
                r'A\$', r'C\$', r'HK\$', r'S\$', r'NZ\$', r'₦', r'₱', r'฿', r'₫',
                r'RM', r'₪', r'₡', r'₲', r'₴', r'₸', r'₼', r'₾', r'лв', r'zł'
            ],
            'issue_size': [
                r'(?:aggregate\s+(?:nominal\s+)?amount|(?:total\s+)?(?:issue|principal)\s+(?:size|amount)|series\s+amount)\s*(?:of\s+(?:the\s+)?(?:notes|securities|bonds))?\s*[:\-]?\s*(?:up\s+to\s+)?([A-Z]{3}|\$|€|£|¥|Fr|₽|₺|R\s|kr|₹)?\s*[\d,.]+\s*(?:million|billion|m|bn)?(?:\s*([A-Z]{3}))?',
                r'(?:aggregate\s+(?:nominal\s+)?amount|(?:total\s+)?(?:issue|principal)\s+(?:size|amount)|series\s+amount)\s*(?:of\s+(?:the\s+)?(?:notes|securities|bonds))?\s*[:\-]?\s*(?:up\s+to\s+)?((?:USD|EUR|GBP|JPY|CHF|AUD|CAD|NZD|HKD|SGD|CNY|CNH|SEK|NOK|DKK|CZK|HUF|PLN|RUB|TRY|ZAR|MXN|BRL|AED|SAR|QAR|KWD|INR))\s*[\d,.]+\s*(?:million|billion|m|bn)?',
                r'[A-Z]{3}[-\s]denominated\s+(?:senior\s+)?(?:unsecured\s+)?notes?\s+(?:due\s+\d{4}\s+)?(?:in\s+(?:the\s+)?(?:aggregate\s+)?(?:principal\s+)?(?:amount\s+)?(?:of\s+)?)?\s*([A-Z]{3}|\$|€|£|¥|Fr|₽|₺|R\s|kr|₹)?\s*[\d,.]+\s*(?:million|billion|m|bn)?',
                r'[\d,.]+\s*(?:million|billion|m|bn)?\s*([A-Z]{3}|\$|€|£|¥|Fr|₽|₺|R\s|kr|₹)\s+(?:aggregate\s+(?:principal\s+)?amount|(?:issue|principal)\s+(?:size|amount))',
                r'[\d,.]+\s*(?:million|billion|m|bn)?\s*((?:USD|EUR|GBP|JPY|CHF|AUD|CAD|NZD|HKD|SGD|CNY|CNH|SEK|NOK|DKK|CZK|HUF|PLN|RUB|TRY|ZAR|MXN|BRL|AED|SAR|QAR|KWD|INR))\s+(?:aggregate\s+(?:principal\s+)?amount|(?:issue|principal)\s+(?:size|amount))',
                # New patterns for issue size
                r'(?:issue|offering)\s+(?:size|amount)\s*[:\-]?\s*(?:of\s+)?(?:up\s+to\s+)?([A-Z]{3}|\$|€|£|¥|Fr|₽|₺|R\s|kr|₹)?\s*([\d,.]+)\s*(?:million|billion|m|bn)?',
                r'(?:up\s+to\s+)?([A-Z]{3}|\$|€|£|¥|Fr|₽|₺|R\s|kr|₹)?\s*([\d,.]+)\s*(?:million|billion|m|bn)?\s*(?:in\s+(?:principal|nominal)\s+amount)',
                r'(?:amount|size)\s+of\s+(?:the\s+)?(?:offering|issuance)\s*[:\-]?\s*(?:up\s+to\s+)?([A-Z]{3}|\$|€|£|¥|Fr|₽|₺|R\s|kr|₹)?\s*([\d,.]+)\s*(?:million|billion|m|bn)?',
                r'(?:issue|offering)\s+of\s+(?:up\s+to\s+)?(?:approximately\s+)?([A-Z]{3}|\$|€|£|¥|Fr|₽|₺|R\s|kr|₹)?\s*([\d,.]+)\s*(?:million|billion|m|bn)',
                r'(?:expected\s+(?:aggregate\s+)?(?:principal|nominal)\s+amount)\s*[:\-]?\s*(?:up\s+to\s+)?([A-Z]{3}|\$|€|£|¥)?\s*([\d,.]+)\s*(?:million|billion|m|bn)?',
                r'(?:maximum\s+(?:aggregate\s+)?(?:issuance|amount))\s*[:\-]?\s*(?:up\s+to\s+)?([A-Z]{3}|\$|€|£|¥)?\s*([\d,.]+)\s*(?:million|billion|m|bn)?',
                r'(?:between|from)\s+([A-Z]{3}|\$|€|£|¥)?\s*([\d,.]+)\s*(?:million|billion|m|bn)?\s*(?:and|to|-)\s*([A-Z]{3}|\$|€|£|¥)?\s*([\d,.]+)\s*(?:million|billion|m|bn)?',
                # Additional enhanced patterns
                r'(?:up\s+to\s+)?(?:a\s+)?(?:maximum\s+(?:aggregate\s+)?amount\s+of\s+)?([A-Z]{3}|\$|€|£|¥|Fr|₽|₺|R\s|kr|₹)?\s*([\d,.]+)\s*(?:million|billion|thousand|m\b|bn|k\b)?',
                r'(?:up\s+to\s+)?((?:USD|EUR|GBP|JPY|CHF|AUD|CAD|NZD|HKD|SGD|CNY|CNH|SEK|NOK|DKK|CZK|HUF|PLN|RUB|TRY|ZAR|MXN|BRL|AED|SAR|QAR|KWD|INR))\s*([\d,.]+)\s*(?:million|billion|thousand|m\b|bn|k\b)?',
                r'(?:programme\s+size|issuance\s+limit|facility\s+amount)\s*(?:of\s+)?(?:up\s+to\s+)?([A-Z]{3}|\$|€|£|¥|Fr|₽|₺|R\s|kr|₹)?\s*([\d,.]+)\s*(?:million|billion|thousand|m\b|bn|k\b)?',
                r'(?:issue|issuance)\s+volume\s*(?:of\s+)?(?:up\s+to\s+)?([A-Z]{3}|\$|€|£|¥|Fr|₽|₺|R\s|kr|₹)?\s*([\d,.]+)\s*(?:million|billion|thousand|m\b|bn|k\b)?',
                r'(?:total\s+size\s+of\s+the\s+bond)\s*(?:is\s+)?([A-Z]{3}|\$|€|£|¥|Fr|₽|₺|R\s|kr|₹)?\s*([\d,.]+)\s*(?:million|billion|thousand|m\b|bn|k\b)?',
                r'(?:value|size)\s+of\s+(?:the\s+)?(?:issue|issuance|offering)\s*[:\-]?\s*([A-Z]{3}|\$|€|£|¥|Fr|₽|₺|R\s|kr|₹)?\s*([\d,.]+)\s*(?:million|billion|thousand|m\b|bn|k\b)?',
                r'(?:issued|issuance)\s+in\s+(?:the\s+)?(?:amount\s+of\s+)?([A-Z]{3}|\$|€|£|¥|Fr|₽|₺|R\s|kr|₹)?\s*([\d,.]+)\s*(?:million|billion|thousand|m\b|bn|k\b)?',
                # European format handling (dot as thousands separator)
                r'(?:aggregate\s+(?:nominal\s+)?amount|(?:total\s+)?(?:issue|principal)\s+(?:size|amount)|series\s+amount)\s*(?:of\s+(?:the\s+)?(?:notes|securities|bonds))?\s*[:\-]?\s*(?:up\s+to\s+)?([A-Z]{3}|\$|€|£|¥|Fr|₽|₺|R\s|kr|₹)?\s*[\d.]+(?:,\d+)?\s*(?:million|billion|m|bn)?(?:\s*([A-Z]{3}))?',
                r'(?:aggregate\s+(?:nominal\s+)?amount|(?:total\s+)?(?:issue|principal)\s+(?:size|amount)|series\s+amount)\s*(?:of\s+(?:the\s+)?(?:notes|securities|bonds))?\s*[:\-]?\s*(?:up\s+to\s+)?((?:USD|EUR|GBP|JPY|CHF|AUD|CAD|NZD|HKD|SGD|CNY|CNH|SEK|NOK|DKK|CZK|HUF|PLN|RUB|TRY|ZAR|MXN|BRL|AED|SAR|QAR|KWD|INR))\s*[\d.]+(?:,\d+)?\s*(?:million|billion|m|bn)?'
            ]
        }
    
    @staticmethod
    def get_coupon_patterns():
        """Get patterns for coupon rate extraction."""
        return {
            'coupon_rate': [
                r'(?:interest\s+rate|coupon\s+rate|rate\s+of\s+interest|fixed\s+rate|coupon|interest)\s*[:\-]?\s*(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                r'(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)(?:\s+(?:fixed\s+)?(?:rate\s+)?(?:interest|coupon))',
                r'(?:bear\s+interest\s+at|pays|with|carries|offering|bearing)(?:\s+a)?\s*(?:fixed\s+)?(?:rate\s+)?(?:coupon\s+)?(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                r'fixed\s+(?:rate\s+)?notes?\s+(?:due\s+\d{4}\s+)?(?:with|paying|at|of|bearing)\s+(?:a\s+(?:coupon|interest)\s+(?:rate\s+)?(?:of\s+)?)?(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                # New patterns for coupon rate
                r'(?:annual\s+)?(?:interest\s+rate|coupon)\s*(?:is|will\s+be|of)\s*(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                r'interest\s+(?:will\s+)?accrue\s*(?:at\s+(?:the\s+)?(?:rate\s+)?(?:of\s+)?)?(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                r'notes?\s+(?:with|bearing|paying|has|have|having)\s+(?:a\s+)?(?:fixed\s+)?(?:coupon|interest)\s+(?:rate\s+)?(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                r'interest\s+(?:payable|paid)\s+(?:at|on)\s+(?:a\s+)?(?:fixed\s+)?(?:rate\s+)?(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                r'coupon\s*[:\-]?\s*(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                r'(?:issue|issuance)\s+of\s+(?:[A-Z]{3}|\$|€|£)[\d,.]+(?:million|billion|m|bn)?\s+(\d+(?:\.\d+)?)\s*%',
                r'(\d+(?:\.\d+)?)\s*%\s+(?:fixed\s+rate\s+)?(?:notes|bonds)',
                r'interest\s+is\s+calculated\s+at\s+a\s+(?:fixed\s+)?rate\s+of\s+(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                r'initial\s+(?:fixed\s+)?(?:interest\s+)?rate\s+(?:is|of)\s+(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                # Additional enhanced patterns
                r'interest\s+rate\s+on\s+the\s+notes\s+(?:is|will\s+be)\s+(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                r'notes\s+shall\s+bear\s+interest\s+at\s+the\s+rate\s+of\s+(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                r'interest\s+shall\s+be\s+payable\s+at\s+(?:the\s+)?rate\s+of\s+(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                r'(?:subject\s+to\s+)?interest\s+at\s+(?:the\s+)?rate\s+of\s+(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                r'coupon\s+(?:of|for)\s+the\s+(?:bonds|notes)\s+(?:is|will\s+be|equals|amounts\s+to)\s+(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                r'issued\s+with\s+(?:a\s+)?fixed\s+rate\s+(?:of|at)\s+(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                r'(?:yield|coupon)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                r'bonds?\s+with\s+(?:a\s+)?yield\s+(?:of|at)\s+(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                r'(?:coupon|interest)\s+(?:rate\s+)?set\s+at\s+(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                r'fixed\s+annual\s+(?:interest|coupon)\s+(?:of|at)\s+(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                r'(?:bond|note)s?\s+carrying\s+a\s+(?:coupon|interest\s+rate)\s+of\s+(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                r'yearly\s+coupon\s+(?:of|at|:)\s+(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)',
                # Specific formats with trailing percent signs
                r'interest\s+(?:rate|coupon)[\s\-:]+(\d+(?:\.\d+)?)\s*%'
            ],
            'coupon_types': [
                r'fixed\s+rate', r'floating\s+rate', r'zero\s+coupon', 
                r'step[- ]up', r'step[- ]down', r'fixed[- ]to[- ]floating',
                r'floating[- ]to[- ]fixed', r'inflation[- ]linked', r'index[- ]linked',
                r'variable\s+rate', r'structured', r'range\s+accrual',
                r'fixed\s+spread', r'discount', r'premium',
                # New coupon types
                r'zero[- ]coupon', r'non[- ]interest[- ]bearing', r'interest[- ]free',
                r'step[- ]coupon', r'dual[- ]currency', r'convertible',
                r'reference[- ]rate[- ]linked', r'callable', r'puttable',
                r'reset', r'capped', r'capped[- ]floating', r'collared[- ]floating', 
                r'reverse[- ]floating', r'hybrid', r'subordinated', 
                r'perpetual', r'deferred[- ]interest', r'payment[- ]in[- ]kind',
                r'credit[- ]linked', r'inverse[- ]floating', r'amortizing',
                # Additional new types
                r'floating[- ]rate', r'variable[- ]rate', r'adjustable[- ]rate',
                r'euribor[- ]linked', r'libor[- ]linked', r'sofr[- ]linked', r'sonia[- ]linked',
                r'benchmark[- ]linked', r'inflation[- ]protected', r'real[- ]return',
                r'constant[- ]maturity[- ]swap', r'cms[- ]linked', r'increasing[- ]rate',
                r'decreasing[- ]rate', r'multi[- ]tranche', r'extendible', r'retractable',
                r'zero[- ]interest', r'increasing[- ]coupon', r'decreasing[- ]coupon',
                r'interest[- ]only', r'principal[- ]only', r'accreting[- ]principal',
                r'step[- ]rate', r'fix[- ]to[- ]float'
            ],
            'floating_rate_terms': [
                r'euribor', r'libor', r'sofr', r'sonia', r'eonia', r'ester', r'€str',
                r'tibor', r'hibor', r'bbsw', r'cdor', r'stibor', r'nibor', r'wibor',
                r'pribor', r'robor', r'bubor', r'cibor', r'jibar', r'saibor', r'shibor',
                r't-bill', r'treasury', r'cms', r'fed\s+funds', r'tonar', r'corra',
                r'ois', r'msfr', r'tona', r'swestr', r'thor', r'honia', r'sabor',
                r'reference\s+rate'
            ],
            'step_coupon_terms': [
                r'step[- ]up', r'step[- ]down', r'increasing\s+(?:coupon|interest|rate)',
                r'decreasing\s+(?:coupon|interest|rate)', r'step[- ]rate',
                r'graduated\s+(?:coupon|interest|rate)', r'escalating\s+(?:coupon|interest|rate)',
                r'initial\s+rate.*?(?:increases|decreases)', r'rate\s+(?:increases|decreases)',
                r'coupon\s+(?:increases|decreases)', r'interest\s+(?:increases|decreases)',
                r'changes?\s+in\s+(?:rate|coupon|interest)', r'(?:rate|coupon|interest)\s+changes?'
            ]
        } 