# AI Task Prompts: ESMA Bond Data Tracker MVP

This document guides AI assistance for achieving the Minimum Viable Product (MVP) for the ESMA Bond Data Tracker. The MVP focuses on extracting key bond data from downloaded ESMA prospectuses into JSON/Excel.

**Current Project State:**
*   `esma_scraper.py`: Functionally complete for downloading PDFs.
*   `pdf_extractor.py`: Exists, but needs significant work on extracting key fields.
*   `main.py`: Runs scraper only; does not integrate extractor or produce final output.

**MVP Roadmap Focus:**
1.  **Offline PDF Extraction Refinement:** Make `pdf_extractor.py` work well on sample files.
2.  **Pipeline Integration:** Connect the refined extractor to `main.py`.
3.  **Final Output Generation:** Create the consolidated JSON/Excel files.

For best results, use **Claude 3.5 Sonnet** in Cursor.

---

## Phase 1 (MVP): Offline PDF Extraction Refinement & Testing

**Goal:** Achieve reliable extraction of key MVP fields from existing PDFs *before* full pipeline integration.

### Prompt 1.1: Setup Extraction Test Script

```markdown
# TASK: Create PDF Extraction Test Script

## CONTEXT
We need to iteratively test and refine the `pdf_extractor.py` module using already downloaded sample PDFs without running the full web scraper each time. This requires a dedicated test script.

## CURRENT CODE
- `processes/pdf_extractor.py`: Contains `PDFExtractor` class with `process_single_pdf(pdf_path)` method.
- `data/downloads/`: Contains downloaded PDFs organized by company/type.

## SPECIFIC TASK
Create a new Python script, ideally `scripts/test_extractor.py`, that does the following:
1.  Takes one or more PDF file paths as command-line arguments (using `argparse`).
2.  Allows specifying a directory containing sample PDFs instead of individual files.
3.  Imports and instantiates the `PDFExtractor` from `processes.pdf_extractor`.
4.  For each specified PDF path:
    *   Calls `extractor.process_single_pdf(pdf_path)`.
    *   Prints the returned dictionary (the extracted data) to the console in a readable format (e.g., using `pprint`).
    *   Logs any exceptions encountered during processing for a specific file.
5.  Includes basic timing information to see how long extraction takes per file or in total.

## IMPLEMENTATION DETAILS
- Use `pathlib` for handling file paths.
- Ensure the script can be run from the project root directory.
- Add clear logging messages (e.g., "Processing: [pdf_path]", "Extracted data:", "Error processing [pdf_path]: [error]").

## TESTING & DEBUGGING
1.  Run the script with a single known PDF path: `python scripts/test_extractor.py data/downloads/COMPANY/TYPE/file.pdf`.
2.  Run the script with a directory: `python scripts/test_extractor.py --dir data/downloads/COMPANY/TYPE/`.
3.  Test with a PDF known to cause errors (if any) to ensure error handling works.
4.  Verify the extracted data printed matches expectations for a simple test PDF.
```

### Prompt 1.2: Refine/Implement Bank Extraction

```markdown
# TASK: Improve Bank/Underwriter Extraction in PDF Extractor

## CONTEXT
Based on initial testing with `scripts/test_extractor.py`, the extraction of bank names (underwriters, bookrunners, managers) from PDFs is unreliable or incomplete. This is a critical field for the MVP.

## CURRENT CODE
- `processes/pdf_extractor.py`: `PDFExtractor` class.
- `extract_bank_info(self, text: str) -> Dict`: Current method using regex, likely searching within a 'distribution' section found by `find_section`.
- `_clean_bank_name(self, bank_name: str)`: Basic name cleaning.
- `is_valid_bank_name(self, bank: str)`: Basic validation/filtering.

## SPECIFIC TASK
Review and significantly enhance the logic within `PDFExtractor` to more reliably identify and extract bank names and their roles (e.g., 'Joint Lead Manager', 'Bookrunner', 'Stabilisation Manager').
1.  **Improve Section Finding:** Make `find_section` more robust. Search for multiple variations of section headers (e.g., 'Plan of Distribution', 'Subscription and Sale', 'Underwriting', 'Placement Agents'). Consider searching across the *entire document* if specific sections aren't found.
2.  **Enhance Regex Patterns:** Modify the regex within `extract_bank_info`. Look for patterns like lists of banks following role keywords (e.g., "The Joint Lead Managers are:", "Bookrunners:"). Handle various list formats (bullet points, comma-separated, numbered lists). Use non-greedy matching and capture groups effectively.
3.  **Contextual Analysis:** If simple regex fails, consider extracting text blocks around potential role keywords and searching for capitalized words or known bank suffixes (AG, SA, PLC, LLC, N.V., S.p.A.) within those blocks.
4.  **Role Association:** Ensure the extracted role is clearly associated with the correct bank(s).
5.  **Refine Cleaning/Validation:** Improve `_clean_bank_name` (remove leading/trailing noise) and `is_valid_bank_name` (add more keywords to ignore, check for minimum length/complexity).

## IMPLEMENTATION DETAILS
- Focus modifications within `pdf_extractor.py`.
- Prioritize accuracy for banks listed under common roles.
- Consider adding a confidence score based on the extraction method used.
- Use helper methods if the logic becomes complex.

## TESTING & DEBUGGING
1.  Use `scripts/test_extractor.py` with a diverse set of sample PDFs where bank extraction previously failed or was incomplete.
2.  Provide specific examples of PDFs and the expected bank/role output to the AI.
3.  Compare the output of the revised code against manual inspection of the PDFs.
4.  Iteratively refine regex patterns and logic based on test results.
5.  Log which patterns/methods successfully extracted banks for specific files.
```

### Prompt 1.3: Implement/Refine Other Key Field Extraction

```markdown
# TASK: Implement/Refine Extraction for Size, Currency, Dates, Coupon

## CONTEXT
Besides banks, the MVP requires extracting Issue Size, Currency, Issue Date, Maturity Date, and Coupon Rate from the PDFs. Current logic for these fields in `pdf_extractor.py` is likely missing or underdeveloped.

## CURRENT CODE
- `processes/pdf_extractor.py`: `PDFExtractor` class.
- `_extract_metadata(self, text: str) -> Dict`: May contain rudimentary attempts, but likely insufficient.
- Methods for extracting these specific fields are probably needed.

## SPECIFIC TASK
Add or significantly enhance methods within `PDFExtractor` to find and extract:
1.  **Issue Size & Currency:** Look for terms like 'Aggregate Nominal Amount', 'Principal Amount', 'Issue Size'. Extract the numeric value and the currency symbol/code (e.g., EUR, USD, €, $). Handle different formatting (commas, decimals).
2.  **Issue Date & Maturity Date:** Search for labels like 'Issue Date', 'Dated', 'Maturity Date'. Extract dates in various formats (e.g., 'DD Month YYYY', 'YYYY-MM-DD') and attempt to parse them into a standard format (e.g., YYYY-MM-DD).
3.  **Coupon Rate:** Look for 'Coupon', 'Interest Rate', 'Fixed Rate'. Extract the percentage value(s). Handle cases like 'Fixed Rate', 'Floating Rate', step-up coupons (extracting the initial rate might be sufficient for MVP).

## IMPLEMENTATION DETAILS
- Create new helper methods within `PDFExtractor` (e.g., `_extract_issue_size_currency`, `_extract_dates`, `_extract_coupon`).
- These methods should take the extracted text (or relevant sections) as input.
- Use targeted regex patterns for each field.
- Prioritize finding these fields in common locations (e.g., summary tables, first few pages, specific sections like 'Terms and Conditions').
- Return extracted values in a structured way (e.g., separate keys for size and currency).
- Add calls to these new methods within `process_single_pdf` and include their results in the returned dictionary.

## TESTING & DEBUGGING
1.  Use `scripts/test_extractor.py` with sample PDFs where these fields are clearly visible.
2.  Provide specific examples of PDFs and expected output for size, currency, dates, and coupon.
3.  Test with different formatting variations found in the sample PDFs.
4.  Compare extracted values against manual inspection.
5.  Log which regex patterns succeeded for each field.
```

### Prompt 1.4: Implement Bank Name Standardization (Utility Script)

```markdown
# TASK: Create Bank Name Standardization Utility

## CONTEXT
The PDF extractor identifies bank names, but the same bank often appears with variations (e.g., "BNP Paribas SA", "BNP", "BNP Paribas Securities"). We need a utility to map these to a standard name for consistent analysis.

## SPECIFIC TASK
Create a new utility script `processes/utils/bank_standardizer.py` containing a `BankStandardizer` class.
1.  **Data Store:** The class should load known bank name variations and their standard forms from a JSON file (`data/bank_names.json`).
    ```json
    // Example data/bank_names.json
    {
      "bnp paribas": {
        "standard_name": "BNP Paribas",
        "aliases": ["bnp", "bnp paribas sa", "bnp paribas securities", "bnp paribas fortis"]
      },
      "deutsche bank": {
        "standard_name": "Deutsche Bank AG",
        "aliases": ["deutsche bank ag", "db"]
      }
      // ... more banks
    }
    ```
2.  **Standardization Method:** Implement a method `standardize(extracted_name: str) -> Tuple[str, float] | None` that:
    *   Cleans the input `extracted_name` (lowercase, remove common suffixes like SA, AG, Ltd, PLC, remove punctuation).
    *   Checks for an exact match in the aliases of the loaded JSON data.
    *   If no exact match, uses fuzzy matching (e.g., `fuzzywuzzy` library's `token_set_ratio`) against the aliases to find the best match above a certain threshold (e.g., 85).
    *   Returns a tuple containing the `standard_name` and a confidence score (1.0 for exact match, fuzzy ratio for fuzzy match), or `None` if no match is found above the threshold.
3.  **Loading:** Load the JSON data upon class initialization.

## IMPLEMENTATION DETAILS
- Add `fuzzywuzzy` and `python-Levenshtein` to `requirements.txt` if not already present.
- Handle potential file loading errors for `bank_names.json`.
- The cleaning step should be robust to common variations.

## TESTING & DEBUGGING
1.  Create unit tests for the `standardize` method with various inputs:
    *   Exact matches (case variations, with/without suffixes).
    *   Fuzzy matches (minor typos, abbreviations).
    *   Names that should *not* match.
2.  Populate `bank_names.json` with a few key examples.
3.  Run tests to verify correct standard name and confidence score are returned.
4.  Test edge cases (empty input, very short names).
```

### Prompt 1.5: Integrate Bank Name Standardization into Extractor

```markdown
# TASK: Integrate Bank Standardizer into PDF Extractor

## CONTEXT
The `BankStandardizer` utility (`processes/utils/bank_standardizer.py`) has been created (Prompt 1.4). Now, we need to use it within the `PDFExtractor` to standardize bank names immediately after they are extracted.

## CURRENT CODE
- `processes/pdf_extractor.py`: `PDFExtractor` class, specifically the `extract_bank_info` method which identifies raw bank names.
- `processes/utils/bank_standardizer.py`: Contains `BankStandardizer` class with `standardize` method.

## SPECIFIC TASK
Modify `processes/pdf_extractor.py`:
1.  Import the `BankStandardizer` class.
2.  Instantiate `BankStandardizer` within the `PDFExtractor.__init__` method.
3.  Modify the `extract_bank_info` method (or wherever raw bank names are finalized):
    *   After extracting a potential bank name and its role, call `self.bank_standardizer.standardize(raw_bank_name)`.
    *   If standardization returns a result (standard name and confidence score), store the `standard_name`, `raw_bank_name`, `role`, and `confidence_score` in the results dictionary.
    *   If standardization returns `None`, decide how to handle it (e.g., store the raw name with a low confidence score, or discard it - maybe store for review?). For MVP, storing the raw name might be acceptable.
4.  Update the structure of the data returned by `extract_bank_info` (and thus `process_single_pdf`) to include these new fields (standard name, confidence).

## IMPLEMENTATION DETAILS
- Ensure the `BankStandardizer` is initialized only once per `PDFExtractor` instance.
- The results dictionary structure should clearly distinguish between the original extracted name and the standardized name.

## TESTING & DEBUGGING
1.  Modify `scripts/test_extractor.py` to print the new standardized name and confidence score fields.
2.  Run the test script with sample PDFs containing banks present in `data/bank_names.json`.
3.  Verify that the correct standard names and appropriate confidence scores are output.
4.  Test with bank names *not* in the standardization list to see how they are handled.
```

### Prompt 1.6: Implement Basic Extraction Validation

```markdown
# TASK: Implement Basic Extraction Validation Rules

## CONTEXT
Extracted data can be noisy or incorrect. We need basic validation within the `PDFExtractor` to flag potentially problematic results before they are used.

## CURRENT CODE
- `processes/pdf_extractor.py`: `PDFExtractor` class, `process_single_pdf` returns extracted data.
- `is_valid_bank_name` provides some basic filtering.

## SPECIFIC TASK
Implement a validation step within `PDFExtractor`.
1.  **Create Validation Method:** Add a method `_validate_extracted_data(self, extracted_data: Dict) -> Dict`.
2.  **Implement Rules:** Inside this method, apply basic checks to the `extracted_data` dictionary:
    *   **Bank Presence:** Check if the list of extracted banks is empty. If so, flag it (e.g., add `validation_flags: ['no_banks_found']`).
    *   **Bank Confidence:** Check if any standardized bank names have low confidence scores (e.g., below 0.85). Flag if necessary.
    *   **Date Plausibility:** Check if extracted dates seem reasonable (e.g., maturity date is after issue date, dates are within expected ranges like 1990-2050).
    *   **Size/Currency Presence:** Check if issue size and currency were extracted.
    *   **(Optional) Cross-checks:** If possible, perform simple cross-checks (e.g., does the extracted issuer name match the company being processed?).
3.  **Integrate:** Call `_validate_extracted_data` at the end of `process_single_pdf` before returning the results. Merge the validation flags into the returned dictionary.

## IMPLEMENTATION DETAILS
- The validation should *add* flags or warnings, not necessarily *remove* data at this stage.
- Keep the rules simple and focused on obvious errors for the MVP.
- The validation flags should be stored in a list under a specific key (e.g., `validation_flags`).

## TESTING & DEBUGGING
1.  Modify `scripts/test_extractor.py` to print the `validation_flags` field.
2.  Create or use sample PDFs that *should* trigger validation flags (e.g., a PDF where bank extraction fails, a PDF with weird dates).
3.  Run the test script and verify that the appropriate flags are generated.
4.  Test with well-formed PDFs to ensure *no* flags are raised incorrectly.
```

---

## Phase 2 (MVP): Pipeline Integration

**Goal:** Connect the refined `pdf_extractor.py` (from Phase 1) into the main `main.py` workflow.

### Prompt 2.1: Integrate Refined Extractor into Main Workflow

```markdown
# TASK: Integrate Refined PDF Extractor into Main Workflow

## CONTEXT
Phase 1 focused on refining `pdf_extractor.py` offline. Now, we need to integrate this improved extractor into the main script (`processes/main.py`) that currently only runs the scraper.

## CURRENT CODE
- `processes/main.py`: Runs `ESMAScraper`, saves per-company metadata JSON.
- `processes/pdf_extractor.py`: Contains the *refined* `PDFExtractor` class (including standardization and validation from Phase 1).
- `processes/esma_scraper.py`: `ESMAScraper` downloads files to structured directories.

## SPECIFIC TASK
Modify `processes/main.py` to perform the full Scrape -> Extract workflow:
1.  **Instantiate Extractor:** Import `PDFExtractor` and instantiate it at the start of the `main` function.
2.  **Get Downloaded PDF Paths:** *After* the `scraper.search_and_process(company_name, ...)` call successfully completes for a company, determine the list of PDF file paths that were downloaded *for that specific run/company*.
    *   **Challenge:** The scraper currently doesn't directly return the paths of successfully downloaded and organized files.
    *   **Recommended Solution:** Modify `ESMAScraper`'s `search_and_process` method (and potentially `download_document`/`organize_file`) to collect and return a list of the final, successfully saved PDF file paths for the processed company.
3.  **Call Extractor:** Iterate through the list of PDF paths obtained in the previous step. For each path, call `pdf_extractor.process_single_pdf(pdf_path)` within a `try...except` block.
4.  **Collect Results:** Store all successfully returned extraction dictionaries (which now include standardized names, validation flags, etc.) for the current company in a list (e.g., `company_extraction_results`).
5.  **Update Temporary Output (for verification):** Modify the per-company JSON saving logic. Instead of (or in addition to) the raw scraper metadata, save the `company_extraction_results` list. This confirms the integrated pipeline works *before* moving to final aggregation.

## IMPLEMENTATION DETAILS
- If modifying the scraper, ensure the changes cleanly propagate the file paths back to `main.py`.
- Add logging to show how many PDFs are being queued for extraction for each company.
- Handle errors gracefully if PDF paths cannot be determined or if extraction fails for a file (log the error and continue).

## TESTING & DEBUGGING
1.  Run `main.py` for a *single* company known to have downloadable PDFs.
2.  Verify that the log shows PDFs being passed to the extractor.
3.  Check the output JSON file (`data/processed/COMPANY_NAME.json`) and confirm it contains the `company_extraction_results` list with data extracted from the PDFs.
4.  Test with a company where scraping might yield results but PDF extraction might fail for some files.
```

---

## Phase 3 (MVP): Final Output Generation & MVP Finalization

**Goal:** Produce the consolidated JSON/Excel output files containing data from all processed companies.

### Prompt 3.1: Aggregate Data and Generate Final JSON/Excel

```markdown
# TASK: Aggregate Results and Create Final JSON/Excel Output

## CONTEXT
The `main.py` script now integrates the refined PDF extractor (Phase 2) and produces per-company JSON files containing extracted data. The final MVP step is to aggregate this data across all processed companies into the specified `results/extracted_data.json` and `results/extracted_data.xlsx` files.

## CURRENT CODE
- `processes/main.py`: Loops through companies, scrapes, extracts, and saves results *per company* (temporarily).

## SPECIFIC TASK
Modify `processes/main.py`:
1.  **Initialize Global List:** Before the main company processing loop starts, initialize an empty list (e.g., `all_extracted_data = []`).
2.  **Append Results:** Inside the loop, after successfully getting the `company_extraction_results` list for a company (from Prompt 2.1), iterate through this list. For each individual PDF\'s extraction dictionary, add relevant context (like `company_name` from the outer loop, perhaps the source `pdf_path`) to the dictionary, and then append this enriched dictionary to the global `all_extracted_data` list.
3.  **Remove Temporary Output:** Remove or comment out the code that saves the *per-company* JSON file.
4.  **Generate Final JSON:** *After* the main loop finishes, write the entire `all_extracted_data` list to `results/extracted_data.json`. Use `json.dump` with `indent=2` for readability.
5.  **Generate Final Excel:**
    *   Import `pandas` (`import pandas as pd`).
    *   *After* the main loop, convert the `all_extracted_data` list into a pandas DataFrame (`df = pd.DataFrame(all_extracted_data)`).
    *   Define the desired order of columns for the Excel sheet (e.g., `company_name`, `issuer_name`, `issue_date`, `maturity_date`, `issue_size`, `currency`, `coupon_rate`, `bank_standard_name`, `bank_role`, `bank_raw_name`, `bank_confidence`, `pdf_path`, `validation_flags`).
    *   Reindex the DataFrame to ensure all desired columns are present and in order, handling missing values appropriately (`df = df.reindex(columns=[...])`).
    *   Save the DataFrame to `results/extracted_data.xlsx` using `df.to_excel('results/extracted_data.xlsx', index=False)`.
6.  **Add Summary Logging:** At the very end, log summary statistics: total companies attempted, total companies successfully processed (scraper ran + at least one PDF extracted?), total PDFs extracted, total errors during extraction.

## IMPLEMENTATION DETAILS
- Ensure the `results/` directory exists before writing files.
- Handle potential errors during file writing.
- Carefully select and order the columns for the Excel output to match the key MVP fields and useful context/metadata.

## TESTING & DEBUGGING
1.  Run `main.py` for a small number of companies (e.g., 2-3).
2.  Verify that `results/extracted_data.json` and `results/extracted_data.xlsx` are created.
3.  Inspect the JSON file for correct structure and aggregated data from all test companies.
4.  Open the Excel file and check:
    *   Data from all test companies is present.
    *   Columns are correctly named and ordered.
    *   Data aligns with the correct columns.
5.  Check the logs for the summary statistics.
```

### Prompt 3.2: Update Documentation

```markdown
# TASK: Update Project Documentation for MVP

## CONTEXT
The core MVP functionality (scrape -> extract -> consolidate -> output JSON/Excel) is now complete. The project documentation needs to be updated to reflect this.

## CURRENT CODE
- `docs/doccumentation.md` or `README.md`: Contains potentially outdated information.
- `docs/PROJECT_MILESTONES.md`: Reflects the MVP plan.

## SPECIFIC TASK
Review and update the main project documentation file (`README.md` or `docs/doccumentation.md`):
1.  **Update Overview/Goal:** Ensure it accurately describes the MVP's focus on ESMA bond data extraction.
2.  **Update Data Flow:** Describe the current 3-stage process: `main.py` uses `ESMAScraper` to download PDFs, then uses `PDFExtractor` (with standardization/validation) to process them, and finally aggregates results into `results/extracted_data.json` and `results/extracted_data.xlsx`.
3.  **Update Usage Instructions:** Explain how to run the `main.py` script to generate the MVP output. Mention any necessary setup (e.g., `requirements.txt`, Tesseract if OCR is crucial, populating `data/bank_names.json`).
4.  **Describe Output Files:** Detail the structure of `results/extracted_data.json` (list of dictionaries) and the columns present in `results/extracted_data.xlsx`.
5.  **Remove Obsolete Sections:** Remove any sections detailing workflows or outputs that are no longer relevant to the completed MVP.

## IMPLEMENTATION DETAILS
- Ensure clarity and accuracy.
- Use code formatting for file paths and commands.

## TESTING & DEBUGGING
1.  Read through the updated documentation from the perspective of a new user.
2.  Verify that the usage instructions are correct and lead to the described output.
3.  Confirm the output file descriptions match the actual generated files.
```

---

## Post-MVP / Future Enhancement Prompts

*(These prompts address tasks beyond the core MVP, such as database integration, advanced workflow management, UI, and further scraper improvements. They correspond mostly to items listed in Phase 4 / Post-MVP in the milestones.)*

### Future Prompt: Improve ESMA Scraper Interaction Stability (Ref: Old Prompt 3)
*(Focuses on making Selenium interactions more robust using explicit waits, better selectors, and enhanced error diagnostics.)*

### Future Prompt: Add Reliable Document Type Filtering (Ref: Old Prompt 5)
*(Focuses on reliably filtering document types *at the source* via the scraper UI/form, rather than post-download filtering.)*

### Future Prompt: Implement Multi-Stage Extraction (Ref: Old Prompt 7)
*(Focuses on enhancing `pdf_extractor.py` with fallback strategies, comparing results from different methods, and improving confidence scoring beyond the basic MVP implementation.)*

### Future Prompt: Create SQLite Database Backend (Ref: Old Prompt 9)
*(Focuses on designing and implementing a database schema (`companies`, `documents`, `banks`, `document_banks`, etc.) and a handler (`database_handler.py`) to store and query the extracted data more efficiently than flat files. This is a key step towards a LobbyFacts-like searchable interface.)*

### Future Prompt: Create Progress Dashboard (Ref: Old Prompt 10)
*(Focuses on creating an HTML dashboard to visualize the progress and success/failure rates of the scraping and extraction process.)*

### Future Prompt: Enhance Main Workflow Orchestration (Ref: Old Prompt 11)
*(Focuses on adding features like batch processing, checkpointing, and resume capabilities to `main.py` for handling large-scale runs more robustly.)*

### Future Prompt: Refactor PDF Extractor into Modular Components

```markdown
# TASK: Refactor PDF Extractor into Modular Components

## CONTEXT
The current `pdf_extractor.py` file has grown to over 2600 lines of code, making it difficult to maintain, test, and extend. It combines multiple responsibilities: text extraction, bank identification, metadata extraction (dates, currency, coupon), and validation. This monolithic structure violates the Single Responsibility Principle and creates challenges for ongoing development.

## CURRENT CODE
- `processes/pdf_extractor.py`: A large (~2600 lines) file containing the `PDFExtractor` class with all extraction logic.
- Key methods include `process_single_pdf`, `_extract_banks_and_roles`, `_extract_metadata`, `_extract_dates`, `_extract_issue_size_currency`, `_extract_coupon`, etc.

## SPECIFIC TASK
Refactor the PDF extraction functionality into a modular package structure with specialized components:

1. **Create Package Structure:**
   ```
   processes/
   ├── pdf_extraction/              # New package directory
   │   ├── __init__.py              # Exports key classes
   │   ├── extractors/              # Specialized extractors
   │   │   ├── __init__.py
   │   │   ├── bank_extractor.py    # Bank name/role extraction
   │   │   ├── date_extractor.py    # Issue/maturity date extraction
   │   │   ├── currency_extractor.py # Size/currency extraction
   │   │   └── coupon_extractor.py  # Coupon rate/type extraction
   │   ├── utils/                   # Shared utilities
   │   │   ├── __init__.py
   │   │   ├── text_processing.py   # Section finding, text cleaning
   │   │   └── pattern_registry.py  # Central repo for regex patterns
   │   └── core.py                  # Orchestration engine
   ├── pdf_extractor.py             # Slim facade for backward compatibility
   ```

2. **Implement Core Components:**
   - Create a base `BaseExtractor` class that defines the common interface
   - Implement specialized extractors by moving existing methods to appropriate files
   - Create a central `ExtractionEngine` class in `core.py` that orchestrates the extraction process
   - Update the main `PDFExtractor` class to delegate to the new engine

3. **Maintain Backward Compatibility:**
   - Ensure the public API of `PDFExtractor` remains unchanged
   - Existing code calling `process_single_pdf` should continue to work without modification
   - Return values should match the current structure exactly

## IMPLEMENTATION DETAILS

### 1. BaseExtractor Interface
Create a consistent interface for all extractors to follow:

```python
# processes/pdf_extraction/extractors/base_extractor.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseExtractor(ABC):
    """Base class for all text extractors."""
    
    @abstractmethod
    def extract(self, text: str) -> Dict[str, Any]:
        """
        Extract information from text.
        
        Args:
            text: The text to extract information from
            
        Returns:
            Dictionary containing extracted information
        """
        pass
```

### 2. Example Specialized Extractor
Move the date extraction logic to its own class:

```python
# processes/pdf_extraction/extractors/date_extractor.py
from typing import Dict, Optional
from datetime import datetime
import re
from ..utils.pattern_registry import PatternRegistry
from .base_extractor import BaseExtractor

class DateExtractor(BaseExtractor):
    """Extracts issue date and maturity date information."""
    
    def __init__(self):
        self.patterns = PatternRegistry.get_date_patterns()
        
    def extract(self, text: str) -> Dict[str, Optional[str]]:
        """
        Extract date information from text.
        
        Args:
            text: The text to extract dates from
            
        Returns:
            Dictionary with issue_date and maturity_date keys
        """
        # Implementation (moved from current _extract_dates method)
        date_info = {'issue_date': None, 'maturity_date': None}
        
        # [Move existing date extraction code here]
        
        return date_info
        
    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        """Helper method to parse various date formats."""
        # [Move existing date parsing code here]
```

### 3. Pattern Registry
Centralize regex patterns:

```python
# processes/pdf_extraction/utils/pattern_registry.py
class PatternRegistry:
    """Central repository for regex patterns used in extraction."""
    
    @staticmethod
    def get_date_patterns():
        """Get patterns for date extraction."""
        return {
            'issue_date': [
                # [Move patterns from _extract_dates]
                r'(?:issue\s+date|date\s+of\s+issue|issuance\s+date)\s*[:\-]?\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                # ... more patterns
            ],
            'maturity_date': [
                # [Move patterns from _extract_dates]
                r'(?:maturity\s+date|final\s+maturity|redemption\s+date)\s*[:\-]?\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                # ... more patterns
            ]
        }
    
    @staticmethod
    def get_bank_patterns():
        """Get patterns for bank extraction."""
        # Similar implementation for bank patterns
```

### 4. Orchestration Engine
Create a class to coordinate all extractors:

```python
# processes/pdf_extraction/core.py
from typing import Dict, Optional, Any
import os
from .extractors.bank_extractor import BankExtractor
from .extractors.date_extractor import DateExtractor
from .extractors.currency_extractor import CurrencyExtractor
from .extractors.coupon_extractor import CouponExtractor
from .utils.text_processing import TextProcessor
import logging

class ExtractionEngine:
    """Orchestrates the PDF extraction process."""
    
    def __init__(self, use_ocr=True, max_workers=4):
        self.logger = logging.getLogger(__name__)
        self.text_processor = TextProcessor()
        self.bank_extractor = BankExtractor(self.text_processor)
        self.date_extractor = DateExtractor()
        self.currency_extractor = CurrencyExtractor()
        self.coupon_extractor = CouponExtractor()
        self.use_ocr = use_ocr
        self.max_workers = max_workers
        
    def extract_text(self, pdf_path):
        """Extract text from PDF."""
        # Implementation from current extract_text method
        
    def process_text(self, text, pdf_path):
        """Process extracted text to identify all required information."""
        # Extract each type of information
        bank_info = self.bank_extractor.extract(text)
        
        # Extract metadata
        dates = self.date_extractor.extract(text)
        currency_info = self.currency_extractor.extract(text)
        coupon_info = self.coupon_extractor.extract(text)
        
        # Extract document sections
        sections = self.text_processor.extract_sections(text)
        
        # Combine all metadata
        metadata = {
            **dates,
            **currency_info,
            **coupon_info
        }
        
        # Create result dictionary (matching current structure)
        result = {
            'filename': os.path.basename(pdf_path),
            'file_path': pdf_path,
            'metadata': metadata,
            'sections': sections,
            'extracted_banks': bank_info['extracted_banks'],
            'bank_sections': bank_info['bank_sections'],
            'bank_info': bank_info,  # For backward compatibility
        }
        
        # Validate results
        validation_flags = self._validate_extraction_results(
            bank_info, metadata, sections, pdf_path
        )
        result['validation_flags'] = validation_flags
        
        return result
        
    def _validate_extraction_results(self, bank_info, metadata, sections, pdf_path):
        """Validate extraction results."""
        # Implementation from current _validate_extraction_results method
```

### 5. Updated PDFExtractor
Slim down the main class to be a facade:

```python
# processes/pdf_extractor.py
from typing import Dict, List, Optional, Any
import os
from processes.pdf_extraction.core import ExtractionEngine

class PDFExtractor:
    """
    PDF Document Extractor
    --------------------
    Extracts and processes text content from PDF documents,
    specifically designed for ESMA prospectus documents.
    """
    
    def __init__(self, pdf_dir: str = "data/downloads", use_ocr: bool = True, max_workers: int = 4):
        """Initialize the PDF extractor."""
        self.pdf_dir = pdf_dir
        self.use_ocr = use_ocr
        self.max_workers = max_workers
        
        # Create the extraction engine
        self.engine = ExtractionEngine(use_ocr=use_ocr, max_workers=max_workers)
        
    def process_single_pdf(self, pdf_path: str) -> Optional[Dict]:
        """
        Process a single PDF file to extract bank information and other metadata.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary containing extracted information
        """
        try:
            # Extract text
            text = self.engine.extract_text(pdf_path)
            if not text:
                return {
                    'filename': os.path.basename(pdf_path),
                    'validation_flags': ['text_extraction_failed']
                }
                
            # Process the text
            return self.engine.process_text(text, pdf_path)
            
        except Exception as e:
            self.engine.logger.error(f"Error processing {pdf_path}: {str(e)}")
            return {
                'filename': os.path.basename(pdf_path),
                'file_path': pdf_path,
                'validation_flags': [f'processing_error: {str(e)}']
            }
    
    # Include other public methods for backward compatibility
    def process_pdfs(self) -> List[Dict]:
        """Process all PDFs in the directory."""
        # Implementation delegates to engine
```

## TESTING & DEBUGGING
1.  Create unit tests for each extractor separately.
2.  Ensure the modular components return the same results as the monolithic version.
3.  Test with a variety of PDF documents to verify consistent behavior.
4.  Create a regression test to compare output before and after refactoring.
5.  Check that existing code using `PDFExtractor` continues to work without modification.

## REFACTORING APPROACH
1.  Start by creating the package structure and empty base files.
2.  Implement one extractor at a time, with corresponding unit tests.
3.  Create the extraction engine to orchestrate the process.
4.  Update the facade class last, ensuring backward compatibility.
5.  Be careful not to change the behavior or return values of any methods.
```
