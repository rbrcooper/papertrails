import logging
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import pandas as pd

from database.db_manager import DatabaseManager
from utils.helpers import (
    setup_logging,
    save_json,
    load_json,
    save_excel,
    parse_date,
    clean_text,
    validate_required_fields
)
from config.settings import (
    FINANCIAL_DATA_DIR,
    PDF_DIR,
    COMPANIES,
    DOCUMENT_TYPES
)

class ProcessManager:
    def __init__(self):
        self.logger = setup_logging(__name__)
        self.db = DatabaseManager()
        self.db.init_db()
        
    def run_collection_process(self):
        """Run the complete data collection process"""
        try:
            self.logger.info("Starting data collection process")
            
            # Create summary data structures
            collection_summary = {
                "start_time": datetime.utcnow().isoformat(),
                "companies_processed": [],
                "total_bonds": 0,
                "total_documents": 0,
                "errors": []
            }
            
            # Process each company
            for company_name, company_info in COMPANIES.items():
                company_summary = self.process_company(company_name, company_info)
                collection_summary["companies_processed"].append(company_summary)
                collection_summary["total_bonds"] += company_summary["bonds_processed"]
                collection_summary["total_documents"] += company_summary["documents_processed"]
                
            # Save collection summary
            collection_summary["end_time"] = datetime.utcnow().isoformat()
            self.save_collection_summary(collection_summary)
            
            self.logger.info("Data collection process completed successfully")
            
        except Exception as e:
            self.logger.error(f"Error in collection process: {str(e)}")
            raise
            
    def process_company(self, company_name: str, company_info: Dict[str, str]) -> Dict[str, Any]:
        """Process data for a specific company"""
        company_summary = {
            "company_name": company_name,
            "start_time": datetime.utcnow().isoformat(),
            "bonds_processed": 0,
            "documents_processed": 0,
            "errors": []
        }
        
        try:
            # Get or create issuer
            issuer = self.db.get_issuer_by_name(company_name)
            if not issuer:
                issuer = self.db.add_issuer(
                    name=company_name,
                    lei=company_info['lei'],
                    country=company_info['country']
                )
                
            # Collect bond data
            bonds_data = self.collect_bond_data(company_info['lei'])
            
            # Process each bond
            for bond_data in bonds_data:
                try:
                    self.process_bond(bond_data, issuer.id)
                    company_summary["bonds_processed"] += 1
                except Exception as e:
                    company_summary["errors"].append({
                        "bond_isin": bond_data.get('isin', 'unknown'),
                        "error": str(e)
                    })
                    
            # Generate company report
            self.generate_company_report(company_name)
            
        except Exception as e:
            company_summary["errors"].append({
                "type": "company_processing",
                "error": str(e)
            })
            
        company_summary["end_time"] = datetime.utcnow().isoformat()
        return company_summary
        
    def collect_bond_data(self, lei: str) -> List[Dict[str, Any]]:
        """Collect bond data from ESMA website"""
        # This method will be implemented in the ESMAProcessor class
        # For now, we'll return an empty list
        return []
        
    def process_bond(self, bond_data: Dict[str, Any], issuer_id: int):
        """Process a single bond and its documents"""
        if not validate_required_fields(bond_data, REQUIRED_BOND_FIELDS):
            raise ValueError(f"Missing required fields for bond {bond_data.get('isin', 'unknown')}")
            
        # Get or create bond
        bond = self.db.get_bond_by_isin(bond_data['isin'])
        if not bond:
            bond = self.db.add_bond(
                isin=bond_data['isin'],
                name=bond_data['name'],
                issuer_id=issuer_id,
                issue_date=bond_data['issue_date'],
                maturity_date=bond_data['maturity_date'],
                currency=bond_data['currency'],
                nominal_amount=bond_data['nominal_amount']
            )
            
        # Collect and process documents
        self.collect_documents(bond.id, bond_data['isin'])
        
    def collect_documents(self, bond_id: int, isin: str):
        """Collect and process documents for a bond"""
        # This method will be implemented in the ESMAProcessor class
        # For now, we'll just log the action
        self.logger.info(f"Collecting documents for bond {isin}")
        
    def generate_company_report(self, company_name: str):
        """Generate a report for a specific company"""
        try:
            # Get company data from database
            issuer = self.db.get_issuer_by_name(company_name)
            if not issuer:
                return
                
            # Get all bonds for the company
            bonds = self.db.get_session().query(Bond).filter(Bond.issuer_id == issuer.id).all()
            
            # Prepare report data
            report_data = []
            for bond in bonds:
                bond_data = {
                    "isin": bond.isin,
                    "name": bond.name,
                    "issue_date": bond.issue_date,
                    "maturity_date": bond.maturity_date,
                    "currency": bond.currency,
                    "amount": bond.amount,
                    "coupon_rate": bond.coupon_rate,
                    "document_count": len(bond.documents)
                }
                report_data.append(bond_data)
                
            # Save report
            report_filename = f"{company_name.lower()}_bonds_report.xlsx"
            save_excel(report_data, report_filename)
            
        except Exception as e:
            self.logger.error(f"Error generating report for {company_name}: {str(e)}")
            
    def save_collection_summary(self, summary: Dict[str, Any]):
        """Save the collection process summary"""
        try:
            # Save as JSON
            save_json(summary, "collection_summary.json")
            
            # Save as Excel
            excel_data = []
            for company in summary["companies_processed"]:
                excel_data.append({
                    "Company": company["company_name"],
                    "Bonds Processed": company["bonds_processed"],
                    "Documents Processed": company["documents_processed"],
                    "Start Time": company["start_time"],
                    "End Time": company["end_time"],
                    "Error Count": len(company["errors"])
                })
                
            save_excel(excel_data, "collection_summary.xlsx")
            
        except Exception as e:
            self.logger.error(f"Error saving collection summary: {str(e)}")
            
    def validate_data(self):
        """Validate the collected data"""
        try:
            validation_results = {
                "timestamp": datetime.utcnow().isoformat(),
                "companies": {}
            }
            
            for company_name in COMPANIES:
                company_validation = self.validate_company_data(company_name)
                validation_results["companies"][company_name] = company_validation
                
            # Save validation results
            save_json(validation_results, "validation_results.json")
            
        except Exception as e:
            self.logger.error(f"Error in data validation: {str(e)}")
            
    def validate_company_data(self, company_name: str) -> Dict[str, Any]:
        """Validate data for a specific company"""
        validation = {
            "issuer": None,
            "bonds": [],
            "documents": [],
            "errors": []
        }
        
        try:
            # Validate issuer
            issuer = self.db.get_issuer_by_name(company_name)
            if issuer:
                validation["issuer"] = {
                    "name": issuer.name,
                    "lei": issuer.lei,
                    "country": issuer.country,
                    "bond_count": len(issuer.bonds)
                }
                
            # Validate bonds
            if issuer:
                for bond in issuer.bonds:
                    bond_validation = {
                        "isin": bond.isin,
                        "name": bond.name,
                        "has_documents": len(bond.documents) > 0,
                        "document_types": [doc.type for doc in bond.documents]
                    }
                    validation["bonds"].append(bond_validation)
                    
        except Exception as e:
            validation["errors"].append(str(e))
            
        return validation 