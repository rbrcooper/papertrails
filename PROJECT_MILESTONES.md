# Project Milestones: Fossil Fuel Finance Tracker

## Project Overview

* **Goal:** Build a web-based tool for campaigners to easily track major shareholders (initially US) and bond underwriters (initially EU) involved in fossil fuel financing.
* **Target Audience:** Campaigners, researchers, potentially ethical investors.
* **Data Sources:** US SEC EDGAR (13F filings), ESMA Prospectus Register.
* **Technology Stack:** Python (Selenium, PyPDF2, pdfplumber, pandas) for backend/scraping, potentially a web framework (Flask/Django) and database (SQLAlchemy/PostgreSQL/SQLite) later. Development environment: VSCode with Cursor AI assistant.

## MVP (Minimum Viable Product) Definition

*(Based on the initial project document and current focus)*

* **Core Aim:** Provide accessible, aggregated data on fossil fuel financing links.
* **MVP Feature Set (Initial Focus: Bonds):**
    * Automated download of relevant ESMA prospectuses.
    * Extraction of key fields from PDFs: Issuer, Underwriting Banks/Bookrunners, Issue Size & Currency, Issue/Maturity Dates, Coupon Rates, Ratings, Listing Info, Stabilisation Manager, Tranche Details.
    * Storing extracted data in a structured format (JSON/Excel initially, database later).
    * (Future) Simple web interface to view/search the bond data.
* **Related Component (Shareholders):**
    * Existing separate script extracts 13F shareholder data for a subset of US-based companies. This might be integrated or developed further in a later phase.

## Phase Breakdown / Roadmap

### Phase 1 (ESMA Bond Data Pipeline):
* [x] Initial script for downloading ESMA prospectuses (`esma_scraper.py`).
* [ ] **CURRENT BLOCKER:** Develop robust PDF data extraction logic (`pdf_extractor.py`) to handle variations in prospectus formats. Need to reliably extract fields listed in MVP.
* [ ] Refine data storage (currently JSON/Excel, plan for database).
* [ ] Design and implement database schema (see `documentation.md`).
* [ ] Build reliable data ingestion pipeline into the database.
* [ ] Develop basic web frontend for bond data (Post-MVP).

### Phase 2 (Shareholder Data - Exploration/Refinement):
* [x] Existing script for 13F data extraction (US subset) in a separate directory.
* [ ] Evaluate feasibility/effort for expanding geographic scope (UK, EU, Canada) using free/low-cost sources.
* [ ] Refine/generalize shareholder data extraction if pursued.
* [ ] Design and implement shareholder database schema.
* [ ] Build data ingestion pipeline.
* [ ] Develop basic web frontend for shareholder data (Post-MVP).

### Phase 3 (Integration & Deployment):
* [ ] Integrate bond and shareholder views/data (if applicable).
* [ ] Implement search/filtering capabilities in the web app.
* [ ] Deploy MVP online.

## Key Decisions/Pivots

* *(Date)* Decision to prioritize refining the ESMA bond data pipeline due to perceived broader initial data availability (EU-wide prospectuses) compared to free shareholder data (primarily US 13F).
* *(Date)* Current focus is overcoming the PDF data extraction challenge for ESMA documents.

## Next Steps

* [ ] Complete PDF extraction logic for ESMA documents
* [ ] Set up initial database structure
* [ ] Begin web interface development
* [ ] Document API endpoints and data structures