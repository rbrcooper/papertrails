# AI Task Prompts for ESMA Prospectus Scraper

This document contains specific prompts for AI assistants to help with implementing the roadmap tasks. Each prompt provides comprehensive context about the project and specific instructions for the task at hand.

For best results, use **Claude 3.5 Sonnet** in Cursor as it provides the most accurate code generation with proper context handling.

---

## File Organization Tasks

### Prompt 1: Organize Downloaded Files -- DONE

```
# TASK: Create File Organizer Utility

## PROJECT CONTEXT
I'm working on an ESMA Prospectus Scraper project that downloads and processes PDF documents from the European Securities and Markets Authority website. The project extracts bank/underwriter information from these documents for fossil fuel financing tracking.

The current project structure is:
- data/downloads/ - Contains downloaded PDFs (chaotic, some at root, some in folders)
- processes/esma_scraper.py - Handles downloading from ESMA
- processes/pdf_extractor.py - Extracts data from PDFs
- processes/company_list_handler.py - Manages company information
- logs/ - Contains log files and progress tracking

## CURRENT PROBLEM
The downloads folder is disorganized with:
1. Some files at root level and others in company folders
2. Inconsistent naming across files
3. Duplicate files with slightly different names
4. No clear way to identify document types from filenames

## SPECIFIC TASK
Create a utility script (processes/utils/file_organizer.py) that will:
1. Move loose PDFs into appropriate company folders
2. Implement a consistent naming scheme: {company_name}/{document_type}_{date}_{hash}.pdf
3. Avoid duplicating files that already exist (check by content hash)
4. Log all file operations for auditing

## IMPLEMENTATION DETAILS
- Use the CompanyListHandler class to get company information
- Add functionality to detect document type from file content
- Calculate SHA-256 hash of file content for deduplication
- Create a main function that can be run independently or imported
- Make the script idempotent (can be run multiple times safely)

## TESTING AND DEBUGGING
1. Start with a dry-run mode that only prints intended file operations
2. Test with a small subset of files first
3. Verify proper company name matching logic
4. Test deduplication with identical files having different names
5. Implement proper error handling for all file operations
6. Add detailed logging of each step for debugging

Create this utility while respecting the existing code organization and file handling patterns.
```

---

### Prompt 2: Implement Hash-Based Deduplication

```
# TASK: Add Document Deduplication to Scraper

## PROJECT CONTEXT
I'm enhancing my ESMA Prospectus Scraper to avoid downloading duplicate documents. The scraper downloads prospectus documents from the European Securities and Markets Authority website and is used to track fossil fuel financing through underwriter information.

## CURRENT CODE STRUCTURE
- processes/esma_scraper.py contains the ESMAScraper class that handles downloading
- The download_document() method in ESMAScraper saves files to data/downloads/
- company_list_handler.py contains a method is_document_downloaded() but it only checks URLs, not content

## SPECIFIC TASK
Add hash-based deduplication to the ESMAScraper class that:
1. Checks if a document with the same content already exists before downloading
2. Uses file hashing (SHA-256) to compare documents
3. Integrates with the existing download workflow
4. Updates the download tracking system

## IMPLEMENTATION DETAILS
1. Create a new method is_duplicate_document() that:
   - Calculates SHA-256 hash of the downloaded file
   - Maintains a JSON database of document hashes at data/document_hashes.json
   - Returns True if hash already exists in database
2. Modify the download_document() method to use this check
3. Update the company_list_handler.py file to store document hashes
4. Make sure temporary/partial downloads are handled correctly

## TESTING AND DEBUGGING
1. Test with known duplicate documents with different names
2. Verify hash calculation is consistent
3. Test edge cases like empty files or corrupted PDFs
4. Confirm integration with existing download tracking system
5. Validate performance with a large number of files
6. Add detailed logging to trace the deduplication process

Please extend the ESMAScraper class with this functionality, maintaining compatibility with the existing code. Test iteratively until the deduplication works reliably.
```

---

## Scraper Enhancement Tasks

### Prompt 3: Improve ESMA Scraper Interaction Stability


# TASK: Improve ESMA Scraper Interaction Stability

## PROJECT CONTEXT
I'm working on an ESMA Prospectus Scraper project that downloads and processes PDF documents from the European Securities and Markets Authority website (https://registers.esma.europa.eu/publication/searchRegister?core=esma_registers_priii_documents). The project extracts bank/underwriter information for fossil fuel financing tracking. The core scraping logic resides in `processes/esma_scraper.py` using Selenium with `undetected-chromedriver`.

## CURRENT PROBLEM
The scraper's interactions with the ESMA website are sometimes unreliable due to:
1.  **Brittle Selectors:** Using CSS selectors or XPaths that are prone to breaking if the website's UI changes slightly (e.g., relying on generated IDs, unstable classes, or element order).
2.  **Insufficient Waits:** Over-reliance on fixed `time.sleep()` or inadequate `WebDriverWait` conditions, leading to race conditions where the script tries to interact with elements before they are fully loaded, visible, or clickable.
3.  **Poor Error Diagnosis:** When an interaction fails (e.g., `NoSuchElementException`, `TimeoutException`), the current logging might not provide enough context (like a screenshot or page source at the time of failure) to easily diagnose the issue.
4.  **Risk of Breaking Changes:** Previous attempts to modify interactions without fully understanding the surrounding logic or website behavior have sometimes broken the script's functionality.

## SPECIFIC TASK
Review and refactor the Selenium interaction points within the `ESMAScraper` class (`processes/esma_scraper.py`) to improve stability and robustness. **Operate conservatively**: the primary goal is to make the *existing* navigation and interaction steps *more reliable*, not to change the overall workflow or add new features in this task. Understand the context of each interaction before modifying it. We have been blocked by capcha before so be aware that that is still a risk

Specifically:
1.  Identify all Selenium actions (`find_element`, `find_elements`, `.click()`, `.send_keys()`, etc.).
2.  Replace brittle selectors with more robust alternatives (prioritizing stable IDs, names, `data-*` attributes, or reliable structural XPaths/CSS selectors).
3.  Replace all fixed `time.sleep()` calls used for waiting for page elements with explicit `WebDriverWait` conditions (`EC.element_to_be_clickable`, `EC.visibility_of_element_located`, `EC.presence_of_element_located`, etc.), using appropriate timeouts.
4.  Wrap critical interactions in `try...except` blocks catching specific Selenium exceptions (`NoSuchElementException`, `TimeoutException`, `StaleElementReferenceException`, `ElementClickInterceptedException`, `ElementNotInteractableException`).
5.  Within these exception blocks, integrate calls to the existing debug helpers (`self.take_screenshot()`, `self.save_page_source()`) to capture the state of the page *at the moment of failure*, using informative filenames (e.g., `error_clicking_search_button_TIMESTAMP`).

## IMPLEMENTATION DETAILS
-   **Target Methods:** Focus review on methods heavily involved in browser interaction, including (but not limited to): `setup_driver`, `navigate_to_search`, `accept_cookies`, `set_results_per_page`, `set_document_type_filter`, `search_company`, `process_results`, `get_document_details`, `_find_element_sequentially`.
-   **Selector Strategy:** Prefer `By.ID` (if stable), `By.NAME`, `By.CSS_SELECTOR` targeting `data-*` attributes or stable class/attribute combinations. Use `By.XPATH` when necessary for complex relationships but ensure they are not overly reliant on specific indexing.
-   **Wait Conditions:** Use the most appropriate `ExpectedCondition` from `selenium.webdriver.support.expected_conditions`. Ensure waits are applied *before* interaction attempts.
-   **Conservative Approach:** **Crucially, focus only on improving the stability and error handling of existing interactions.** Do not add significant new logic, change the sequence of operations, or implement new features (like the 100 results/page or document type filtering *logic* itself - just make the *current interaction attempts* more stable). Verify that any change doesn't inadvertently alter the intended behavior.

## TESTING AND DEBUGGING
1.  After refactoring, run the scraper for a few known companies that previously worked and some that might have caused issues.
2.  Monitor logs for a *reduction* in Selenium exceptions (`TimeoutException`, `NoSuchElementException`, etc.).
3.  Verify that the scraper still successfully navigates, searches, and processes results.
4.  If possible, temporarily modify a selector to be invalid and trigger an exception handler to ensure the screenshot/page source capture is working correctly within the `except` block.
5.  Run the process multiple times to check for consistency.
```

---

---

### Prompt 5: Add Document Type Filtering

```
# TASK: Implement Reliable Document Type Filtering

## PROJECT CONTEXT
My ESMA Prospectus Scraper needs to filter for specific document types at the search level to improve efficiency. The current implementation filters documents after receiving search results, which wastes bandwidth and processing time.

## CURRENT CODE STRUCTURE
- processes/esma_scraper.py contains the ESMAScraper class
- The set_document_type_filter() method (around line 348) attempts to set a document type filter
- The current process searches for all documents then filters the results programmatically

## CURRENT METHOD (Outline)
```python
def set_document_type_filter(self, doc_type="Base prospectus with Final terms"):
    """Set document type filter in the search form"""
    try:
        # Current implementation is unreliable
        # Attempts to interact with document type filter in UI
    except Exception as e:
        self.logger.error(f"Error setting document type filter: {str(e)}")
```

## SPECIFIC TASK
Enhance the set_document_type_filter() method to:
1. Reliably filter for "Base prospectus with Final terms" at the search form level
2. Handle the actual form elements on the ESMA website correctly
3. Verify the filter was successfully applied
4. Fall back gracefully if the UI changes or elements aren't found

## IMPLEMENTATION DETAILS
1. The document type field is likely a dropdown or multiple selection element
2. You may need to use complex selector chains to find the right elements
3. Consider using JavaScript execution for direct form manipulation
4. Implement a verification step that confirms the filter is active
5. Add detailed error capturing and logging

## TESTING AND DEBUGGING
1. Take screenshots before and after applying the filter
2. Save page HTML at various stages to analyze in case of failure
3. Implement tests with different document types
4. Verify that search results actually contain only the filtered type
5. Test with deliberately slow network connections
6. Add retry logic with exponential backoff for reliability

Please update this method in the ESMAScraper class while maintaining compatibility with the existing code. Test iteratively until the filtering works reliably across multiple runs.
```

---

## PDF Extraction Tasks

### Prompt 6: Create Bank Name Standardization

```
# TASK: Develop Bank Name Standardization Utility

## PROJECT CONTEXT
My ESMA Prospectus Scraper extracts bank/underwriter information from PDFs for fossil fuel financing tracking. Currently, the same banks appear under different names across documents (e.g., "BNP Paribas SA", "BNP", "BNP Paribas Securities"), making analysis difficult.

## CURRENT CODE STRUCTURE
- processes/pdf_extractor.py handles PDF data extraction
- The extract_bank_info() method finds banks but doesn't standardize names
- There's a clean_bank_name() method that does basic cleaning but not standardization

## SPECIFIC TASK
Create a new utility (processes/utils/bank_standardizer.py) that:
1. Maintains a database of known bank names and their variations
2. Maps extracted bank names to their standardized forms
3. Handles common variations like abbreviations, legal entity types, etc.
4. Provides confidence scoring for matches

## IMPLEMENTATION DETAILS
1. Create a JSON file data/bank_names.json with mappings like:
   ```json
   {
     "bnp paribas": {
       "standard_name": "BNP Paribas",
       "aliases": ["bnp", "bnp paribas sa", "bnp paribas securities"]
     },
     // More banks...
   }
   ```
2. Implement fuzzy matching with a threshold for uncertain matches
3. Handle bank name prefixes/suffixes (SA, AG, Ltd, GmbH, etc.)
4. Provide a method to suggest additions to the database
5. Create functionality to merge results from different extraction methods

## TESTING AND DEBUGGING
1. Create unit tests with known bank name variations
2. Test with actual extraction results from different documents
3. Measure standardization accuracy on a test set
4. Implement logging of all standardization decisions
5. Add functionality to manually review uncertain matches
6. Test edge cases like very short names or highly ambiguous names

Please create this utility with a focus on accuracy and extensibility. Test it against a diverse set of extracted bank names to ensure it properly standardizes the data.
```

---

### Prompt 7: Implement Multi-Stage Extraction

```
# TASK: Implement Multi-Stage PDF Extraction

## PROJECT CONTEXT
My ESMA Prospectus Scraper extracts bank/underwriter information from prospectus PDFs. Currently, the extractor primarily looks for the "Distribution" section, but this approach fails with documents that use different formats or have poor text extraction quality.

## CURRENT CODE STRUCTURE
- processes/pdf_extractor.py contains the PDFExtractor class
- The extract_bank_info() method attempts to find bank information in the "Distribution" section
- There's a find_section() method that locates specific sections in the document
- The extract_text() method handles PDF text extraction

## CURRENT LIMITATIONS
1. Relies too heavily on finding specific section titles
2. No fallback if primary extraction method fails
3. Limited handling of different document structures
4. Doesn't compare results from different methods

## SPECIFIC TASK
Enhance the PDFExtractor class to implement a multi-stage extraction approach:
1. Try section-based extraction first (looking for Distribution, Placement, etc.)
2. Fall back to pattern matching throughout the document if section extraction fails
3. Consider OCR for scanned documents if needed
4. Compare and reconcile results from different methods
5. Assign confidence scores to extraction results

## IMPLEMENTATION DETAILS
1. Create a new extract_with_fallbacks() method that:
   - Tries each method in sequence
   - Combines results with confidence scoring
   - Returns the best results with metadata about the method used
2. Enhance pattern matching with more comprehensive bank name patterns
3. Implement contextual extraction that looks at text around potential bank names
4. Add OCR support for documents with poor text extraction
5. Create a reconciliation system to merge results from different methods

## TESTING AND DEBUGGING
1. Test with a diverse set of PDF documents with known information
2. Create a test suite with documents that use different formats
3. Measure extraction accuracy before and after enhancements
4. Implement logging that shows which extraction method succeeded
5. Add visualization of extraction results for debugging
6. Test with deliberately challenging documents

Please enhance the PDFExtractor class with this multi-stage approach while maintaining its current interface. Test iteratively with various document types until the extraction is significantly more reliable.
```

---

### Prompt 8: Create Extraction Validation Rules

```
# TASK: Implement PDF Extraction Validation Rules

## PROJECT CONTEXT
My ESMA Prospectus Scraper extracts bank/underwriter information from PDFs, but currently has limited validation of the extracted data, leading to potential inaccuracies in the dataset.

## CURRENT CODE STRUCTURE
- processes/pdf_extractor.py contains the PDFExtractor class
- The extract_bank_info() method extracts bank information
- There's no systematic validation of extraction results

## SPECIFIC TASK
Create a validation system within the PDFExtractor class that:
1. Checks extracted bank names against a reference list
2. Validates the roles assigned to banks (manager, underwriter, etc.)
3. Ensures the extraction results follow the expected structure
4. Provides confidence scores for the extraction
5. Flags potentially problematic or incomplete extractions

## IMPLEMENTATION DETAILS
1. Create a new validate_extraction() method that:
   - Takes extraction results as input
   - Performs various validation checks
   - Returns validated results with confidence scores and flags
2. Implement the following validation rules:
   - Bank names should match known banks or be flagged as uncertain
   - Each role should be one of the expected types
   - Certain document types should have specific roles present
   - Results should have a minimum number of banks for specific document types
   - Cross-reference information across different sections
3. Add a data structure to store validation results alongside extraction data

## TESTING AND DEBUGGING
1. Create a test suite with documents of known content
2. Test with both well-formed and problematic documents
3. Create edge cases to test each validation rule
4. Implement detailed logging of validation failures
5. Add a manual review system for flagged extractions
6. Track validation accuracy over time

Please integrate this validation system into the PDFExtractor class without breaking the existing workflow. Test iteratively against a variety of documents until the validation provides reliable quality assurance.
```

---

## Storage & Integration Tasks

### Prompt 9: Create SQLite Database Schema

```
# TASK: Implement SQLite Database for Extracted Data

## PROJECT CONTEXT
My ESMA Prospectus Scraper extracts bank/underwriter information from prospectus PDFs. Currently, results are saved as individual JSON files, making analysis and querying difficult.

## CURRENT CODE STRUCTURE
- processes/pdf_extractor.py extracts data from PDFs
- Results are saved as JSON files in data/output/
- No central database exists for the extracted information

## SPECIFIC TASK
Create a database handler (processes/utils/database_handler.py) that:
1. Defines a SQLite schema for storing:
   - Company information (name, country, identifiers)
   - Document metadata (date, type, URL, filename)
   - Extracted bank information and their roles
   - Extraction metadata (confidence, method used)
2. Provides methods for storing and retrieving data
3. Ensures proper indexing for efficient queries
4. Handles data validation and error conditions

## IMPLEMENTATION DETAILS
1. Create a SQLite database at data/extracted_data.db
2. Implement the following tables:
   - companies (id, name, country, identifier)
   - documents (id, company_id, doc_type, date, url, filename, hash)
   - banks (id, name, standardized_name)
   - roles (id, name, description)
   - document_banks (id, document_id, bank_id, role_id, confidence)
   - extraction_metadata (id, document_id, extraction_method, timestamp, success)
3. Create the following methods:
   - initialize_database(): Create tables if they don't exist
   - add_company(name, country, identifier): Add/get company
   - add_document(company_id, doc_info): Add document with metadata
   - add_extraction_result(document_id, results): Add extraction results
   - get_companies(): Get all companies
   - get_documents_by_company(company_id): Get documents for company
   - get_banks_by_document(document_id): Get banks for document
   - get_banks_by_company(company_id): Get all banks for a company's documents

## TESTING AND DEBUGGING
1. Create unit tests for each database operation
2. Test with sample data from actual extractions
3. Verify data integrity constraints
4. Test concurrent access scenarios
5. Implement transaction handling for reliability
6. Add migration functionality for schema updates

Please create this database handler with a focus on data integrity and query efficiency. Test it thoroughly with realistic data to ensure it properly stores and retrieves the extraction results.
```

---

### Prompt 10: Create Progress Dashboard

```
# TASK: Create Scraping Progress Dashboard

## PROJECT CONTEXT
My ESMA Prospectus Scraper processes prospectus documents from hundreds of companies. Currently, progress is only tracked in log files and company_progress.json, making it difficult to visualize overall status.

## CURRENT CODE STRUCTURE
- logs/company_progress.json contains basic progress information
- processes/main.py updates progress as companies are processed
- No visualization of progress currently exists

## SPECIFIC TASK
Create a utility (processes/utils/dashboard_generator.py) that:
1. Reads progress data from company_progress.json and log files
2. Generates a simple HTML dashboard showing:
   - Overall progress (companies processed/total)
   - Success rates for downloading and extraction
   - Recent activity and errors
   - Per-company statistics
3. Updates the dashboard periodically
4. Provides filtering and sorting options

## IMPLEMENTATION DETAILS
1. Create a function generate_dashboard() that:
   - Reads progress data from logs/company_progress.json
   - Reads recent log entries for activity information
   - Generates an HTML file with Bootstrap styling at dashboard/index.html
2. Include the following sections in the dashboard:
   - Summary statistics (total companies, processed, success rate)
   - Progress bar for overall completion
   - Table of recently processed companies with status
   - List of recent errors with details
   - Charts for success/failure rates by document type
3. Add auto-refresh functionality to the HTML
4. Create a background process that updates the dashboard every 5 minutes

## TESTING AND DEBUGGING
1. Test with sample progress data of varying completeness
2. Verify dashboard renders correctly in different browsers
3. Test with large datasets to ensure performance
4. Implement error handling for malformed progress data
5. Add logging of dashboard generation process
6. Create a development mode with more detailed information

Please create this dashboard utility with a focus on clarity and usability. Test it with realistic progress data to ensure it provides accurate and helpful insights into the scraping process.
```

---

### Prompt 11: Unified Entry Point

```
# TASK: Refine Main Process Orchestration

## PROJECT CONTEXT
My ESMA Prospectus Scraper consists of several components (scraper, extractor, company handler) that need better integration. Currently, main.py is basic and doesn't provide robust orchestration.

## CURRENT CODE STRUCTURE
- processes/main.py is the current entry point
- It initializes components and processes companies sequentially
- Limited error handling and no checkpointing
- No batch processing or progress resumption

## CURRENT LIMITATIONS
1. No ability to resume interrupted runs
2. Processes one company at a time without batching
3. Limited error recovery
4. No coordination between scraping and extraction
5. Basic logging without detailed progress tracking

## SPECIFIC TASK
Refine the main entry point (processes/main.py) to:
1. Process companies in configurable batches
2. Implement proper checkpointing for resuming interrupted runs
3. Coordinate between scraping, PDF extraction, and data storage
4. Provide comprehensive logging and error handling
5. Add command-line arguments for flexible execution

## IMPLEMENTATION DETAILS
1. Update the main() function to:
   - Accept command-line arguments using argparse
   - Support batch processing with configurable size
   - Implement checkpointing after each batch
   - Add proper exception handling with recovery
   - Integrate with the database handler for storage
2. Add the following command-line options:
   - --batch-size: Number of companies to process in a batch
   - --resume: Resume from last checkpoint
   - --companies-file: Custom path to companies file
   - --mode: 'scrape', 'extract', or 'full' for partial runs
   - --debug: Enable debug logging
3. Implement a State class to track and persist execution state

## TESTING AND DEBUGGING
1. Test with small batches to verify checkpointing
2. Simulate interruptions to test resumption
3. Test each execution mode separately
4. Verify error handling with deliberate failures
5. Test command-line argument parsing
6. Monitor resource usage during execution

Please update main.py to provide this improved orchestration while maintaining compatibility with existing components. Test iteratively with realistic scenarios until the process runs reliably with proper resumption and error handling.
``` 