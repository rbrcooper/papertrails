import pandas as pd
import logging
from typing import List, Dict
from pathlib import Path
import json

class CompanyListHandler:
    def __init__(self, excel_path: str):
        self.excel_path = excel_path
        self.logger = logging.getLogger(__name__)
        self.companies = {}  # Dictionary to store company info
        self.processed = set()  # Track processed companies
        
        # Define EU countries (including EEA countries)
        self.eu_countries = {
            'Austria', 'Belgium', 'Bulgaria', 'Croatia', 'Cyprus', 'Czech Republic',
            'Denmark', 'Estonia', 'Finland', 'France', 'Germany', 'Greece',
            'Hungary', 'Ireland', 'Italy', 'Latvia', 'Lithuania', 'Luxembourg',
            'Malta', 'Netherlands', 'Poland', 'Portugal', 'Romania', 'Slovakia',
            'Slovenia', 'Spain', 'Sweden', 'Iceland', 'Liechtenstein', 'Norway'
        }
        
        self.load_companies()
        
    def is_eu_country(self, country: str) -> bool:
        """Check if a country is in the EU/EEA"""
        if not country:
            return False
        # Normalize country name
        country = country.strip().lower()
        # Check against normalized EU country names
        return country in {c.lower() for c in self.eu_countries}
        
    def load_companies(self):
        """Load company information from Excel file (Upstream only)"""
        try:
            # Read Excel, skip first 2 rows, use row 3 as header
            df = pd.read_excel(self.excel_path, sheet_name='Upstream', header=2)
            
            # Get relevant columns - handle both original and renamed columns
            company_col = df.columns[0]  # First column is Company Name
            subsidiary_col = df.columns[1]  # Second column is Subsidiary Name
            country_col = df.columns[2]  # Third column is Country of Headquarters
            
            # Clean data and drop rows where company name is empty
            df = df.dropna(subset=[company_col])
            df = df[df[company_col].str.strip() != '']
            
            # Process each company
            eu_companies = 0
            for _, row in df.iterrows():
                company_name = str(row[company_col]).strip()
                country = str(row[country_col]).strip() if pd.notna(row[country_col]) else ''
                
                if company_name and company_name != 'Company Name':  # Skip header row if present
                    if self.is_eu_country(country):
                        self.companies[company_name] = {
                            'name': company_name,
                            'subsidiary': str(row[subsidiary_col]).strip() if pd.notna(row[subsidiary_col]) else '',
                            'country': country,
                        }
                        eu_companies += 1
            
            self.logger.info(f"Loaded {len(self.companies)} EU-based companies from Upstream")
            self.logger.info(f"Total companies in Excel: {len(df)}")
            
        except Exception as e:
            self.logger.error(f"Error loading companies: {str(e)}")
            raise
            
    def get_unprocessed_companies(self) -> List[Dict]:
        """Get list of unprocessed companies with their information"""
        return [
            company_info
            for company_name, company_info in self.companies.items()
            if company_name not in self.processed
        ]
        
    def mark_company_as_processed(self, company_name: str):
        """Mark a company as processed"""
        if company_name in self.companies:
            self.processed.add(company_name)
            self.logger.info(f"Marked {company_name} as processed")
            
    def save_progress(self, output_dir: str):
        """Save current progress to JSON file"""
        output_path = Path(output_dir) / 'company_progress.json'
        progress_data = {
            'companies': self.companies,
            'processed': list(self.processed)
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, indent=2, ensure_ascii=False)
        self.logger.info(f"Saved progress to {output_path}")
        
    def load_progress(self, progress_file: str):
        """Load progress from JSON file"""
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.companies = data['companies']
                self.processed = set(data['processed'])
            self.logger.info(f"Loaded progress from {progress_file}")
        except Exception as e:
            self.logger.warning(f"Could not load progress file: {str(e)}") 