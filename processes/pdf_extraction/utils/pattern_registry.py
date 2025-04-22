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
                r'(?:FC\d+)_(\d{8})_'
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
                r'notes?\s+maturing\s+(?:in\s+)?(\d{4})'
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
                r'MXN', r'BRL', r'AED', r'SAR', r'QAR', r'KWD', r'INR'
            ],
            'currency_symbols': [
                r'\$', r'€', r'£', r'¥', r'Fr', r'kr', r'₽', r'₺', r'R\s', r'₹'
            ],
            'issue_size': [
                r'(?:aggregate\s+(?:nominal\s+)?amount|(?:total\s+)?(?:issue|principal)\s+(?:size|amount)|series\s+amount)\s*(?:of\s+(?:the\s+)?(?:notes|securities|bonds))?\s*[:\-]?\s*(?:up\s+to\s+)?([A-Z]{3}|\$|€|£|¥|Fr|₽|₺|R\s|kr|₹)?\s*[\d,.]+\s*(?:million|billion|m|bn)?(?:\s*([A-Z]{3}))?',
                r'(?:aggregate\s+(?:nominal\s+)?amount|(?:total\s+)?(?:issue|principal)\s+(?:size|amount)|series\s+amount)\s*(?:of\s+(?:the\s+)?(?:notes|securities|bonds))?\s*[:\-]?\s*(?:up\s+to\s+)?((?:USD|EUR|GBP|JPY|CHF|AUD|CAD|NZD|HKD|SGD|CNY|CNH|SEK|NOK|DKK|CZK|HUF|PLN|RUB|TRY|ZAR|MXN|BRL|AED|SAR|QAR|KWD|INR))\s*[\d,.]+\s*(?:million|billion|m|bn)?',
                r'[A-Z]{3}[-\s]denominated\s+(?:senior\s+)?(?:unsecured\s+)?notes?\s+(?:due\s+\d{4}\s+)?(?:in\s+(?:the\s+)?(?:aggregate\s+)?(?:principal\s+)?(?:amount\s+)?(?:of\s+)?)?\s*([A-Z]{3}|\$|€|£|¥|Fr|₽|₺|R\s|kr|₹)?\s*[\d,.]+\s*(?:million|billion|m|bn)?',
                r'[\d,.]+\s*(?:million|billion|m|bn)?\s*([A-Z]{3}|\$|€|£|¥|Fr|₽|₺|R\s|kr|₹)\s+(?:aggregate\s+(?:principal\s+)?amount|(?:issue|principal)\s+(?:size|amount))',
                r'[\d,.]+\s*(?:million|billion|m|bn)?\s*((?:USD|EUR|GBP|JPY|CHF|AUD|CAD|NZD|HKD|SGD|CNY|CNH|SEK|NOK|DKK|CZK|HUF|PLN|RUB|TRY|ZAR|MXN|BRL|AED|SAR|QAR|KWD|INR))\s+(?:aggregate\s+(?:principal\s+)?amount|(?:issue|principal)\s+(?:size|amount))'
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
                r'fixed\s+(?:rate\s+)?notes?\s+(?:due\s+\d{4}\s+)?(?:with|paying|at|of|bearing)\s+(?:a\s+(?:coupon|interest)\s+(?:rate\s+)?(?:of\s+)?)?(\d+(?:\.\d+)?)\s*(?:per\s*(?:cent\.?|%)|%)'
            ],
            'coupon_types': [
                r'fixed\s+rate', r'floating\s+rate', r'zero\s+coupon', 
                r'step[- ]up', r'step[- ]down', r'fixed[- ]to[- ]floating',
                r'floating[- ]to[- ]fixed', r'inflation[- ]linked', r'index[- ]linked',
                r'variable\s+rate', r'structured', r'range\s+accrual',
                r'fixed\s+spread', r'discount', r'premium'
            ]
        } 