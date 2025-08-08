#!/usr/bin/env python3
"""
Diagnostic script to examine the actual table structure on ESMA website
"""
import logging
import sys

# Add current directory to path
sys.path.append('.')

from processes.esma_scraper import ESMAScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def diagnose_table_structure():
    """Examine the actual table structure and cell content"""
    logger.info("Diagnosing table structure...")
    
    scraper = None
    try:
        scraper = ESMAScraper(debug_mode=True, headless=False)
        
        # Navigate and search
        if not scraper.navigate_to_search():
            logger.error("Navigation failed")
            return
            
        if not scraper.search_company("OMV"):
            logger.error("Search failed") 
            return
            
        # Wait and set results per page
        import time
        time.sleep(4)
        scraper.set_results_per_page(100)
        
        # Get the raw table structure
        from selenium.webdriver.common.by import By
        RESULTS_CONTAINER_ID = "resultsTable"
        RESULTS_TABLE_ID = "T01"
        
        try:
            results_container = scraper.wait.until(
                lambda d: d.find_element(By.ID, RESULTS_CONTAINER_ID)
            )
            
            try:
                results_table = results_container.find_element(By.ID, RESULTS_TABLE_ID)
            except:
                results_table = results_container
            
            rows = results_table.find_elements(By.CSS_SELECTOR, "tbody tr")
            logger.info(f"Found {len(rows)} rows")
            
            if len(rows) > 0:
                # Examine first few rows
                for i, row in enumerate(rows[:3]):
                    logger.info(f"\n--- Row {i+1} Analysis ---")
                    cells = row.find_elements(By.TAG_NAME, "td")
                    logger.info(f"Number of cells: {len(cells)}")
                    
                    for j, cell in enumerate(cells):
                        text = cell.text.strip()
                        # Check for links
                        links = cell.find_elements(By.TAG_NAME, "a")
                        link_info = ""
                        if links:
                            for link in links:
                                href = link.get_attribute('href')
                                if href:
                                    link_info += f" [Link: {href}]"
                        
                        logger.info(f"  Cell {j}: '{text}'{link_info}")
                        
                        # If text is very long, truncate for readability
                        if len(text) > 100:
                            logger.info(f"    (Full content truncated, length: {len(text)})")
                
                # Check header row for column names
                try:
                    header_row = results_table.find_element(By.CSS_SELECTOR, "thead tr")
                    header_cells = header_row.find_elements(By.TAG_NAME, "th")
                    logger.info(f"\n--- Header Analysis ---")
                    logger.info(f"Number of header cells: {len(header_cells)}")
                    for j, cell in enumerate(header_cells):
                        text = cell.text.strip()
                        logger.info(f"  Header {j}: '{text}'")
                except Exception as e:
                    logger.warning(f"Could not get header row: {e}")
            
        except Exception as e:
            logger.error(f"Error accessing table: {e}")
            
    except Exception as e:
        logger.error(f"Diagnostic failed: {e}", exc_info=True)
    finally:
        if scraper:
            scraper.close()

if __name__ == "__main__":
    diagnose_table_structure()
