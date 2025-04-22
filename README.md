# ESMA Bond Data Tracker

This project aims to build a tool to extract and aggregate key bond data, primarily focusing on underwriter information, for specific companies from ESMA Prospectus documents. The primary challenge lies in reliably extracting structured data from PDF documents with variable formats.

## Project Goal

Provide accessible, aggregated data on bond underwriting links and other key financial details found within ESMA prospectuses, primarily for researchers and campaigners.

## Minimum Viable Product (MVP) Scope

The MVP focuses on delivering the core extraction and aggregation pipeline:

1.  **Automated Prospectus Download:** Download relevant ESMA prospectuses for a predefined list of companies using `processes/esma_scraper.py`.
2.  **Key Field Extraction:** Extract the following fields from the downloaded PDFs using `processes/pdf_extractor.py`:
    *   Issuer Name
    *   Underwriting Banks/Bookrunners (including standardization)
    *   Issue Size & Currency
    *   Issue Date & Maturity Date
    *   Coupon Rate(s)
3.  **Consolidated Output:** Store the extracted data in structured formats: `results/extracted_data.json` and `results/extracted_data.xlsx`.

## Current Status (Summary from PROJECT_MILESTONES.md)

*   **ESMA Scraper (`esma_scraper.py`):** Functionally complete for downloading and organizing PDFs. **`[x]`**
*   **PDF Extractor (`pdf_extractor.py`):** Initial extraction logic exists but requires significant refinement for MVP fields and is not fully integrated. **`[~]`**
*   **Main Workflow (`main.py`):** Runs the scraper but does not yet integrate the extractor or produce the final aggregated output. **`[~]`**
*   **Output:** Final consolidated JSON/Excel files are not yet generated. **`[ ]`**

## Development Roadmap (Simplified)

1.  **Phase 1: Offline PDF Extraction Refinement:** Improve `pdf_extractor.py` using sample PDFs.
2.  **Phase 2: Pipeline Integration:** Connect the refined extractor to `main.py`.
3.  **Phase 3: Final Output Generation:** Create the consolidated JSON/Excel files.

## Technology Stack

*   **Python:** Core language.
*   **Web Scraping:** Selenium (`undetected-chromedriver`).
*   **PDF Processing:** PyMuPDF, pdfplumber (potential Tesseract OCR fallback).
*   **Data Handling:** pandas.
*   **Development:** VS Code with Cursor AI assistant.

## Basic Usage (Anticipated)

1.  Ensure all dependencies are installed:
    ```bash
    pip install -r requirements.txt
    ```
2.  Ensure `data/bank_names.json` (for standardization) is populated if needed.
3.  Run the main workflow script (likely `main.py` or `run.py`):
    ```bash
    python main.py
    ```
4.  Check the `results/` directory for `extracted_data.json` and `extracted_data.xlsx`.

## Output Files

*   **`results/extracted_data.json`:** A list of dictionaries, where each dictionary represents the extracted data from a single PDF document.
*   **`results/extracted_data.xlsx`:** A spreadsheet containing the aggregated extracted data, with columns corresponding to the key MVP fields.

## Notes

*   The project is currently focused on achieving the MVP functionality.
*   Development prioritizes refining the PDF extraction logic offline before full pipeline integration.

## System Components

1. **ESMA Scraper** (`processes/esma_scraper.py`)
   - Downloads PDF documents from the ESMA website
   - Filters for "Final Terms" documents
   - Handles document metadata and organization

2. **PDF Extractor** (`processes/pdf_extractor.py`)
   - Processes downloaded PDFs
   - Extracts bank information, particularly from the "Distribution" section
   - Uses both primary (section-based) and fallback (pattern-based) extraction strategies

## Test Process

The test script (`test_full_process.py`) demonstrates the complete workflow:

1. Downloads Final Terms documents for test companies:
   - BNP Paribas
   - Société Générale
   - Deutsche Bank

2. Processes the downloaded PDFs to extract bank information

3. Saves results in JSON format

### Directory Structure

```
data/
└── test/
    ├── downloads/    # Downloaded PDFs
    └── results/      # Extracted bank information
```

### Running the Test

1. Ensure all dependencies are installed:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the test script:
   ```bash
   python test_full_process.py
   ```

3. Monitor the progress through the console output

4. Check the results in `data/test/results/`

## Notes

- The system is configured to only process "Final Terms" documents
- Bank information is primarily extracted from the "Distribution" section
- Results are saved in JSON format with detailed bank information and roles
- The system includes error handling and logging for troubleshooting

## Troubleshooting

If you encounter issues:
1. Check the console output for error messages
2. Verify the ESMA website is accessible
3. Ensure all required dependencies are installed
4. Check the log files for detailed error information 