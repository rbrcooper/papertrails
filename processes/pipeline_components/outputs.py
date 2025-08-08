import json
from datetime import datetime
import pandas as pd
# Assuming DataAggregator is in the same directory or configured in PYTHONPATH
# from .aggregation import DataAggregator 

class OutputGenerator:
    def __init__(self, aggregator):
        # aggregator is an instance of DataAggregator
        self.aggregator = aggregator
        
    def generate_json(self, output_path):
        # Ensure output_path includes the .json extension
        if not output_path.lower().endswith('.json'):
            output_path += '.json'
            
        data = self.aggregator.aggregate_results() 
        
        # Add metadata
        output = {
            'generated_at': datetime.now().isoformat(),
            'total_companies': len(data),
            'total_bonds': sum(c.get('total_bonds', 0) for c in data.values()),
            'companies': data
        }
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            print(f"JSON output successfully generated at {output_path}")
        except IOError as e:
            print(f"Error writing JSON to {output_path}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during JSON generation: {e}")
            
    def generate_excel(self, output_path):
        # Ensure output_path includes the .xlsx extension
        if not output_path.lower().endswith('.xlsx'):
            output_path += '.xlsx'

        data = self.aggregator.aggregate_results()
        
        if not data:
            print("No data to generate Excel report.")
            return

        try:
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                self._create_summary_sheet(data, writer)
                self._create_company_sheet(data, writer)
                self._create_bond_sheet(data, writer)
                self._create_bank_sheet(data, writer)
            print(f"Excel output successfully generated at {output_path}")
        except ImportError:
            print("Pandas or openpyxl is not installed. Cannot generate Excel. Please install them.")
        except Exception as e:
            print(f"An unexpected error occurred during Excel generation: {e}")

    # Placeholder private methods for Excel sheet creation
    # These would need to be implemented based on specific reporting requirements

    def _create_summary_sheet(self, data, writer):
        # Example: Create a summary DataFrame
        summary_data = []
        for company_name, company_data in data.items():
            total_amount_str = ", ".join([f"{amt:.2f} {curr}" for curr, amt in company_data.get('total_amount', {}).items()])
            summary_data.append({
                'Company Name': company_name,
                'Total Bonds': company_data.get('total_bonds', 0),
                'Total Amount': total_amount_str,
                'Unique Banks Involved': len(company_data.get('banks', {})),
            })
        summary_df = pd.DataFrame(summary_data)
        if not summary_df.empty:
            summary_df.to_excel(writer, sheet_name='Overall Summary', index=False)
        else:
            # Create an empty sheet if no data
            pd.DataFrame().to_excel(writer, sheet_name='Overall Summary', index=False)

    def _create_company_sheet(self, data, writer):
        # Placeholder for company details sheet
        all_company_details = []
        for company_name, company_data in data.items():
            for currency, total_val in company_data.get('total_amount', {}).items():
                all_company_details.append({
                    'Company Name': company_name,
                    'Total Bonds': company_data.get('total_bonds',0),
                    'Currency': currency,
                    'Total Value in Currency': total_val,
                    'Number of Related Banks': len(company_data.get('banks',{}))
                })
        company_df = pd.DataFrame(all_company_details)
        if not company_df.empty:
            company_df.to_excel(writer, sheet_name='Company Details', index=False)
        else:
            pd.DataFrame().to_excel(writer, sheet_name='Company Details', index=False)

    def _create_bond_sheet(self, data, writer):
        # Placeholder for bond details sheet
        all_bonds = []
        for company_name, company_data in data.items():
            for bond in company_data.get('bonds', []):
                all_bonds.append({
                    'Company Name': company_name,
                    'Issue Date': bond.get('issue_date'),
                    'Maturity Date': bond.get('maturity_date'),
                    'Currency': bond.get('currency'),
                    'Amount': bond.get('amount'),
                    'Coupon Rate': bond.get('coupon_rate'),
                    'Banks': ", ".join(bond.get('banks', [])),
                })
        bond_df = pd.DataFrame(all_bonds)
        if not bond_df.empty:
            bond_df.to_excel(writer, sheet_name='Bond Details', index=False)
        else:
            pd.DataFrame().to_excel(writer, sheet_name='Bond Details', index=False)

    def _create_bank_sheet(self, data, writer):
        # Placeholder for bank relationships sheet
        all_banks_relations = []
        for company_name, company_data in data.items():
            for bank_name, count in company_data.get('banks', {}).items():
                all_banks_relations.append({
                    'Company Name': company_name,
                    'Bank Name': bank_name,
                    'Number of Bonds Involved With': count
                })
        bank_df = pd.DataFrame(all_banks_relations)
        if not bank_df.empty:
            bank_df.to_excel(writer, sheet_name='Bank Relationships', index=False)
        else:
            pd.DataFrame().to_excel(writer, sheet_name='Bank Relationships', index=False) 