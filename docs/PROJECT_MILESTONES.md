# Project Milestones: ESMA Bond Data Tracker

## Project Overview

*   **Goal:** Build a tool to extract and aggregate bond underwriter information for specific companies from ESMA Prospectus documents.
*   **Target Audience:** Campaigners, researchers.
*   **Data Source:** ESMA Prospectus Register.
*   **Technology Stack:** Python (Selenium (`undetected-chromedriver`), PyMuPDF, pdfplumber, pandas) for backend/scraping. Development environment: VSCode with Cursor AI assistant.

## MVP (Minimum Viable Product) Definition

*   **Core Aim:** Provide accessible, aggregated data on bond underwriting links from ESMA prospectuses.
*   **MVP Feature Set:**
    *   [x] Automated download of relevant ESMA prospectuses for a given company list.
    *   [ ] Extraction of key fields from downloaded PDFs: **Issuer, Underwriting Banks/Bookrunners, Issue Size & Currency, Issue/Maturity Dates, Coupon Rates**. (Lower Priority: Ratings, Listing Info, etc.)
    *   [ ] Storing the extracted data in a consolidated, structured format: **`results/extracted_data.json`** and **`results/extracted_data.xlsx`**.

## Current Status & Roadmap to MVP

**Current Status:**
*   **ESMA Scraper (`esma_scraper.py`):** Downloads PDFs for companies successfully, including file organization and deduplication. **Status: `[x]` (Functional)**
*   **PDF Extractor (`pdf_extractor.py`):** Contains initial code for text extraction (PyMuPDF, OCR fallback) and some basic regex (e.g., for banks), but **needs significant refinement** for key MVP fields and is **not currently used** by the main workflow. **Status: `[~]` (Needs Work & Integration)**
*   **Main Workflow (`main.py`):** Runs the scraper to download files but **does not call the PDF extractor** or produce the final consolidated JSON/Excel output. **Status: `[~]` (Incomplete)**
*   **Output:** Currently saves only scraper metadata per company, not the required consolidated extracted data. **Status: `[ ]` (Not Implemented)**

**Roadmap to MVP (Simplified 3-Phase Plan):**

### **Phase 1: Offline PDF Extraction Refinement & Testing**
*   **Goal:** Make `pdf_extractor.py` reliably extract the key MVP fields from a sample of existing PDFs *before* integrating it into the main pipeline.
*   **Key Tasks:**
    *   [ ] **Setup Test Environment:** Create a script (`scripts/test_extractor.py`?) to run `pdf_extractor.py` on specific, already downloaded PDFs.
    *   [ ] **Gather Sample PDFs:** Select diverse examples from `data/downloads/`.
    *   [ ] **Iteratively Refine `pdf_extractor.py`:**
        *   [ ] Focus on robustly extracting **Underwriting Banks/Bookrunners**. (Consider Prompt 7: Multi-Stage Extraction)
        *   [ ] Implement/refine extraction for **Issue Size & Currency**.
        *   [ ] Implement/refine extraction for **Issue Date & Maturity Date**.
        *   [ ] Implement/refine extraction for **Coupon Rate(s)**.
        *   [ ] Implement/refine extraction for **Issuer Name**.
    *   [ ] **Implement Bank Name Standardization:** Create and integrate utility to map variations to standard names (Prompt 6).
    *   [ ] **Implement Basic Validation:** Add rules to check extracted data quality (Prompt 8).
    *   [ ] **Test:** Ensure acceptable accuracy (>80-90% target) for key fields on the sample set.

### **Phase 2: Pipeline Integration**
*   **Goal:** Integrate the *refined* `pdf_extractor.py` into the main workflow (`main.py`).
*   **Key Tasks:**
    *   [ ] Modify `main.py` to instantiate `PDFExtractor`.
    *   [ ] Modify `main.py` to identify downloaded PDF paths for the current company.
    *   [ ] Modify `main.py` to call the refined `pdf_extractor.process_single_pdf()` for each PDF, collecting the results.
    *   [ ] Add logging/error handling for the extraction step within `main.py`.

### **Phase 3: Final Output Generation & MVP Finalization**
*   **Goal:** Produce the final consolidated `results/extracted_data.json` and `results/extracted_data.xlsx` files.
*   **Key Tasks:**
    *   [ ] Modify `main.py` to aggregate all structured results from Phase 2 into a single list.
    *   [ ] Implement saving the aggregated list to `results/extracted_data.json`.
    *   [ ] Implement saving the aggregated list to `results/extracted_data.xlsx` (using pandas).
    *   [ ] Add basic run summary statistics to `main.py` logs.
    *   [ ] Update `README.md`/`doccumentation.md` with MVP usage and output details.

## Post-MVP / Future Enhancements

*   [ ] **Run Full Pipeline:** Process the entire company list end-to-end.
*   [ ] **Database Storage:** Implement SQLite backend for easier querying (Prompt 9).
*   [ ] **Scraper Improvements:** Enhance stability and filtering (Prompts 3, 5).
*   [ ] **Workflow Improvements:** Add checkpointing/resume capabilities (Prompt 11).
*   [ ] **Monitoring:** Create a progress dashboard (Prompt 10).
*   [ ] **Web Frontend:** Develop a simple UI for viewing/searching data (Inspiration: `lobbyfacts.eu`).
*   [ ] **Expand Data:** Consider other fields or data sources.

## Key Decisions & Focus

*   **Decision:** Focus solely on the ESMA Bond data extraction MVP.
*   **Challenge:** Reliable data extraction from variable PDF formats remains the core difficulty.
*   **Strategy:** Tackle PDF extraction refinement **offline first (Phase 1)** to simplify iteration before integrating into the full pipeline.
*   **Current Focus:** Implement **Phase 1: Offline PDF Extraction Refinement & Testing**.

## Next Steps

1.  Begin **Phase 1 (MVP): Offline PDF Extraction Refinement & Testing**.
2.  Proceed to **Phase 2 (MVP): Pipeline Integration**.
3.  Complete **Phase 3 (MVP): Final Output Generation**.

## Success Criteria (MVP)

*   PDF extraction achieves acceptable accuracy (>80-90% target) for key fields (Banks, Size, Currency, Dates) during offline testing (Phase 1) and functions when integrated (Phase 2). Status: `[ ]`
*   Extracted data is correctly aggregated and saved to `results/extracted_data.json` and `results/extracted_data.xlsx` (Phase 3). Status: `[ ]`
*   The core `main.py` workflow successfully integrates the refined extractor and produces the final files for sample companies. Status: `[ ]`
