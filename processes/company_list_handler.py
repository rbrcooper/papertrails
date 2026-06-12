"""
Company List Handler
------------------
This module handles loading and managing the list of companies to process.
"""

import os
import logging
import pandas as pd
from pathlib import Path
import hashlib
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class CompanyListHandler:
    """Handles loading and managing the list of companies to process.
    
    Supports both the legacy GOGEL Excel format and the new GOGEL 2025 CSV
    with financial identifiers (LEI, ISIN, PermID, FIGI).
    """

    EU_COUNTRIES = {
        'Austria', 'Belgium', 'Bulgaria', 'Croatia', 'Cyprus', 'Czech Republic',
        'Denmark', 'Estonia', 'Finland', 'France', 'Germany', 'Greece', 'Hungary',
        'Ireland', 'Italy', 'Latvia', 'Lithuania', 'Luxembourg', 'Malta',
        'Netherlands', 'Poland', 'Portugal', 'Romania', 'Slovakia', 'Slovenia',
        'Spain', 'Sweden'
    }

    def __init__(self, excel_path: str = 'data/raw/Urgewald GOGEL 2025 V1.2 with identifiers.csv',
                 region_filter: str = 'all', eu_countries: list = None):
        """Initialize the handler.
        
        Args:
            excel_path: Path to the GOGEL data file (.csv or .xlsx).
            region_filter: 'all' to load every company, 'eu' for EU-only,
                           or a comma-separated list of country names.
            eu_countries: Explicit list of EU countries (overrides default).
        """
        self.excel_path = Path(excel_path)
        self.region_filter = region_filter
        self.eu_countries = set(eu_countries) if eu_countries else self.EU_COUNTRIES
        self.companies = []
        self.processed_companies = set()
        self.processed_companies_file = Path('data/processed/processed_companies.txt')
        self.downloaded_docs_file = Path('data/processed/downloaded_documents.txt')
        self.company_stats_file = Path('data/processed/company_stats.json')
        self.downloaded_docs = set()
        self.company_stats = {}
        
        # Load companies from file
        self.load_companies()
        
        # Load progress if exists
        self.load_progress()
        
        # Load downloaded documents
        self.load_downloaded_docs()
        
        # Load company stats
        self.load_company_stats()
        
        self._ensure_files_exist()

    @staticmethod
    def _parse_multi_value(raw: str) -> list:
        """Parse a semicolon-separated field (possibly quoted) into a list of clean strings.
        
        Handles values like: "XS123; XS456; XS789" or just "XS123" or "." or NaN.
        Returns an empty list for missing / placeholder values.
        """
        if not isinstance(raw, str) or raw.strip() in ('', '.', 'NA', 'nan'):
            return []
        # Strip surrounding quotes if present
        raw = raw.strip().strip('"')
        parts = [v.strip() for v in raw.split(';') if v.strip() and v.strip() != '.']
        return parts
    
    def _ensure_files_exist(self):
        """Ensure the tracking files exist."""
        self.processed_companies_file.parent.mkdir(parents=True, exist_ok=True)
        for file_path in [self.processed_companies_file, self.downloaded_docs_file, self.company_stats_file]:
            if not file_path.exists():
                if file_path.suffix == '.json':
                    with open(file_path, 'w') as f:
                        json.dump({}, f)
                else:
                    file_path.touch()
    
    def load_company_stats(self):
        """Load company stats from JSON file"""
        try:
            if self.company_stats_file.exists():
                with open(self.company_stats_file, 'r') as f:
                    self.company_stats = json.load(f)
                logger.info(f"Loaded stats for {len(self.company_stats)} companies")
            else:
                self.company_stats = {}
        except Exception as e:
            logger.error(f"Error loading company stats: {str(e)}")
            self.company_stats = {}
    
    def save_company_stats(self):
        """Save company stats to JSON file"""
        try:
            with open(self.company_stats_file, 'w') as f:
                json.dump(self.company_stats, f, indent=2)
            logger.info(f"Saved stats for {len(self.company_stats)} companies")
        except Exception as e:
            logger.error(f"Error saving company stats: {str(e)}")
    
    def load_companies(self):
        """Load companies from the GOGEL data file.
        
        Auto-detects CSV vs Excel format. For the new GOGEL 2025 CSV, extracts
        financial identifiers (LEI, ISINs, PermID, FIGI) and attaches them to
        each company dict. Applies region filtering based on self.region_filter.
        """
        try:
            logger.info(f"Loading companies from {self.excel_path}")
            
            suffix = self.excel_path.suffix.lower()
            if suffix == '.csv':
                df = self._load_csv(self.excel_path)
            elif suffix in ('.xlsx', '.xls'):
                df = self._load_excel(self.excel_path)
            else:
                logger.error(f"Unsupported file format: {suffix}")
                self.companies = []
                return
            
            if df is None or df.empty:
                logger.warning("No data loaded from file")
                self.companies = []
                return

            # Apply region filter
            df = self._apply_region_filter(df)
            
            logger.info(f"Loaded {len(self.companies)} companies (filter: {self.region_filter})")
            
        except Exception as e:
            logger.error(f"Error loading companies: {str(e)}")
            self.companies = []

    def _load_csv(self, path: Path) -> 'pd.DataFrame':
        """Load and parse the GOGEL 2025 CSV with financial identifiers."""
        df = pd.read_csv(path, sep=';', encoding='utf-8')
        logger.info(f"CSV loaded: {len(df)} rows, columns: {list(df.columns)[:10]}...")

        # Expected column mapping (GOGEL 2025 CSV)
        name_col = 'name_company'
        country_col = 'hq_country'

        if name_col not in df.columns:
            # Fallback: try the first column
            logger.warning(f"Column '{name_col}' not found, using first column ({df.columns[0]})")
            name_col = df.columns[0]
        if country_col not in df.columns:
            logger.warning(f"Column '{country_col}' not found, using third column")
            country_col = df.columns[2] if len(df.columns) > 2 else None

        self.companies = []
        for _, row in df.iterrows():
            company_name = row.get(name_col) if isinstance(row.get(name_col), str) else None
            if not company_name or not company_name.strip():
                continue

            country = str(row.get(country_col, '')).strip() if country_col else ''
            
            company = {
                'name': company_name.strip(),
                'country': country,
                'status': 'Active',
                # Financial identifiers
                'lei': str(row.get('lei', '')).strip() if pd.notna(row.get('lei', '')) else '',
                'isin_equity': str(row.get('isin_equity', '')).strip() if pd.notna(row.get('isin_equity', '')) else '',
                'isins_bonds': self._parse_multi_value(str(row.get('isins_bonds', ''))),
                'isins_bonds_subsidiaries': self._parse_multi_value(str(row.get('isins_bonds_subsidiaries', ''))),
                'permid': str(row.get('lseg_permid', '')).strip() if pd.notna(row.get('lseg_permid', '')) else '',
                'figi': str(row.get('bloomberg_figi', '')).strip() if pd.notna(row.get('bloomberg_figi', '')) else '',
                # GOGEL metadata
                'hierarchy': str(row.get('company_hierarchy', '')).strip() if pd.notna(row.get('company_hierarchy', '')) else '',
                'parent_company': str(row.get('parent_company', '')).strip() if pd.notna(row.get('parent_company', '')) else '',
            }
            self.companies.append(company)
        
        return df

    def _load_excel(self, path: Path) -> 'pd.DataFrame':
        """Load the legacy GOGEL Excel format (positional columns, 'Upstream' sheet)."""
        df = pd.read_excel(path, sheet_name='Upstream', skiprows=3)
        logger.info(f"Excel loaded: {len(df)} rows")

        self.companies = []
        for _, row in df.iterrows():
            company_name = row.iloc[0]
            country = str(row.iloc[2]) if pd.notna(row.iloc[2]) else ''
            
            if pd.notna(company_name) and isinstance(company_name, str):
                company = {
                    'name': company_name.strip(),
                    'country': country,
                    'status': 'Active',
                    # No identifiers in legacy format
                    'lei': '',
                    'isin_equity': '',
                    'isins_bonds': [],
                    'isins_bonds_subsidiaries': [],
                    'permid': '',
                    'figi': '',
                    'hierarchy': '',
                    'parent_company': '',
                }
                self.companies.append(company)
        
        return df

    def _apply_region_filter(self, df) -> 'pd.DataFrame':
        """Filter self.companies in-place based on self.region_filter."""
        if self.region_filter == 'all':
            # No filtering
            return df
        
        if self.region_filter == 'eu':
            allowed_countries = self.eu_countries
        else:
            # Treat as comma-separated list of country names
            allowed_countries = {c.strip() for c in self.region_filter.split(',')}
        
        self.companies = [
            c for c in self.companies
            if c.get('country', '') in allowed_countries
        ]
        return df
    
    def get_all_companies(self):
        """Get list of all companies"""
        return self.companies
    
    def get_unprocessed_companies(self):
        """Get list of companies that haven't been processed yet"""
        return [c for c in self.companies if c['name'] not in self.processed_companies]
    
    def get_unprocessed_eu_companies(self):
        """Get list of unprocessed EU companies"""
        return [
            c
            for c in self.companies
            if c.get("country", "") in self.eu_countries and c["name"] not in self.processed_companies
        ]
    
    def mark_company_as_processed(self, company_name):
        """Mark a company as processed"""
        self.processed_companies.add(company_name)
        self.save_progress()
    
    def load_progress(self):
        """Load progress from file"""
        try:
            if self.processed_companies_file.exists():
                with open(self.processed_companies_file, 'r', encoding='utf-8') as f:
                    self.processed_companies = set(line.strip() for line in f)
                logger.info(f"Loaded {len(self.processed_companies)} processed companies")
        except Exception as e:
            logger.error(f"Error loading progress: {str(e)}")
    
    def save_progress(self):
        """Save progress to file"""
        try:
            with open(self.processed_companies_file, 'w', encoding='utf-8') as f:
                for company in sorted(self.processed_companies):
                    f.write(f"{company}\n")
            logger.info(f"Saved progress for {len(self.processed_companies)} companies")
        except Exception as e:
            logger.error(f"Error saving progress: {str(e)}")
    
    def get_company_by_name(self, name):
        """Get company details by name"""
        for company in self.companies:
            if company['name'].lower() == name.lower():
                return company
        return None
        
    def load_downloaded_docs(self):
        """Load list of already downloaded documents"""
        try:
            if self.downloaded_docs_file.exists():
                with open(self.downloaded_docs_file, 'r') as f:
                    self.downloaded_docs = set(line.strip() for line in f)
                logger.info(f"Loaded {len(self.downloaded_docs)} downloaded documents")
        except Exception as e:
            logger.error(f"Error loading downloaded documents: {str(e)}")
            self.downloaded_docs = set()
            
    def save_downloaded_docs(self):
        """Save list of downloaded documents"""
        try:
            # Create directory if it doesn't exist
            self.downloaded_docs_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.downloaded_docs_file, 'w') as f:
                for doc_id in sorted(self.downloaded_docs):
                    f.write(f"{doc_id}\n")
            logger.info(f"Saved {len(self.downloaded_docs)} downloaded documents")
        except Exception as e:
            logger.error(f"Error saving downloaded documents: {str(e)}")
            
    def is_document_downloaded(self, doc_id):
        """Check if a document has already been downloaded"""
        return doc_id in self.downloaded_docs
        
    def mark_document_as_downloaded(self, doc_id):
        """Mark a document as downloaded"""
        self.downloaded_docs.add(doc_id)
        self.save_downloaded_docs()
        
    def get_document_id(self, url, company_name, doc_type, date):
        """Generate a unique document ID based on URL, company name, doc type, and date"""
        # Create a string with all the document information
        doc_info = f"{url}_{company_name}_{doc_type}_{date}"
        
        # Generate a hash of the document information
        doc_hash = hashlib.md5(doc_info.encode()).hexdigest()
        
        return doc_hash

    def get_processed_companies(self) -> set:
        """Get the set of processed companies from the tracking file.
        
        Returns:
            set: Set of company names that have been processed
        """
        try:
            with open(self.processed_companies_file, 'r', encoding='utf-8') as f:
                return set(line.strip() for line in f if line.strip())
        except FileNotFoundError:
            return set()

    def add_document_stats(self, company_name, doc_type, date):
        """Add a downloaded document to the company stats"""
        if company_name not in self.company_stats:
            self.company_stats[company_name] = {
                "total_documents": 0,
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "document_types": {}
            }
        
        # Update company stats
        self.company_stats[company_name]["total_documents"] += 1
        self.company_stats[company_name]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        
        # Update document type counts
        if doc_type not in self.company_stats[company_name]["document_types"]:
            self.company_stats[company_name]["document_types"][doc_type] = 0
        self.company_stats[company_name]["document_types"][doc_type] += 1
        
        # Save updated stats
        self.save_company_stats()
        
    def get_document_hash(self, doc_info):
        """Generate a hash for a document to uniquely identify it"""
        # Create document hash with the required fields
        doc_str = f"{doc_info['issuer']}_{doc_info['document_type']}_{doc_info['date']}"
        return hashlib.md5(doc_str.encode()).hexdigest()
        
    def add_downloaded_document(self, doc_hash, company_name=None, doc_type=None, date=None):
        """Add a document hash to the set of downloaded documents and update stats if provided"""
        self.downloaded_docs.add(doc_hash)
        self.save_downloaded_docs()
        
        # Update company stats if details are provided
        if company_name and doc_type and date:
            self.add_document_stats(company_name, doc_type, date) 