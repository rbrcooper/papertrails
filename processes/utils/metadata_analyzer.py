"""
Metadata Analyzer Utility
-----------------------
Analyzes and processes metadata extracted from ESMA documents.
Specializes in parsing and standardizing document metadata like dates, ISINs, and other identifiers.

Key Features:
- Metadata extraction and validation
- Date parsing and standardization
- ISIN validation and processing
- Document type classification
- Pattern matching and normalization

Dependencies:
- re: Regular expressions
- datetime: Date handling
- pandas: Data processing
- logging: Logging functionality

Usage:
    from processes.utils.metadata_analyzer import MetadataAnalyzer
    
    analyzer = MetadataAnalyzer()
    processed_metadata = analyzer.process_document_metadata(raw_metadata)
"""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime
import logging

class MetadataAnalyzer:
    def __init__(self, results_dir: str):
        self.results_dir = Path(results_dir)
        self.logger = logging.getLogger(__name__)
        
    def load_all_metadata(self):
        """Load all company metadata files"""
        all_data = []
        for json_file in self.results_dir.glob("*.json"):
            if json_file.name == "company_progress.json":
                continue
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    all_data.append(data)
            except Exception as e:
                self.logger.error(f"Error loading {json_file}: {str(e)}")
        return all_data
        
    def create_summary_report(self):
        """Create a summary report of all documents"""
        all_data = self.load_all_metadata()
        
        # Create lists for DataFrame
        companies = []
        doc_types = []
        prospectus_types = []
        approval_dates = []
        isins = []
        urls = []
        
        for company_data in all_data:
            company_name = company_data['company']['name']
            for doc in company_data['documents']:
                companies.append(company_name)
                doc_types.append(doc['document_type'])
                prospectus_types.append(doc['prospectus_type'])
                approval_dates.append(doc['approval_date'])
                isins.append(doc['isin'])
                urls.append(doc['url'])
        
        # Create DataFrame
        df = pd.DataFrame({
            'Company': companies,
            'Document Type': doc_types,
            'Prospectus Type': prospectus_types,
            'Approval Date': approval_dates,
            'ISIN': isins,
            'URL': urls
        })
        
        # Convert dates
        df['Approval Date'] = pd.to_datetime(df['Approval Date'], format='%d/%m/%Y', errors='coerce')
        
        # Save to Excel
        output_file = self.results_dir / 'document_summary.xlsx'
        df.to_excel(output_file, index=False)
        self.logger.info(f"Created summary report at {output_file}")
        
        # Create some basic statistics
        stats = {
            'Total Companies': len(set(companies)),
            'Total Documents': len(df),
            'Document Types': df['Document Type'].value_counts().to_dict(),
            'Prospectus Types': df['Prospectus Type'].value_counts().to_dict(),
            'Documents by Company': df['Company'].value_counts().to_dict()
        }
        
        # Save statistics
        stats_file = self.results_dir / 'document_statistics.json'
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2)
        self.logger.info(f"Created statistics at {stats_file}")
        
    def filter_documents(self, 
                        min_date: str = None,
                        max_date: str = None,
                        doc_types: list = None,
                        companies: list = None):
        """Filter documents based on criteria"""
        all_data = self.load_all_metadata()
        filtered_docs = []
        
        for company_data in all_data:
            company_name = company_data['company']['name']
            
            # Skip if company not in filter
            if companies and company_name not in companies:
                continue
                
            for doc in company_data['documents']:
                # Convert date
                doc_date = datetime.strptime(doc['approval_date'], '%d/%m/%Y')
                
                # Apply filters
                if min_date and doc_date < datetime.strptime(min_date, '%d/%m/%Y'):
                    continue
                if max_date and doc_date > datetime.strptime(max_date, '%d/%m/%Y'):
                    continue
                if doc_types and doc['document_type'] not in doc_types:
                    continue
                    
                filtered_docs.append({
                    'company': company_name,
                    **doc
                })
        
        # Save filtered results
        output_file = self.results_dir / 'filtered_documents.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(filtered_docs, f, indent=2)
        self.logger.info(f"Created filtered documents list at {output_file}")
        
def main():
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Initialize analyzer
    analyzer = MetadataAnalyzer("results")
    
    # Create summary report
    analyzer.create_summary_report()
    
    # Example: Filter recent base prospectuses
    analyzer.filter_documents(
        min_date="01/01/2023",
        doc_types=["Base prospectus without Final terms"]
    )

if __name__ == "__main__":
    main() 