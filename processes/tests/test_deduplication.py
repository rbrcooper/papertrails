import os
import shutil
from pathlib import Path
from processes.esma_scraper import ESMAScraper

def test_deduplication():
    """Test the hash-based deduplication functionality"""
    # Initialize scraper
    scraper = ESMAScraper(debug_mode=True)
    
    # Create test directory
    test_dir = Path("data/test_deduplication")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # Create two identical PDF files with different names
    test_file1 = test_dir / "test1.pdf"
    test_file2 = test_dir / "test2.pdf"
    
    # Create some test content
    test_content = b"This is a test PDF content for deduplication testing"
    
    # Write the same content to both files
    with open(test_file1, 'wb') as f:
        f.write(test_content)
    with open(test_file2, 'wb') as f:
        f.write(test_content)
    
    try:
        # Test 1: Check if files are detected as duplicates
        print("Test 1: Checking duplicate detection...")
        is_duplicate1 = scraper.is_duplicate_document(test_file1)
        is_duplicate2 = scraper.is_duplicate_document(test_file2)
        
        print(f"First file duplicate check: {is_duplicate1}")
        print(f"Second file duplicate check: {is_duplicate2}")
        
        if is_duplicate1 == is_duplicate2:
            print("❌ Test 1 Failed: Both files should not be duplicates on first check")
        else:
            print("✅ Test 1 Passed: First file is new, second file is detected as duplicate")
        
        # Test 2: Verify hash database
        print("\nTest 2: Checking hash database...")
        hash_count = len(scraper.document_hashes)
        print(f"Number of hashes in database: {hash_count}")
        
        if hash_count != 1:
            print("❌ Test 2 Failed: Database should contain exactly one hash")
        else:
            print("✅ Test 2 Passed: Hash database contains correct number of entries")
        
        # Test 3: Check hash persistence
        print("\nTest 3: Checking hash persistence...")
        # Create new scraper instance to test persistence
        scraper2 = ESMAScraper(debug_mode=True)
        hash_count2 = len(scraper2.document_hashes)
        print(f"Number of hashes in new scraper instance: {hash_count2}")
        
        if hash_count2 != hash_count:
            print("❌ Test 3 Failed: Hashes not persisted between scraper instances")
        else:
            print("✅ Test 3 Passed: Hashes persisted correctly")
        
        # Test 4: Check with different content
        print("\nTest 4: Checking with different content...")
        test_file3 = test_dir / "test3.pdf"
        with open(test_file3, 'wb') as f:
            f.write(b"This is different test content")
        
        is_duplicate3 = scraper.is_duplicate_document(test_file3)
        print(f"Different content file duplicate check: {is_duplicate3}")
        
        if is_duplicate3:
            print("❌ Test 4 Failed: Different content should not be detected as duplicate")
        else:
            print("✅ Test 4 Passed: Different content correctly identified as unique")
        
    finally:
        # Clean up
        print("\nCleaning up test files...")
        shutil.rmtree(test_dir)
        print("Cleanup complete")

if __name__ == "__main__":
    test_deduplication() 