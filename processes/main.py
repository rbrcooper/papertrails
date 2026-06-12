"""
ESMA Document Processing Pipeline
------------------------------
Main orchestration script that coordinates the document scraping and processing pipeline.
Manages the workflow between the ESMA scraper, PDF extractor, and company list handler.

Key Features:
- Pipeline orchestration
- Error handling and recovery
- Progress tracking
- Logging and reporting
- Batch processing management
- File organization and deduplication

Dependencies:
- esma_scraper: Web scraping functionality
- pdf_extractor: PDF processing
- company_list_handler: Company data management
- logging: Logging functionality

Usage:
python main.py [--companies-file PATH] [--output-dir PATH]

The script will:
1. Load the list of companies to process
2. Initialize the ESMA scraper
3. Download relevant documents for each company (Note: Current version modified to use local PDFs)
4. Extract and process document content
5. Save results and generate reports (Note: Reporting part is simplified for now)
"""

import logging
from pathlib import Path
import json
import time
import colorlog
import os
import argparse
import sys
from typing import Dict, List
import re

# Relative imports for running with python -m processes.main
from .pdf_extractor import PDFExtractor
from .database_handler import DatabaseHandler
from .company_list_handler import CompanyListHandler
from .esma_scraper import ESMAScraper # ESMAScraper might still be initialized, though not for active scraping

# Imports for pipeline components moved to a subfolder
from .pipeline_components.validators import (
    ExtractionValidator,
    compute_completeness_gates,
    filter_underwriter_banks,
)
from .pipeline_components.aggregation import DataAggregator
from .pipeline_components.outputs import OutputGenerator
from .pipeline_components.reporting import ValidationReporter
from .utils.decorators import log_error_with_category
from .pipeline_components.run_ledger import (
    CompanyRunRecord,
    RunLedger,
    derive_outcome,
    now_iso,
)

# Add parent directory to sys.path to allow imports when run directly
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configure colored logging (ensure 'handler' is unique if ESMAProcessor also defines one)
main_handler = colorlog.StreamHandler()
main_handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/workflow.log'),
        main_handler # Use the uniquely named handler
    ]
)

logger = logging.getLogger(__name__)


def _sanitized_download_dir(company_name: str) -> Path:
    sanitized = re.sub(r'[\\\\/:*?\"<>|]', '_', company_name)
    return Path(f"data/downloads/{sanitized}")


def _build_company_queue(company_handler, args, run_ledger: RunLedger) -> List[Dict]:
    if args.company:
        match = company_handler.get_company_by_name(args.company)
        if not match:
            logger.error("Company not found in GOGEL list: %s", args.company)
            sys.exit(1)
        return [match]

    if args.retry_failed:
        status = run_ledger.load_status()
        failed = {
            name
            for name, st in status.items()
            if st.get("outcome") and st.get("outcome") != "complete"
        }
        companies = [
            c for c in company_handler.get_all_companies()
            if c["name"] in failed and c["name"] not in company_handler.processed_companies
        ]
    else:
        companies = company_handler.get_unprocessed_companies()

    if args.limit_companies:
        companies = companies[: args.limit_companies]
    return companies


def _dry_run_preview(companies: List[Dict], run_ledger: RunLedger) -> None:
    status = run_ledger.load_status()
    logger.info("Dry run: %s companies queued", len(companies))
    for c in companies:
        name = c["name"]
        dl_dir = _sanitized_download_dir(name)
        pdf_count = len(list(dl_dir.glob("*.pdf"))) if dl_dir.is_dir() else 0
        st = status.get(name, {})
        logger.info(
            "  %s | country=%s | download_dir=%s | pdfs=%s | last_outcome=%s",
            name,
            c.get("country", ""),
            "yes" if dl_dir.is_dir() else "no",
            pdf_count,
            st.get("outcome", ""),
        )


def _placeholder_validate_extraction(extraction_result: Dict) -> Dict:
    """Placeholder validator for integration testing."""
    is_ok = bool(extraction_result.get('metadata')) # Basic check
    return {
        'is_valid': is_ok,
        'flags': ['placeholder_validation'] if not is_ok else [],
        'confidence_scores': {'overall_placeholder': 1.0 if is_ok else 0.5}
    }

def process_company_pdfs(
    company_name: str,
    pdf_dir: Path,
    pdf_extractor_instance: PDFExtractor,
    validator_instance: ExtractionValidator,
    expected_isins: List[str] = None,
    max_pdf_chars: int = 80000,
) -> List[Dict]:
    """Process all PDFs for a company using a provided PDFExtractor instance and validator."""
    # extractor = PDFExtractor() # Use passed instance
    processed_pdf_results = [] # Changed variable name for clarity
    
    if not pdf_dir.exists() or not pdf_dir.is_dir():
        logger.warning(f"PDF directory not found for {company_name} at {pdf_dir}. Skipping PDF processing.")
        return processed_pdf_results

    for pdf_file_path_obj in pdf_dir.glob('*.pdf'):
        pdf_file_path_str = str(pdf_file_path_obj)
        try:
            logger.info(f"Processing {pdf_file_path_str} for {company_name}")
            
            # Quick first-page validation check before full extraction
            quick_check = validator_instance.quick_first_page_checks(
                pdf_file_path_str,
                company_name,
                expected_isins=expected_isins or [],
                max_pdf_chars=max_pdf_chars,
            )
            
            if not quick_check.get('pass', True):
                logger.warning(f"Skipping {pdf_file_path_str} - quick check failed: {quick_check.get('reason', 'Unknown reason')}")
                processed_pdf_results.append({
                    'company_name': company_name,
                    'pdf_path': pdf_file_path_str,
                    'extraction_result': None,
                    'validation_result': {
                        'is_valid': False,
                        'quick_check_failed': True,
                        'quick_check_reason': quick_check.get('reason', 'Unknown reason'),
                        'quick_check_details': {
                            'issuer_match': quick_check.get('issuer_match'),
                            'isin_present': quick_check.get('isin_present'),
                            'guarantor_mentioned': quick_check.get('guarantor_mentioned')
                        }
                    },
                    'error': f"Quick validation failed: {quick_check.get('reason', 'Unknown reason')}"
                })
                continue
            
            # The raw extraction_result from PDFExtractor
            extraction_data = pdf_extractor_instance.process_single_pdf(
                pdf_file_path_str,
                section_only=quick_check.get('section_only', False),
            )
            
            if extraction_data is None: # Handle case where PDF processing might return None
                logger.warning(f"PDF processing returned None for {pdf_file_path_str}. Skipping validation and storage.")
                processed_pdf_results.append({
                    'company_name': company_name,
                    'pdf_path': pdf_file_path_str,
                    'extraction_result': None,
                    'validation_result': None,
                    'error': 'PDF processing returned no data'
                })
                continue

            # Use the actual ExtractionValidator
            # Passing None for llm_response_data as we are focusing on rule-based/template extraction
            validation_data = validator_instance.validate_extraction(extraction_data) # Corrected call
            
            # Structure for storing and returning, includes all parts
            # This structure can be written to the per-company JSON and also used for DB storage
            pdf_result_package = {
                'company_name': company_name,
                'pdf_path': pdf_file_path_str,
                'extraction_result': extraction_data, # The full result from PDFExtractor
                'validation_result': validation_data # The result from our placeholder validator
            }
            processed_pdf_results.append(pdf_result_package)

        except Exception as e:
            logger.error(f"FULL ERROR for {pdf_file_path_str}:", exc_info=True)
            log_error_with_category(e, f"processing PDF {pdf_file_path_str} for {company_name}", logger)
            processed_pdf_results.append({
                'company_name': company_name,
                'pdf_path': pdf_file_path_str,
                'extraction_result': None,
                'validation_result': None,
                'error': str(e)
            })
            
    return processed_pdf_results

def main():
    parser = argparse.ArgumentParser(description="ESMA document processing pipeline")
    parser.add_argument("--companies-file",
                        default=os.path.join("data", "raw", "Urgewald GOGEL 2025 V1.2 with identifiers.csv"),
                        help="Path to the GOGEL data file (.csv or .xlsx)")
    parser.add_argument("--output-dir", default="data/processed", help="Directory to save output files")
    parser.add_argument("--limit-companies", type=int, default=None, help="Limit the number of companies to process for testing")
    parser.add_argument("--skip-scraping", action='store_true', help="Skip the scraping step and use local PDFs")
    parser.add_argument("--max-workers", type=int, default=4, help="Maximum number of workers for parallel PDF processing (default: 4)")
    parser.add_argument("--region-filter", default="all",
                        help="Region filter: 'all', 'eu', or comma-separated country names (default: all)")
    parser.add_argument("--doc-policy", default="strict", choices=["strict", "balanced"],
                        help="Document tier policy for ESMA selection (default: strict)")
    parser.add_argument("--max-pdf-chars", type=int, default=80000,
                        help="Above this size, use syndicate-section-only bank extraction")
    parser.add_argument("--company", default=None, help="Process a single company by exact GOGEL name")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Queue companies with last outcome != complete (not in processed set)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print queue plan only; no scrape, extract, or DB writes")
    args = parser.parse_args()
    
    output_data_dir = Path(args.output_dir)
    output_data_dir.mkdir(parents=True, exist_ok=True)
    
    scraper = None
    pipeline_start = time.time()
    run_ledger = RunLedger()
    run_company_records: List[Dict] = []
    run_metrics = {
        "total_companies": 0, "companies_succeeded": 0, "companies_failed": 0,
        "total_pdfs_processed": 0, "pdfs_stored_successfully": 0,
        "isins_in_scope": 0, "isins_with_tier1": 0, "tier1_downloaded": 0,
        "tier1_valid_underwriter_set": 0, "eligible_for_allocation": 0, "allocated_rows": 0,
    }
    try:
        logger.info("Starting ESMA document processing pipeline")
        
        # Initialize handlers and processors
        company_handler = CompanyListHandler(args.companies_file, region_filter=args.region_filter)
        companies_to_process = _build_company_queue(company_handler, args, run_ledger)
        logger.info(f"Found {len(companies_to_process)} companies to process.")

        if args.dry_run:
            _dry_run_preview(companies_to_process, run_ledger)
            return

        # Initialize scraper only if scraping is enabled
        if not args.skip_scraping:
            # Get headless setting from environment or CLI arg (default to False for debugging)
            headless_mode = os.environ.get('HEADLESS', 'false').lower() == 'true'
            scraper = ESMAScraper(debug_mode=True, headless=headless_mode)
        db_handler = DatabaseHandler()
        pdf_extractor = PDFExtractor(debug_mode=True, max_workers=args.max_workers)
        validator = ExtractionValidator()
        aggregator = DataAggregator(db_handler)
        reporter = ValidationReporter(db_handler)
        output_gen = OutputGenerator(aggregator)

        for company in companies_to_process:
            current_company_name = company['name']
            logger.info(f"Processing company: {current_company_name}")

            run_metrics["total_companies"] += 1
            company_start = time.time()
            record = CompanyRunRecord(
                company=current_company_name,
                run_timestamp=now_iso(),
                region_filter=args.region_filter,
                doc_policy=args.doc_policy,
                skip_scraping=bool(args.skip_scraping),
            )

            bond_isins = list(dict.fromkeys(
                (company.get('isins_bonds') or []) + (company.get('isins_bonds_subsidiaries') or [])
            ))
            bond_isins_in_scope = [i for i in bond_isins if i and len(i) >= 12]
            run_metrics["isins_in_scope"] += len(bond_isins_in_scope)
            record.bond_isin_count = len(bond_isins_in_scope)

            if not args.skip_scraping:
                logger.info(f"Scraping documents for {current_company_name}")
                try:
                    downloads = scraper.search_and_process(
                        current_company_name,
                        company_data=company,
                        doc_policy=args.doc_policy,
                    )
                    tier1_isins = {d.get('isin') for d in downloads if d.get('isin')}
                    run_metrics["isins_with_tier1"] += len(tier1_isins)
                    run_metrics["tier1_downloaded"] += len(downloads)
                    record.tier1_downloaded = len(downloads)
                    logger.info(f"Downloaded {len(downloads)} documents for {current_company_name}")
                except Exception as scrape_e:
                    log_error_with_category(scrape_e, f"scraping documents for {current_company_name}", logger)
                    run_metrics["companies_failed"] += 1
                    record.outcome = "scrape_error"
                    record.skip_reason = str(scrape_e)
                    record.duration_seconds = round(time.time() - company_start, 2)
                    try:
                        run_ledger.append(record)
                        run_company_records.append({
                            "name": record.company,
                            "outcome": record.outcome,
                            "tier1_downloaded": record.tier1_downloaded,
                            "pdfs_processed": record.pdfs_processed,
                            "pdfs_stored": record.pdfs_stored,
                            "duration_seconds": record.duration_seconds,
                        })
                    except Exception as le:
                        logger.warning(f"Failed writing run ledger for {current_company_name}: {le}")
                    logger.info("Continuing to the next company.")
                    continue
            
            # Standardize the company name for directory path
            sanitized_company_name = re.sub(r'[\\\\/:*?\"<>|]', '_', current_company_name)
            company_pdf_download_dir = _sanitized_download_dir(current_company_name)
            
            # Process all PDFs for the current company
            company_pdf_processing_results = process_company_pdfs(
                current_company_name,
                company_pdf_download_dir,
                pdf_extractor,
                validator,
                expected_isins=bond_isins,
                max_pdf_chars=args.max_pdf_chars,
            )
            record.pdfs_processed = len(company_pdf_processing_results or [])
            
            # Track if at least one PDF was successfully stored in the database
            successful_db_stores = 0
            
            run_metrics["total_pdfs_processed"] += len(company_pdf_processing_results) if company_pdf_processing_results else 0

            if not company_pdf_processing_results:
                logger.info(f"No PDFs processed or found for {current_company_name} in {company_pdf_download_dir}.")
            else:
                logger.info(f"Successfully processed {len(company_pdf_processing_results)} PDF(s) for {current_company_name}.")
            
                # Store results for each PDF
                for pdf_package in company_pdf_processing_results:
                    if pdf_package.get('error'):
                        log_error_with_category(
                            Exception(pdf_package['error']), 
                            f"storing {pdf_package.get('pdf_path')}", 
                            logger
                        )
                        continue

                    extraction_data = pdf_package.get('extraction_result')
                    validation_data = pdf_package.get('validation_result')

                    if not extraction_data:
                        logger.warning(f"Skipping database storage for {pdf_package.get('pdf_path')} due to missing extraction data.")
                        continue
                    
                    # Prepare the payload for DatabaseHandler.store_extraction_result
                    banks = extraction_data.get('extracted_banks', [])
                    underwriters = filter_underwriter_banks(banks)
                    issue_size = extraction_data.get('metadata', {}).get('issue_size')
                    if 'ftws_section_not_found' in extraction_data.get('validation_flags', []):
                        completeness_status = 'underwriter_set_incomplete'
                    elif not underwriters:
                        completeness_status = 'underwriter_set_incomplete'
                    elif not issue_size:
                        completeness_status = 'amount_not_emitted'
                    else:
                        completeness_status = 'allocated_ok'
                        run_metrics['eligible_for_allocation'] += 1
                        run_metrics['allocated_rows'] += len(underwriters)
                    if underwriters:
                        run_metrics['tier1_valid_underwriter_set'] += 1

                    db_payload = {
                        'filename': Path(pdf_package['pdf_path']).name,
                        'file_path': pdf_package['pdf_path'],
                        'document_type': extraction_data.get('document_type', 'unknown'),
                        'extraction_status': 'complete' if extraction_data else 'failed',
                        'metadata': extraction_data.get('metadata', {}),
                        'extracted_banks': banks,
                        'completeness_status': completeness_status,
                    }

                    # Add validation status and confidence to metadata
                    if validation_data:
                        db_payload['metadata']['validation_status'] = 'valid' if validation_data.get('is_valid') else 'invalid'
                        db_payload['metadata']['extraction_confidence'] = validation_data.get('overall_confidence', 0.0)
                        db_payload['metadata']['validation_checks'] = validation_data.get('validation_checks', [])

                    try:
                        db_handler.store_extraction_result(
                            pdf_package['company_name'], 
                            db_payload
                        )
                        successful_db_stores += 1
                        run_metrics["pdfs_stored_successfully"] += 1
                        try:
                            company_handler.add_document_stats(
                                current_company_name,
                                extraction_data.get("document_type", "unknown"),
                                extraction_data.get("metadata", {}).get("issue_date", "") or "",
                            )
                        except Exception:
                            pass
                    except Exception as db_e:
                        log_error_with_category(db_e, f"storing extraction result for {pdf_package.get('pdf_path')}", logger)
            
                # Save per-company summary JSON
                company_summary_output_file = output_data_dir / f"{sanitized_company_name}_extraction_summary.json"
                try:
                    with open(company_summary_output_file, 'w', encoding='utf-8') as f:
                        json.dump(company_pdf_processing_results, f, indent=2, ensure_ascii=False)
                    logger.info(f"Saved extraction summary for {current_company_name} to {company_summary_output_file}")
                except Exception as json_e:
                    log_error_with_category(json_e, f"saving summary JSON for {current_company_name}", logger)

            # Mark company as processed ONLY if at least one PDF was successfully stored in DB
            record.pdfs_stored = successful_db_stores
            if successful_db_stores > 0:
                company_handler.mark_company_as_processed(current_company_name)
                run_metrics["companies_succeeded"] += 1
                record.outcome = "complete"
                logger.info(f"Finished processing and marked '{current_company_name}' as processed ({successful_db_stores} PDF(s) stored in DB).")
            else:
                run_metrics["companies_failed"] += 1
                record.outcome, record.skip_reason = derive_outcome(
                    pdfs_stored=successful_db_stores,
                    tier1_downloaded=record.tier1_downloaded,
                    skip_scraping=bool(args.skip_scraping),
                    download_dir_exists=company_pdf_download_dir.exists(),
                )
                logger.warning(f"NOT marking '{current_company_name}' as processed - no PDFs were successfully stored in database. Will retry on next run.")

            record.duration_seconds = round(time.time() - company_start, 2)
            try:
                run_ledger.append(record)
                run_company_records.append({
                    "name": record.company,
                    "outcome": record.outcome,
                    "tier1_downloaded": record.tier1_downloaded,
                    "pdfs_processed": record.pdfs_processed,
                    "pdfs_stored": record.pdfs_stored,
                    "duration_seconds": record.duration_seconds,
                })
            except Exception as le:
                logger.warning(f"Failed writing run ledger for {current_company_name}: {le}")

        # Aggregation, Reporting, and Output Generation (after all companies are processed)
        logger.info("Attempting final aggregation, reporting, and output generation for all processed companies...")
        try:
            aggregated_data = aggregator.aggregate_results()
            if not aggregated_data:
                logger.warning("Aggregated data is empty. Skipping report generation.")
            else:
                logger.info(f"Aggregated data successfully. Number of companies aggregated: {len(aggregated_data)}")
                
                validation_summary_report = reporter.generate_validation_report()
                logger.info(f"Validation report generated. Report type: {type(validation_summary_report)}")
                
                # Generate a single combined Excel report
                excel_output_path = output_data_dir / "master_detailed_report.xlsx"
                logger.info(f"Generating combined Excel report to: {excel_output_path}")
                output_gen.generate_excel(str(excel_output_path))

                logger.info("Final output generation complete.")

        except Exception as e:
            log_error_with_category(e, "final aggregation/reporting/output generation", logger)

        logger.info("Pipeline completed for all companies.")

    except Exception as e:
        log_error_with_category(e, "main pipeline execution", logger)
    finally:
        # Write run metrics
        run_metrics["pipeline_duration_seconds"] = round(time.time() - pipeline_start, 1)
        run_metrics["run_timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        outcome_counts: Dict[str, int] = {}
        for row in run_company_records:
            outcome_counts[row["outcome"]] = outcome_counts.get(row["outcome"], 0) + 1
        run_metrics["cli_args"] = {
            "region_filter": getattr(args, "region_filter", "all"),
            "limit_companies": getattr(args, "limit_companies", None),
            "skip_scraping": bool(getattr(args, "skip_scraping", False)),
            "doc_policy": getattr(args, "doc_policy", "strict"),
            "company": getattr(args, "company", None),
            "retry_failed": bool(getattr(args, "retry_failed", False)),
            "dry_run": bool(getattr(args, "dry_run", False)),
        }
        run_metrics["outcome_counts"] = outcome_counts
        run_metrics["companies"] = run_company_records
        run_metrics["ledger_path"] = str(run_ledger.ledger_path)
        gate_report = compute_completeness_gates(run_metrics)
        run_metrics["completeness_gates"] = gate_report["gates"]
        run_metrics["completeness_ship"] = gate_report["ship"]
        metrics_path = Path("logs/run_metrics.json")
        gates_path = Path("logs/completeness_gates.json")
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(metrics_path, 'w') as f:
                json.dump(run_metrics, f, indent=2)
            with open(gates_path, 'w') as f:
                json.dump(gate_report, f, indent=2)
            logger.info(f"Run metrics saved to {metrics_path}")
            logger.info(f"Completeness gates saved to {gates_path} (ship={gate_report['ship']})")
        except Exception as me:
            logger.error(f"Failed to write run metrics: {me}")

        if scraper:
            scraper.close()

if __name__ == "__main__":
    main() 