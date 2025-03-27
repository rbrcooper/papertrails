import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Union
import finsec
import json
import pandas as pd

# Configure logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_current_quarter() -> str:
    """Get the current quarter in the format required by finsec (e.g., 'Q1-2024')."""
    now = datetime.now()
    quarter = (now.month - 1) // 3 + 1
    year = now.year
    
    # If we're in the first month of a quarter, look at the previous quarter
    # since the filing for the current quarter won't exist yet
    if now.month % 3 == 1:
        if quarter == 1:
            quarter = 4
            year -= 1
        else:
            quarter -= 1
    
    return f"Q{quarter}-{year}"

def get_previous_quarter(current_quarter: str) -> str:
    """Get the previous quarter given the current quarter."""
    quarter = int(current_quarter[1])
    year = int(current_quarter[3:])
    
    if quarter == 1:
        return f"Q4-{year-1}"
    else:
        return f"Q{quarter-1}-{year}"

class VanguardCollector:
    """Collector for Vanguard's 13F filings from SEC EDGAR using finsec."""
    
    def __init__(self):
        """Initialize the collector with Vanguard's CIK and target companies."""
        logger.debug("Initializing VanguardCollector")
        # Vanguard's CIK
        self.cik = "0000102909"  # Vanguard Group Inc
        logger.debug(f"Using CIK: {self.cik}")
        
        # Target companies to track
        self.target_companies = {
            "APPLE INC": "0000320193",  # Apple Inc
            "EXXON MOBIL CORPORATION": "0000034088"  # Exxon Mobil Corporation
        }
        logger.debug(f"Target companies: {self.target_companies}")
        
        # Initialize SEC Filing object with user agent
        self.filing = finsec.Filing(
            self.cik,
            declared_user="Company Name AdminEmail@company.com"
        )
        
        # Initial delay
        self.initial_delay = 1  # seconds
        logger.debug(f"Initial delay of {self.initial_delay} seconds")
        time.sleep(self.initial_delay)

    def get_latest_13f_filings(self) -> List[Dict]:
        """Get the latest 13F filings from Vanguard using finsec."""
        try:
            logger.debug("Fetching latest 13F filings")
            
            # Get the current and previous quarters
            current_quarter = get_current_quarter()
            prev_quarter = get_previous_quarter(current_quarter)
            logger.debug(f"Trying quarters: {current_quarter} and {prev_quarter}")
            
            # Try to get the latest filing
            try:
                # First, try to get the latest filing
                try:
                    latest_cover, latest_holdings_df, latest_info = self.filing.get_13f_filing(current_quarter)
                    logger.debug(f"Retrieved filing data for {current_quarter}")
                except Exception as e:
                    logger.warning(f"Could not get {current_quarter} filing: {str(e)}")
                    # Fall back to previous quarter
                    current_quarter = prev_quarter
                    prev_quarter = get_previous_quarter(prev_quarter)
                    logger.debug(f"Falling back to quarters: {current_quarter} and {prev_quarter}")
                    latest_cover, latest_holdings_df, latest_info = self.filing.get_13f_filing(current_quarter)
                    logger.debug(f"Retrieved filing data for {current_quarter}")
                
                # If we got here, we have the latest filing
                logger.debug(f"Latest filing info: {latest_info}")
                
                # Get the previous quarter's filing
                prev_cover, prev_holdings_df, prev_info = self.filing.get_13f_filing(prev_quarter)
                logger.debug(f"Retrieved filing data for {prev_quarter}")
                logger.debug(f"Previous filing info: {prev_info}")
                
                # Process the filings
                filings = []
                
                # Process latest filing
                if isinstance(latest_holdings_df, pd.DataFrame):
                    logger.debug(f"Latest holdings DataFrame shape: {latest_holdings_df.shape}")
                    logger.debug(f"Latest holdings columns: {latest_holdings_df.columns.tolist()}")
                    logger.debug(f"Latest holdings sample:\n{latest_holdings_df.head()}")
                    
                    holdings = latest_holdings_df.to_dict('records')
                    logger.debug(f"Found {len(holdings)} holdings for {current_quarter}")
                    
                    filings.append({
                        "filing_date": latest_cover.get("signatureDate"),
                        "holdings": holdings
                    })
                else:
                    logger.warning(f"Latest holdings not in DataFrame format: {type(latest_holdings_df)}")
                
                # Process previous filing
                if isinstance(prev_holdings_df, pd.DataFrame):
                    logger.debug(f"Previous holdings DataFrame shape: {prev_holdings_df.shape}")
                    logger.debug(f"Previous holdings columns: {prev_holdings_df.columns.tolist()}")
                    
                    holdings = prev_holdings_df.to_dict('records')
                    logger.debug(f"Found {len(holdings)} holdings for {prev_quarter}")
                    
                    filings.append({
                        "filing_date": prev_cover.get("signatureDate"),
                        "holdings": holdings
                    })
                else:
                    logger.warning(f"Previous holdings not in DataFrame format: {type(prev_holdings_df)}")
                
                logger.debug(f"Processed {len(filings)} filings")
                return filings
                
            except Exception as e:
                logger.error(f"Error getting filings: {str(e)}")
                raise
            
        except Exception as e:
            logger.error(f"Error in get_latest_13f_filings: {str(e)}", exc_info=True)
            raise

    def _filter_target_holdings(self, holdings):
        """Filter holdings to include only target companies."""
        if isinstance(holdings, list):
            holdings = pd.DataFrame(holdings)
        
        logger.debug(f"Filtering {len(holdings)} holdings")
        logger.debug(f"DataFrame columns: {holdings.columns.tolist()}")
        logger.debug(f"First row: {holdings.iloc[0].to_dict()}")
        
        # Get all unique company names
        unique_names = holdings['Name of issuer'].unique()
        logger.debug(f"All unique company names: {sorted(unique_names)}")
        
        # Define variations for our target companies
        company_variations = {
            'APPLE INC': ['APPLE INC', 'APPLE', 'APPLE COMPUTER INC', 'APPLE COMPUTER'],
            'EXXON MOBIL CORPORATION': ['EXXON MOBIL CORPORATION', 'EXXON MOBIL', 'EXXON', 'EXXONMOBIL', 'EXXON MOBIL CORP']
        }
        
        # Create a mapping of variations to canonical names
        name_mapping = {}
        for canonical, variations in company_variations.items():
            for variation in variations:
                name_mapping[variation] = canonical
        
        # Log potential matches
        logger.debug("Found companies matching our patterns:")
        for name in unique_names:
            for pattern in self.target_companies:
                if pattern in name.upper():
                    logger.debug(f"Potential match: {name} with {pattern}")
        
        # Filter holdings
        target_holdings = []
        for _, row in holdings.iterrows():
            company_name = row['Name of issuer'].strip()
            canonical_name = name_mapping.get(company_name.upper())
            
            if canonical_name:
                holding = row.to_dict()
                holding['canonicalName'] = canonical_name
                target_holdings.append(holding)
        
        logger.debug(f"Found {len(target_holdings)} target holdings")
        return target_holdings

    def collect_and_save_data(self):
        """Collect data and save to JSON file."""
        try:
            logger.debug("Starting data collection")
            # Get the latest filings
            filings = self.get_latest_13f_filings()
            
            if not filings:
                logger.error("No filings found")
                raise ValueError("No filings found")
            
            # Process each filing
            processed_filings = []
            for filing in filings:
                # Filter holdings for target companies
                holdings = self._filter_target_holdings(filing.get("holdings", []))
                processed_filing = {
                    "filing_date": filing.get("filing_date"),
                    "holdings": holdings
                }
                processed_filings.append(processed_filing)
            
            # Calculate changes between filings
            changes = self._calculate_changes(processed_filings)
            logger.debug(f"Found {len(changes)} significant changes")
            
            # Calculate portfolio metrics
            portfolio_metrics = self._calculate_portfolio_metrics(processed_filings[0]["holdings"])
            logger.debug(f"Portfolio metrics calculated: {portfolio_metrics}")
            
            # Prepare output data
            output_data = {
                "filing_date": processed_filings[0]["filing_date"],
                "portfolio_metrics": portfolio_metrics,
                "changes": changes
            }
            
            # Save to JSON file
            output_file = "vanguard_holdings.json"
            logger.debug(f"Saving data to {output_file}")
            with open(output_file, "w") as f:
                json.dump(output_data, f, indent=4)
            
            logger.info(f"Data saved to {output_file}")
            
            # Also save to Excel for easier viewing
            self.filing.filings_to_excel()
            logger.info("Data also saved to Excel")
            
        except Exception as e:
            logger.error(f"Error collecting and saving data: {str(e)}", exc_info=True)
            raise

    def _calculate_changes(self, filings):
        """Calculate changes between filings."""
        if not filings or len(filings) < 2:
            logging.debug("Not enough filings to calculate changes")
            return []

        current_holdings = {h["Name of issuer"]: h for h in filings[0]["holdings"]}
        previous_holdings = {h["Name of issuer"]: h for h in filings[1]["holdings"]}

        changes = []
        for company in self.target_companies:
            current = current_holdings.get(company)
            previous = previous_holdings.get(company)

            if current or previous:
                change = {
                    "company": company,
                    "current_shares": int(current["Share or principal amount count"]) if current else 0,
                    "previous_shares": int(previous["Share or principal amount count"]) if previous else 0,
                    "current_value": float(current["Holding value"]) if current else 0,
                    "previous_value": float(previous["Holding value"]) if previous else 0
                }
                change["share_change"] = change["current_shares"] - change["previous_shares"]
                change["value_change"] = change["current_value"] - change["previous_value"]
                changes.append(change)

        return changes

    def _calculate_portfolio_metrics(self, holdings: List[Dict]) -> Dict:
        """Calculate portfolio metrics."""
        logger.debug("Calculating portfolio metrics")
        total_value = sum(float(h.get("Holding value", 0)) for h in holdings)
        
        # Sort holdings by value
        sorted_holdings = sorted(holdings, key=lambda x: float(x.get("Holding value", 0)), reverse=True)
        
        metrics = {
            "total_positions": len(holdings),
            "total_value": total_value,
            "top_10_holdings": sorted_holdings[:10]
        }
        logger.debug(f"Portfolio metrics calculated: {metrics}")
        return metrics

def main():
    """Main function to run the collector."""
    try:
        logger.info("Starting Vanguard collector")
        collector = VanguardCollector()
        collector.collect_and_save_data()
        logger.info("Data collection completed successfully")
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main() 