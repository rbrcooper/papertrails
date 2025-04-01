import logging
from pathlib import Path
import sys
from datetime import datetime
import traceback

from workflow import ESMAWorkflow
from utils.helpers import setup_logging

def main():
    # Set up logging
    logger = setup_logging(__name__)
    logger.info("Starting ESMA workflow")
    
    try:
        # Initialize and run workflow
        workflow = ESMAWorkflow()
        workflow.initialize()
        
        # Process each company
        for company_name, company_data in workflow.companies.items():
            try:
                logger.info(f"Processing company: {company_name}")
                result = workflow.process_company(company_name, company_data)
                if result["success"]:
                    logger.info(f"Successfully processed company: {company_name} - Found {result['bond_count']} bonds")
                else:
                    logger.error(f"Failed to process company {company_name}: {result.get('error', 'Unknown error')}")
            except Exception as e:
                logger.error(f"Error processing company {company_name}: {str(e)}")
                logger.error(traceback.format_exc())
                continue
        
        # Generate final reports
        workflow.generate_reports()
        
        logger.info("ESMA workflow completed successfully")
        
    except Exception as e:
        logger.error(f"ESMA workflow failed: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        if hasattr(workflow, 'driver') and workflow.driver:
            workflow.driver.quit()

if __name__ == "__main__":
    main() 