import requests
import pandas as pd
from datetime import datetime
import json
from typing import Dict, List, Optional
import logging
import os
from dotenv import load_dotenv
import time
from urllib.parse import urljoin
import re
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BlackRockCollector:
    def __init__(self):
        """Initialize the BlackRock data collector."""
        self.base_url = "https://www.sec.gov"
        self.headers = {
            'User-Agent': 'BlackRockTracker test@example.com',  # Replace with your email
            'Accept-Encoding': 'gzip, deflate, br',
            'Host': 'www.sec.gov'
        }
        self.cik = "0001364742"  # BlackRock's CIK
        self.cik_padded = self.cik.zfill(10)  # Pad to 10 digits
        self.latest_filing = None
        self.previous_filing = None

    def _make_request(self, endpoint: str, expect_json: bool = False) -> Dict:
        """
        Make a request to the SEC API with proper rate limiting.
        
        Args:
            endpoint: The API endpoint to call
            expect_json: Whether to expect a JSON response
            
        Returns:
            Dict containing the API response or raw content
        """
        url = urljoin(self.base_url, endpoint)
        try:
            # SEC requires rate limiting of 10 requests per second
            time.sleep(0.1)
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            # Log response details for debugging
            logger.info(f"Response status code: {response.status_code}")
            logger.info(f"Response headers: {response.headers}")
            logger.info(f"URL: {url}")
            
            if response.status_code == 404:
                logger.error(f"Endpoint not found: {url}")
                logger.error(f"Response content: {response.text[:500]}")
                raise ValueError(f"Endpoint not found: {url}")
                
            if response.status_code == 403:
                logger.error(f"Access forbidden: {url}")
                logger.error(f"Response content: {response.text[:500]}")
                raise ValueError(f"Access forbidden: {url}")
            
            if expect_json:
                try:
                    return response.json()
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON response: {str(e)}")
                    logger.error(f"Response content: {response.text[:500]}")
                    raise
            else:
                return {'content': response.text}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error making request to SEC API: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response content: {e.response.text[:500]}")
            raise

    def get_latest_13f_filings(self) -> Dict:
        """
        Fetch the latest and previous 13F filings from BlackRock.
        
        Returns:
            Dict containing the latest and previous filing data
        """
        try:
            # Get company submissions
            endpoint = f"/cgi-bin/browse-edgar?action=getcompany&CIK={self.cik}&type=13F-HR"
            filings_page = self._make_request(endpoint)
            
            # Parse the HTML to find filing URLs
            soup = BeautifulSoup(filings_page.get('content', ''), 'html.parser')
            
            # Find the document table
            doc_table = soup.find('table', class_='tableFile2')
            if not doc_table:
                raise ValueError("Could not find filings table")
            
            # Find all 13F-HR rows (skip amendments)
            filing_rows = []
            for row in doc_table.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 4 and cells[0].text.strip() == '13F-HR':
                    filing_rows.append(row)
            
            if len(filing_rows) < 2:
                raise ValueError("Could not find enough 13F filings")
            
            # Get the two most recent filings
            latest_row = filing_rows[0]
            previous_row = filing_rows[1]
            
            # Extract filing URLs
            latest_url = urljoin(self.base_url, latest_row.find('a', id='documentsbutton')['href'])
            previous_url = urljoin(self.base_url, previous_row.find('a', id='documentsbutton')['href'])
            
            # Get the filing data
            latest_filing = self._get_filing_data(latest_url)
            previous_filing = self._get_filing_data(previous_url)
            
            self.latest_filing = latest_filing
            self.previous_filing = previous_filing
            
            return {
                "latest": latest_filing,
                "previous": previous_filing
            }
            
        except Exception as e:
            logger.error(f"Error fetching 13F filings: {str(e)}")
            raise

    def _get_filing_data(self, filing_url: str) -> Dict:
        """
        Get the actual filing data from a filing URL.
        
        Args:
            filing_url: The URL of the filing
            
        Returns:
            Dict containing the filing data
        """
        try:
            # Get the filing page
            filing_page = self._make_request(filing_url)
            
            # Parse the HTML
            soup = BeautifulSoup(filing_page.get('content', ''), 'html.parser')
            
            # Find all links in the page
            links = soup.find_all('a')
            
            # Find the XML info table link (it ends with InfoTable.xml)
            info_table_link = None
            for link in links:
                href = link.get('href', '')
                if href.endswith('InfoTable.xml'):
                    # Remove any XSL transformation path
                    href = href.replace('xslForm13F_X02/', '')
                    info_table_link = link
                    info_table_link['href'] = href
                    break
            
            if not info_table_link:
                raise ValueError("Could not find info table XML link")
            
            # Get the info table XML URL
            info_table_url = urljoin(self.base_url, info_table_link['href'])
            logger.info(f"Info table URL: {info_table_url}")
            
            # Add headers to request raw XML
            headers = self.headers.copy()
            headers['Accept'] = 'application/xml,text/xml,*/*'
            
            # Make request with custom headers
            try:
                response = requests.get(info_table_url, headers=headers)
                response.raise_for_status()
                info_table_content = response.text
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching info table XML: {str(e)}")
                if hasattr(e.response, 'text'):
                    logger.error(f"Response content: {e.response.text[:500]}")
                raise
            
            # Parse holdings from XML
            holdings = self._parse_xml_holdings(info_table_content)
            
            # Extract filing date from the page header
            filing_date = None
            filing_date_row = soup.find('div', text=re.compile(r'Filing Date'))
            if filing_date_row:
                filing_date = filing_date_row.find_next('div').text.strip()
            
            return {
                "filing_date": filing_date,
                "holdings": holdings
            }
            
        except Exception as e:
            logger.error(f"Error getting filing data: {str(e)}")
            raise

    def _parse_xml_holdings(self, xml_content: str) -> List[Dict]:
        """
        Parse holdings data from XML content.
        
        Args:
            xml_content: The XML content to parse
            
        Returns:
            List of holdings with their details
        """
        try:
            holdings = []
            
            # Parse XML
            root = ET.fromstring(xml_content)
            
            # Define the namespace
            ns = {'ns': 'http://www.sec.gov/edgar/document/thirteenf/informationtable'}
            
            # Find all infotable entries
            for info_table in root.findall('.//ns:infoTable', ns):
                name_of_issuer = info_table.find('ns:nameOfIssuer', ns)
                value_element = info_table.find('ns:value', ns)
                shares_element = info_table.find('.//ns:sshPrnamt', ns)
                
                if name_of_issuer is not None and value_element is not None and shares_element is not None:
                    holding = {
                        "company_name": name_of_issuer.text,
                        "value": float(value_element.text.replace(',', '')),
                        "shares": int(shares_element.text.replace(',', ''))
                    }
                    holdings.append(holding)
            
            return holdings
            
        except Exception as e:
            logger.error(f"Error parsing XML holdings: {str(e)}")
            raise

    def extract_holdings_data(self, filing_data: Dict) -> List[Dict]:
        """
        Extract holdings data from a 13F filing.
        
        Args:
            filing_data: The filing data from SEC API
            
        Returns:
            List of holdings with their details
        """
        try:
            holdings = filing_data.get('holdings', [])
            
            processed_holdings = []
            for holding in holdings:
                processed_holding = {
                    "ticker": holding.get('ticker', ''),
                    "company_name": holding.get('nameOfIssuer', ''),
                    "shares": int(holding.get('shares', 0)),
                    "value": float(holding.get('value', 0)),
                    "filing_date": filing_data.get('filing_date', '')
                }
                processed_holdings.append(processed_holding)
            
            return processed_holdings
            
        except Exception as e:
            logger.error(f"Error processing holdings data: {str(e)}")
            raise

    def process_latest_quarter(self) -> Dict:
        """
        Process the latest quarter's 13F filings and calculate changes.
        
        Returns:
            Dict containing the processed data
        """
        try:
            # Get the latest filings
            filings = self.get_latest_13f_filings()
            latest_filing = filings['latest']
            previous_filing = filings['previous']
            
            # Calculate total value and prepare holdings data
            total_value = sum(holding['value'] for holding in latest_filing['holdings'])
            
            # Create a map of previous holdings for easy lookup
            previous_holdings_map = {
                holding['company_name']: holding
                for holding in previous_filing['holdings']
            }
            
            # Calculate changes
            new_positions = []
            exited_positions = []
            significant_changes = []
            
            for holding in latest_filing['holdings']:
                company_name = holding['company_name']
                if company_name not in previous_holdings_map:
                    new_positions.append({
                        'company_name': company_name,
                        'value': holding['value'],
                        'shares': holding['shares']
                    })
                else:
                    # Calculate percentage change in shares
                    prev_shares = previous_holdings_map[company_name]['shares']
                    curr_shares = holding['shares']
                    if prev_shares > 0:
                        pct_change = (curr_shares - prev_shares) / prev_shares * 100
                        if abs(pct_change) >= 25:  # 25% threshold for significant changes
                            significant_changes.append({
                                'company_name': company_name,
                                'previous_shares': prev_shares,
                                'current_shares': curr_shares,
                                'percentage_change': pct_change
                            })
            
            # Find exited positions
            for company_name in previous_holdings_map:
                if company_name not in {h['company_name'] for h in latest_filing['holdings']}:
                    prev_holding = previous_holdings_map[company_name]
                    exited_positions.append({
                        'company_name': company_name,
                        'previous_value': prev_holding['value'],
                        'previous_shares': prev_holding['shares']
                    })
            
            # Get top 10 holdings by value
            top_10_holdings = sorted(
                latest_filing['holdings'],
                key=lambda x: x['value'],
                reverse=True
            )[:10]
            
            # Prepare the output data
            output_data = {
                'filing_info': {
                    'filing_date': latest_filing['filing_date'],
                    'total_value': total_value
                },
                'holdings': latest_filing['holdings'],
                'changes': {
                    'new_positions': new_positions,
                    'exited_positions': exited_positions,
                    'significant_changes': significant_changes
                },
                'portfolio_metrics': {
                    'total_positions': len(latest_filing['holdings']),
                    'top_10_holdings': top_10_holdings,
                    'total_value': total_value
                }
            }
            
            # Save to JSON file
            with open('blackrock_holdings.json', 'w') as f:
                json.dump(output_data, f, indent=4)
            
            logger.info("Data saved to blackrock_holdings.json")
            return output_data
            
        except Exception as e:
            logger.error(f"Error processing latest quarter: {str(e)}")
            raise

def main():
    """Main function to run the data collection process."""
    try:
        collector = BlackRockCollector()
        data = collector.process_latest_quarter()
        logger.info("Data collection completed successfully")
    except Exception as e:
        logger.error(f"Error in main process: {str(e)}")
        raise

if __name__ == "__main__":
    main() 