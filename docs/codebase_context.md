# ESMA Prospectus Scraper - Codebase Context

## Project Overview
This project is designed to scrape and process ESMA prospectus documents for EU companies, with a focus on final terms documents.

## Directory Structure
```
ff2/
├── data/                      # Data storage
│   ├── raw/                  # Original source data
│   │   └── urgewald GOGEL 2023 V1.2.xlsx
│   └── downloads/            # Downloaded ESMA documents
│       └── [company_name]/   # Company-specific documents
│
├── logs/                     # Logging and tracking
│   ├── company_progress.json # Scraping progress tracking
│   ├── esma_scraper.log     # Scraper execution logs
│   └── eu_companies_scraping.log
│
├── processes/                # Core processing scripts
│   ├── main.py              # Main execution script
│   ├── esma_scraper.py      # ESMA website scraper
│   ├── company_list_handler.py # Company data management
│   ├── pdf_extractor.py     # PDF processing
│   └── utils/               # Utility scripts
│       ├── update_context.py
│       └── metadata_analyzer.py
│
└── docs/                    # Documentation
    ├── doccumentation.md
    └── PROJECT_MILESTONES.md
```

## Core Components

### 1. Main Script (`main.py`)
- **Purpose**: Orchestrates the scraping process
- **Dependencies**:
  - `esma_scraper.py`
  - `company_list_handler.py`
- **Key Functions**:
  - Initializes scraper and company handler
  - Processes companies sequentially
  - Handles errors and logging

### 2. ESMA Scraper (`esma_scraper.py`)
- **Purpose**: Handles web scraping and document downloading
- **Dependencies**:
  - `company_list_handler.py`
- **Key Features**:
  - Selenium-based web scraping
  - Document type filtering
  - Download management
  - Error handling and retries

### 3. Company List Handler (`company_list_handler.py`)
- **Purpose**: Manages company data and progress tracking
- **Dependencies**: None
- **Key Features**:
  - Excel file processing
  - EU company filtering
  - Progress tracking
  - Company data management

### 4. PDF Extractor (`pdf_extractor.py`)
- **Purpose**: Processes downloaded PDFs
- **Dependencies**: None
- **Key Features**:
  - PDF text extraction
  - Section finding
  - Bank information extraction

## Data Flow
1. Source data (Excel) → Company List Handler
2. Company List → ESMA Scraper
3. ESMA Scraper → Downloads
4. Downloads → PDF Extractor
5. Progress tracking throughout

## Key Files
- `company_progress.json`: Tracks scraping progress
- `urgewald GOGEL 2023 V1.2.xlsx`: Source company data
- Log files: Track execution and errors

## Dependencies
- Selenium: Web scraping
- Pandas: Excel processing
- PyMuPDF: PDF processing
- colorlog: Colored logging 