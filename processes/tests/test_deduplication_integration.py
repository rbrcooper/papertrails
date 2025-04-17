import shutil
import json
import logging
from pathlib import Path
import time
import os # Added for path manipulation
from processes.esma_scraper import ESMAScraper
from processes.company_list_handler import CompanyListHandler # Import needed for path overrides

# Configure basic logging for the test
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Constants ---
TEST_DATA_DIR = Path("data/test_runtime_data")
TEST_DOWNLOAD_DIR = TEST_DATA_DIR / "downloads"
TEST_HASH_DB = TEST_DATA_DIR / "document_hashes.json"
TEST_PROCESSED_COMPANIES = TEST_DATA_DIR / "processed_companies.txt"
TEST_DOWNLOADED_DOCS = TEST_DATA_DIR / "downloaded_documents.txt"
TEST_COMPANY_STATS = TEST_DATA_DIR / "company_stats.json"

# Using a simple, stable PDF URL for testing content duplication
CONTENT_URL = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
COMPANY_A = {"name": "TestCompanyA", "country": "Germany"}
COMPANY_B = {"name": "TestCompanyB", "country": "France"}
DOC_TYPE_1 = "Prospectus"
DOC_TYPE_2 = "FinalTerms"
DATE_1 = "20240101"
DATE_2 = "20240202"

# --- Helper Functions ---
def setup_test_environment():
    """Cleans and sets up the test directories and state files."""
    logging.info("--- Setting up test environment ---")
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR)
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    TEST_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Create empty state files needed by CompanyListHandler and ESMAScraper
    for file_path in [TEST_HASH_DB, TEST_PROCESSED_COMPANIES, TEST_DOWNLOADED_DOCS, TEST_COMPANY_STATS]:
        file_path.parent.mkdir(parents=True, exist_ok=True) # Ensure parent dir exists
        if file_path.suffix == '.json':
            with open(file_path, 'w') as f:
                json.dump({}, f)
            logging.info(f"Created empty JSON state file: {file_path.absolute()}")
        else:
            file_path.touch()
            logging.info(f"Created empty text state file: {file_path.absolute()}")

    logging.info("--- Setup complete ---")

def cleanup_test_environment():
    """Reports final state but leaves files for inspection."""
    logging.info("--- Test environment cleanup (files kept for inspection) ---")
    logging.info(f"Test data directory: {TEST_DATA_DIR.absolute()}")
    logging.info("--- Cleanup reporting complete ---")


def count_files(directory: Path) -> int:
    """Counts the number of PDF files in the company subdirectories."""
    count = 0
    if not directory.is_dir():
        return 0
    for company_dir in directory.iterdir():
        if company_dir.is_dir():
            count += len(list(company_dir.glob('*.pdf')))
    return count

def get_scraper_instance() -> ESMAScraper:
    """Creates a scraper instance configured for testing with isolated state."""
    # Initialize with test download dir
    scraper = ESMAScraper(download_dir=TEST_DOWNLOAD_DIR)

    # --- Override Scraper Paths ---
    scraper.document_hashes_file = TEST_HASH_DB
    # Load the (empty or existing) test hashes
    scraper.document_hashes = scraper._load_document_hashes()

    # --- Override CompanyListHandler Paths (within the scraper's instance) ---
    handler = scraper.company_list_handler
    handler.processed_companies_file = TEST_PROCESSED_COMPANIES
    handler.downloaded_docs_file = TEST_DOWNLOADED_DOCS
    handler.company_stats_file = TEST_COMPANY_STATS
    # Reload state from the new (empty) test files
    handler.load_progress() # Reloads from TEST_PROCESSED_COMPANIES
    handler.load_downloaded_docs() # Reloads from TEST_DOWNLOADED_DOCS
    handler.load_company_stats() # Reloads from TEST_COMPANY_STATS
    # We don't need to override excel_path as we aren't loading companies in this test

    # Lower delays for faster testing
    scraper.min_delay = 0.1
    scraper.max_delay = 0.3
    return scraper

# --- Test Cases ---
def test_case_1_same_url():
    """Tests downloading the exact same URL/metadata multiple times."""
    logging.info("\n--- Test Case 1: Same URL, Multiple Attempts ---")
    setup_test_environment()
    scraper = get_scraper_instance()

    try:
        logging.info("Attempt 1 (Company A):")
        result_path1 = scraper.download_document(CONTENT_URL, COMPANY_A["name"], DOC_TYPE_1, DATE_1)
        logging.info(f"Result 1 Path: {result_path1}")
        assert result_path1 is not None, "Test Case 1 Failed: First download should succeed"
        assert result_path1.exists(), f"Test Case 1 Failed: Expected file {result_path1} does not exist"
        assert count_files(TEST_DOWNLOAD_DIR) == 1, f"Test Case 1 Failed: Should be 1 file after first download, found {count_files(TEST_DOWNLOAD_DIR)}"
        assert len(scraper.document_hashes) == 1, f"Test Case 1 Failed: Hash DB should have 1 entry, found {len(scraper.document_hashes)}"
        # Check CompanyHandler state
        assert len(scraper.company_list_handler.downloaded_docs) == 1, "Test Case 1 Failed: CompanyHandler downloaded_docs should have 1 entry"
        logging.info("Attempt 1 checks passed.")

        # Allow some time for file operations and state saving if needed
        time.sleep(1)

        logging.info("\nAttempt 2 (Company A - Same Metadata):")
        # This attempt should be caught by the company_handler's URL check
        result_path2 = scraper.download_document(CONTENT_URL, COMPANY_A["name"], DOC_TYPE_1, DATE_1)
        logging.info(f"Result 2 Path: {result_path2}")
        assert result_path2 is None, "Test Case 1 Failed: Second download attempt (same URL/meta) should be skipped (result should be None)"
        assert count_files(TEST_DOWNLOAD_DIR) == 1, f"Test Case 1 Failed: Should still be 1 file after second attempt, found {count_files(TEST_DOWNLOAD_DIR)}"
        assert len(scraper.document_hashes) == 1, f"Test Case 1 Failed: Hash DB should still have 1 entry, found {len(scraper.document_hashes)}"
        assert len(scraper.company_list_handler.downloaded_docs) == 1, "Test Case 1 Failed: CompanyHandler downloaded_docs should still have 1 entry"
        logging.info("Attempt 2 checks passed.")

        logging.info("--- Test Case 1 Passed ---")

    finally:
        scraper.close()


def test_case_2_different_metadata_same_content():
    """Tests downloading with different metadata but the same content URL."""
    logging.info("\n--- Test Case 2: Different Metadata, Same Content URL ---")
    setup_test_environment()
    scraper = get_scraper_instance()

    try:
        logging.info("Download 1 (Company A):")
        result_path1 = scraper.download_document(CONTENT_URL, COMPANY_A["name"], DOC_TYPE_1, DATE_1)
        logging.info(f"Result 1 Path: {result_path1}")
        assert result_path1 is not None, "Test Case 2 Failed: First download should succeed"
        assert result_path1.exists(), f"Test Case 2 Failed: Expected file {result_path1} does not exist"
        assert count_files(TEST_DOWNLOAD_DIR) == 1, f"Test Case 2 Failed: Should be 1 file after first download, found {count_files(TEST_DOWNLOAD_DIR)}"
        assert len(scraper.document_hashes) == 1, f"Test Case 2 Failed: Hash DB should have 1 entry, found {len(scraper.document_hashes)}"
        assert len(scraper.company_list_handler.downloaded_docs) == 1, "Test Case 2 Failed: CompanyHandler downloaded_docs should have 1 entry"
        first_file_path = result_path1
        logging.info("Download 1 checks passed.")

        time.sleep(1)

        logging.info("\nDownload 2 (Company B - Different Metadata, Same Content URL):")
        # Use different metadata so the initial company_handler URL check passes, forcing content hash check
        result_path2 = scraper.download_document(CONTENT_URL, COMPANY_B["name"], DOC_TYPE_2, DATE_2)
        logging.info(f"Result 2 Path: {result_path2}")
        # Should download temporarily, find hash collision, delete temp, return None
        # Crucially, the URL check *passed*, so the company_handler *should* mark the second doc_id as downloaded too, even though the file is rejected.
        assert result_path2 is None, "Test Case 2 Failed: Second download (same content) should be detected as duplicate and return None"
        # Wait briefly to ensure file system reflects potential deletion
        time.sleep(0.5)
        assert count_files(TEST_DOWNLOAD_DIR) == 1, f"Test Case 2 Failed: Should still be only 1 file (from first download), found {count_files(TEST_DOWNLOAD_DIR)}"
        assert len(scraper.document_hashes) == 1, f"Test Case 2 Failed: Hash DB should still have only 1 entry, found {len(scraper.document_hashes)}"
        assert len(scraper.company_list_handler.downloaded_docs) == 2, f"Test Case 2 Failed: CompanyHandler downloaded_docs should have 2 entries (both doc_ids marked)"
        # Verify the original file still exists
        assert first_file_path.exists(), f"Test Case 2 Failed: Original file {first_file_path} was deleted"
        logging.info("Download 2 checks passed.")

        logging.info("--- Test Case 2 Passed ---")

    finally:
        scraper.close()

def test_case_3_missing_file():
    """Tests behavior when the hash exists but the referenced file is gone."""
    logging.info("\n--- Test Case 3: Missing File Handling ---")
    setup_test_environment()
    scraper = get_scraper_instance()

    try:
        logging.info("Download 1 (Company A):")
        result_path1 = scraper.download_document(CONTENT_URL, COMPANY_A["name"], DOC_TYPE_1, DATE_1)
        logging.info(f"Result 1 Path: {result_path1}")
        assert result_path1 is not None, "Test Case 3 Failed: First download failed"
        assert result_path1.exists(), f"Test Case 3 Failed: File {result_path1} does not exist after download"
        assert count_files(TEST_DOWNLOAD_DIR) == 1, "Test Case 3 Failed: File count incorrect after first download"
        assert len(scraper.document_hashes) == 1, "Test Case 3 Failed: Hash count incorrect after first download"
        assert len(scraper.company_list_handler.downloaded_docs) == 1, "Test Case 3 Failed: CompanyHandler downloaded_docs incorrect after first download"
        original_hash = list(scraper.document_hashes.keys())[0]
        logging.info("Download 1 checks passed.")

        logging.info(f"\nManually deleting file: {result_path1}")
        result_path1.unlink() # Delete the actual downloaded file
        assert not result_path1.exists(), "Test Case 3 Failed: Manual deletion failed"
        # Keep the hash entry in the DB for this test

        time.sleep(1)

        logging.info("\nDownload 2 (Company B - after file deletion):")
        # Use different metadata to bypass the URL check, forcing content check
        result_path2 = scraper.download_document(CONTENT_URL, COMPANY_B["name"], DOC_TYPE_2, DATE_2)
        logging.info(f"Result 2 Path: {result_path2}")
        # is_duplicate_document should find the hash, see the file is missing, WARN, update the DB path, return False.
        # The download should proceed, and the file should be organized under Company B.
        assert result_path2 is not None, "Test Case 3 Failed: Second download should succeed after file deletion"
        assert result_path2.exists(), f"Test Case 3 Failed: File {result_path2} should exist after second download"
        # The file is now organized under Company B
        assert count_files(TEST_DOWNLOAD_DIR) == 1, f"Test Case 3 Failed: Should be 1 file total after second download, found {count_files(TEST_DOWNLOAD_DIR)}"
        assert len(scraper.document_hashes) == 1, f"Test Case 3 Failed: Hash DB should still have 1 entry, found {len(scraper.document_hashes)}"
        assert list(scraper.document_hashes.keys())[0] == original_hash, "Test Case 3 Failed: Hash key changed unexpectedly"
        # Check if the path in the hash DB was updated
        updated_path_in_db = Path(scraper.document_hashes[original_hash]["file_path"])
        assert updated_path_in_db == result_path2, f"Test Case 3 Failed: Path in hash DB ({updated_path_in_db}) not updated to new path {result_path2}"
        # The second doc_id should also be marked as downloaded
        assert len(scraper.company_list_handler.downloaded_docs) == 2, f"Test Case 3 Failed: CompanyHandler downloaded_docs should have 2 entries after second download"
        logging.info("Download 2 checks passed.")

        logging.info("--- Test Case 3 Passed ---")
    finally:
        scraper.close()

# --- Main Execution ---
if __name__ == "__main__":
    all_passed = True
    test_functions = [test_case_1_same_url, test_case_2_different_metadata_same_content, test_case_3_missing_file]
    for test_func in test_functions:
        try:
            test_func()
            logging.info(f"--- {test_func.__name__} PASSED ---")
        except AssertionError as e:
            logging.error(f"\n❌❌❌ Test Failed: {test_func.__name__} - {e} ❌❌❌")
            all_passed = False
        except Exception as e:
            logging.error(f"\n❌❌❌ Test Failed with unhandled exception: {test_func.__name__} - {e} ❌❌❌", exc_info=True)
            all_passed = False
        time.sleep(1) # Small pause between tests

    if all_passed:
        logging.info("\n✅✅✅ All Integration Tests Passed ✅✅✅")
    else:
        logging.error("\n❌❌❌ Some Integration Tests Failed ❌❌❌")

    cleanup_test_environment() 