#!/usr/bin/env python
"""
PDF Extraction Test Script
-------------------------
Tests the PDF extractor on individual files or directories of PDFs
without running the full web scraper pipeline.

Usage:
    python scripts/test_extractor.py path/to/file.pdf
    python scripts/test_extractor.py --dir path/to/dir
    python scripts/test_extractor.py --dir path/to/dir --output results.json
    python scripts/test_extractor.py --company "Company Name"
"""

import argparse
import json
import logging
import time
from pathlib import Path
import pprint
import sys
from typing import List, Dict, Optional, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the PDF extractor
from processes.pdf_extractor import PDFExtractor


def setup_logging():
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/test_extractor.log')
        ]
    )
    return logging.getLogger(__name__)


def find_pdfs(path: Path, company_filter: Optional[str] = None) -> List[Path]:
    """
    Find PDF files in the given path.
    
    Args:
        path: Path to search in (file or directory)
        company_filter: Optional company name to filter by
        
    Returns:
        List of PDF file paths
    """
    pdf_files = []
    
    if path.is_file() and path.suffix.lower() == '.pdf':
        pdf_files.append(path)
    elif path.is_dir():
        # If company_filter is provided, look only in that company's directory
        if company_filter and (path / company_filter).exists():
            pdf_files.extend((path / company_filter).glob('**/*.pdf'))
        else:
            pdf_files.extend(path.glob('**/*.pdf'))
    
    return pdf_files


def process_pdfs(pdf_paths: List[Path], output_file: Optional[str] = None, logger=None) -> List[Dict]:
    """
    Process a list of PDF files using the PDFExtractor.
    
    Args:
        pdf_paths: List of PDF file paths to process
        output_file: Optional path to save results as JSON
        logger: Logger instance
        
    Returns:
        List of extraction results
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    extractor = PDFExtractor()
    results = []
    
    total_start_time = time.time()
    
    for i, pdf_path in enumerate(pdf_paths):
        logger.info(f"Processing [{i+1}/{len(pdf_paths)}]: {pdf_path}")
        
        try:
            # Time the extraction
            start_time = time.time()
            result = extractor.process_single_pdf(str(pdf_path))
            elapsed = time.time() - start_time
            
            # Add timing information
            result['processing_time'] = elapsed
            
            logger.info(f"Extracted data from {pdf_path.name} in {elapsed:.2f} seconds")
            logger.info(f"Found {len(result.get('extracted_banks', []))} banks")
            logger.info(f"Metadata: {result.get('metadata', {})}")
            logger.info(f"Validation flags: {result.get('validation_flags', [])}")
            
            # Print detailed results
            if logger.level <= logging.DEBUG:
                logger.debug("Detailed extraction results:")
                logger.debug(pprint.pformat(result, indent=2))
            
            results.append(result)
            
        except Exception as e:
            logger.error(f"Error processing {pdf_path}: {str(e)}", exc_info=True)
            results.append({
                'filename': pdf_path.name,
                'file_path': str(pdf_path),
                'error': str(e),
                'success': False
            })
    
    total_elapsed = time.time() - total_start_time
    logger.info(f"Processed {len(pdf_paths)} PDFs in {total_elapsed:.2f} seconds")
    logger.info(f"Average time per PDF: {total_elapsed/len(pdf_paths):.2f} seconds")
    
    # Save results to file if specified
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logger.info(f"Results saved to {output_path}")
    
    return results


def main():
    """Main function for the test script."""
    parser = argparse.ArgumentParser(description='Test PDF extractor on files or directories')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('pdf_path', nargs='?', help='Path to a PDF file to process')
    group.add_argument('--dir', help='Directory containing PDFs to process')
    parser.add_argument('--output', help='Path to save extraction results as JSON')
    parser.add_argument('--company', help='Filter PDFs by company name')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    
    # Set up logging
    logger = setup_logging()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Create logs directory if it doesn't exist
    Path('logs').mkdir(exist_ok=True)
    
    # Determine the path to search for PDFs
    if args.pdf_path:
        search_path = Path(args.pdf_path)
    else:
        search_path = Path(args.dir)
    
    # Default to data/downloads if no path specified
    if not search_path.exists() and not args.pdf_path and not args.dir:
        search_path = Path('data/downloads')
        logger.info(f"No path specified, using default: {search_path}")
    
    # Find PDFs to process
    pdf_paths = find_pdfs(search_path, args.company)
    
    if not pdf_paths:
        logger.error(f"No PDF files found at {search_path}")
        return
    
    logger.info(f"Found {len(pdf_paths)} PDF files to process")
    
    # Process the PDFs
    process_pdfs(pdf_paths, args.output, logger)


if __name__ == '__main__':
    main() 