"""
Test File Organizer
------------------
Tests the file organizer utility with a dry run and validates its functionality.
"""

import os
import sys
from pathlib import Path
import logging

# Add parent directory to path to allow importing from processes
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from processes.utils.file_organizer import FileOrganizer

def test_file_organizer():
    """Test the file organizer with a dry run"""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    print("=" * 80)
    print("TESTING FILE ORGANIZER (DRY RUN)")
    print("=" * 80)
    
    # Create a file organizer with dry run mode
    organizer = FileOrganizer(
        downloads_dir="data/downloads",
        log_file="logs/test_file_organizer.log",
        dry_run=True,
        max_workers=4
    )
    
    # Run the organization process in dry run mode
    stats = organizer.dry_run_organize()
    
    # Print summary
    print("\nDRY RUN SUMMARY:")
    print("-" * 40)
    print(f"Total files: {stats['total_files']}")
    print(f"Files that would be organized: {stats['organized_files']}")
    print(f"Files that would be skipped: {stats['skipped_files']}")
    print(f"Files with errors: {stats['error_files']}")
    print("-" * 40)
    
    print("\nCheck logs/test_file_organizer.log for detailed information.")
    
    # Return success
    return stats['organized_files'] > 0

def test_small_subset():
    """Test the file organizer with a small subset of files"""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    print("=" * 80)
    print("TESTING FILE ORGANIZER WITH SMALL SUBSET")
    print("=" * 80)
    
    # Create a file organizer with dry run mode
    organizer = FileOrganizer(
        downloads_dir="data/downloads",
        log_file="logs/test_subset_organizer.log",
        dry_run=True,
        max_workers=2
    )
    
    # Scan downloads directory
    all_files = organizer.scan_downloads()
    
    # Select first 5 PDF files or all if less than 5
    subset_files = all_files[:min(5, len(all_files))]
    
    # Process each file individually
    print(f"Processing {len(subset_files)} files:")
    
    for file_path in subset_files:
        print(f"\nAnalyzing: {file_path}")
        
        # Identify company
        company = organizer.identify_company(file_path)
        print(f"  Identified company: {company}")
        
        # Detect document type
        doc_type = organizer.detect_document_type(file_path)
        print(f"  Detected document type: {doc_type}")
        
        # Extract date
        date = organizer.extract_date(file_path)
        print(f"  Extracted date: {date}")
        
        # Calculate hash
        file_hash = organizer.get_file_hash(file_path)
        print(f"  File hash: {file_hash[:8]}...")
        
        # Show proposed filename
        if company:
            clean_company = company.replace("/", "_").replace("\\", "_")
            new_filename = f"{doc_type}_{date}_{file_hash[:8]}.pdf"
            print(f"  Proposed path: {clean_company}/{new_filename}")
        else:
            print(f"  Could not determine company, file would go to Unidentified/")
    
    print("\nSubset testing complete.")
    return True

if __name__ == "__main__":
    # Test file organizer with dry run
    test_file_organizer()
    print("\n")
    # Test with small subset
    test_small_subset() 