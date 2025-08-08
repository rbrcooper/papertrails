from collections import defaultdict
# Assuming DatabaseHandler will be imported or passed correctly if this were part of a larger system.
# For now, we define it based on the usage in the prompt.
# from .database_handler import DatabaseHandler 

class DataAggregator:
    def __init__(self, db_handler):
        self.db = db_handler # db_handler is an instance of DatabaseHandler
        
    def aggregate_results(self, start_date=None, end_date=None):
        # Get all results from DB
        # Assumes db_handler.get_results() method exists and returns a list of dicts
        results = self.db.get_results(
            start_date=start_date,
            end_date=end_date
        )
        
        # Aggregate by company
        aggregated = defaultdict(lambda: {
            'company_name': '', # This will be set from the first result for that company
            'total_bonds': 0,
            'total_amount': defaultdict(float), # Stores amounts per currency
            'banks': defaultdict(int), # Stores count of relationships per bank
            'bonds': [] # List of individual bond details
        })
        
        if not results: # Handle case where no results are returned
            return {}

        for result in results:
            company_name = result.get('company_name')
            if not company_name:
                # Skip results without a company name or log a warning
                # For now, we skip.
                continue

            agg = aggregated[company_name]
            
            if not agg['company_name']: # Set company name if not already set
                agg['company_name'] = company_name
            
            # Update company stats
            agg['total_bonds'] += 1 # Assuming each 'result' is a bond
            
            # Currency information processing
            currency_info = result.get('currency_info')
            if currency_info and isinstance(currency_info, dict):
                currency = currency_info.get('currency')
                amount = currency_info.get('amount')
                if currency and amount is not None:
                    try:
                        agg['total_amount'][currency] += float(amount)
                    except (ValueError, TypeError):
                        # Log error or handle non-numeric amount
                        pass 
                        
            # Update bank relationships
            banks_data = result.get('banks', [])
            if isinstance(banks_data, list):
                for bank_entry in banks_data:
                    # Assuming bank_entry is a dict with 'standardized_name'
                    if isinstance(bank_entry, dict) and 'standardized_name' in bank_entry:
                        bank_name = bank_entry['standardized_name']
                        if bank_name: # Ensure bank name is not empty
                           agg['banks'][bank_name] += 1
            
            # Add bond details
            bond_detail = {
                'issue_date': result.get('issue_date'),
                'maturity_date': result.get('maturity_date'),
                'currency': None, # Default
                'amount': None, # Default
                'coupon_rate': result.get('coupon_info'), # Assuming coupon_info is the rate
                'banks': [] # Default
            }
            if currency_info and isinstance(currency_info, dict):
                bond_detail['currency'] = currency_info.get('currency')
                bond_detail['amount'] = currency_info.get('amount')

            if isinstance(banks_data, list):
                bond_detail['banks'] = [
                    b['standardized_name'] for b in banks_data 
                    if isinstance(b, dict) and 'standardized_name' in b
                ]
            
            agg['bonds'].append(bond_detail)
        
        return dict(aggregated) # Convert defaultdict to dict for the final output 