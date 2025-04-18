import argparse
import logging
import time
from pathlib import Path
from pprint import pprint
import sys

# Add project root to sys.path to allow importing from processes
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from processes.pdf_extractor import PDFExtractor
except ImportError as e:
    print(f"Error importing PDFExtractor: {e}")
    print("Ensure the script is run from the project root or the project structure is correct.")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout) # Ensure logs go to stdout
    ]
)

def collect_pdf_paths(args):
    """Collects PDF paths from command line arguments."""
    pdf_paths = []
    if args.file:
        for file_path_str in args.file:
            file_path = Path(file_path_str)
            if file_path.is_file() and file_path.suffix.lower() == '.pdf':
                pdf_paths.append(file_path)
            elif file_path.is_dir():
                 logging.warning(f"Argument '{file_path_str}' is a directory, use --dir instead. Skipping.")
            else:
                logging.warning(f"File path '{file_path_str}' is not a valid PDF file or does not exist. Skipping.")

    if args.dir:
        dir_path = Path(args.dir)
        if dir_path.is_dir():
            logging.info(f"Scanning directory: {dir_path}")
            pdf_paths.extend(list(dir_path.rglob('*.pdf'))) # Recursively find all PDFs
        else:
            logging.error(f"Directory path '{args.dir}' does not exist or is not a directory.")

    # Deduplicate paths
    unique_pdf_paths = sorted(list(set(pdf_paths)))
    logging.info(f"Found {len(unique_pdf_paths)} unique PDF files to process.")
    return unique_pdf_paths

def display_bank_extraction_results(extracted_data):
    """Display focused view of the bank extraction results"""
    print("\n" + "=" * 80)
    print(f"FILE: {extracted_data.get('filename', 'Unknown')}")
    print("=" * 80)
    
    # Display validation flags
    validation_flags = extracted_data.get('validation_flags', [])
    if validation_flags:
        print("\n🚩 VALIDATION FLAGS:")
        for flag in validation_flags:
            print(f"  - {flag}")
    
    # Display extracted bank information
    extracted_banks = extracted_data.get('extracted_banks', [])
    if extracted_banks:
        print(f"\n💰 EXTRACTED BANKS: ({len(extracted_banks)} found)")
        print("-" * 60)
        
        # Group banks by role for readability
        banks_by_role = {}
        for bank in extracted_banks:
            role = bank.get('role', 'Unknown')
            if role not in banks_by_role:
                banks_by_role[role] = []
            banks_by_role[role].append(bank)
        
        # Display banks grouped by role with confidence scores
        for role, banks in banks_by_role.items():
            print(f"\n📌 {role}:")
            for bank in banks:
                confidence = bank.get('confidence', 0)
                confidence_symbol = "✅" if confidence >= 0.8 else "⚠️" if confidence >= 0.6 else "❓"
                print(f"   {confidence_symbol} {bank.get('cleaned_name')} (conf: {confidence:.2f})")
                print(f"      Raw: \"{bank.get('raw_name')}\"")
                print(f"      Source: {bank.get('source')}")
    else:
        print("\n❌ NO BANKS EXTRACTED")
    
    # Display bank sections found
    bank_sections = extracted_data.get('bank_sections', {})
    if bank_sections:
        print("\n📄 BANK SECTIONS FOUND:")
        for section_name, section_text in bank_sections.items():
            preview = section_text[:100] + "..." if len(section_text) > 100 else section_text
            print(f"  - {section_name}: {preview}")
    else:
        print("\n❌ NO BANK SECTIONS FOUND")
    
    # Display metadata
    metadata = extracted_data.get('metadata', {})
    if metadata:
        print("\n📋 METADATA:")
        for key, value in metadata.items():
            if value:  # Only show non-empty values
                print(f"  - {key}: {value}")
    
    print("\n" + "=" * 80)

def main():
    parser = argparse.ArgumentParser(description="Test PDF Extractor on specified files or directories.")
    parser.add_argument(
        '-f', '--file',
        nargs='+',
        help="One or more paths to individual PDF files."
    )
    parser.add_argument(
        '-d', '--dir',
        help="Path to a directory containing PDF files (will be scanned recursively)."
    )
    parser.add_argument(
        '--detailed',
        action='store_true',
        help="Show full detailed extraction results"
    )

    args = parser.parse_args()

    if not args.file and not args.dir:
        parser.error("No input specified. Please provide at least one --file or --dir.")
        return

    pdf_paths = collect_pdf_paths(args)

    if not pdf_paths:
        logging.warning("No valid PDF files found to process.")
        return

    logging.info("Initializing PDFExtractor...")
    try:
        # Pass any required initialization arguments here if needed
        extractor = PDFExtractor()
    except Exception as e:
        logging.exception("Failed to initialize PDFExtractor.")
        return

    total_start_time = time.time()
    processed_count = 0
    error_count = 0

    logging.info(f"Starting processing for {len(pdf_paths)} files...")
    for pdf_path in pdf_paths:
        logging.info(f"Processing: {pdf_path}")
        file_start_time = time.time()
        try:
            extracted_data = extractor.process_single_pdf(str(pdf_path)) # Ensure path is string
            file_end_time = time.time()
            logging.info(f"Successfully processed in {file_end_time - file_start_time:.2f} seconds.")
            
            # Display results in a focused, readable format
            display_bank_extraction_results(extracted_data)
            
            # If detailed flag is set, also print the raw output
            if args.detailed:
                print("\nDETAILED RAW EXTRACTION DATA:")
                pprint(extracted_data, indent=2)
                
            processed_count += 1
        except Exception as e:
            file_end_time = time.time()
            logging.error(f"Error processing {pdf_path}: {e}", exc_info=True) # Enable full traceback for debugging
            error_count += 1
        logging.info(f"Finished processing: {pdf_path} (Duration: {file_end_time - file_start_time:.2f}s)")


    total_end_time = time.time()
    total_duration = total_end_time - total_start_time

    logging.info("=" * 30 + " Summary " + "=" * 30)
    logging.info(f"Total files processed: {processed_count}")
    logging.info(f"Total errors: {error_count}")
    logging.info(f"Total execution time: {total_duration:.2f} seconds")
    logging.info("=" * 69)


if __name__ == "__main__":
    main() 