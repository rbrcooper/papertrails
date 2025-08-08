# System Architecture

This document provides a detailed overview of the Papertrails data pipeline's architecture, components, and data flow.

## Pipeline Orchestration

The entire process is orchestrated by `processes/main.py`. It is responsible for coordinating the various components of the system in a sequential and robust manner.

### High-Level Workflow

1.  **Load Companies:** The pipeline starts by loading a list of companies to process using the `CompanyListHandler`. This handler also tracks which companies have already been processed to allow the pipeline to be stopped and resumed.
2.  **Scrape Documents (Optional):** For each company, the `ESMAScraper` is invoked to search for and download relevant prospectus documents from the ESMA portal. This step can be skipped using the `--skip-scraping` command-line flag.
3.  **Process PDFs:** All downloaded PDFs for a company are passed to the `PDFExtractor`.
4.  **Extract Data:** The extractor processes each PDF, using its hybrid AI/regex engine to extract bank names and other metadata.
5.  **Store Results:** The extracted data from each PDF is stored in a structured format in an SQLite database via the `DatabaseHandler`.
6.  **Aggregate and Report:** After all companies are processed, the `DataAggregator` and `OutputGenerator` create a final, consolidated Excel report of all extracted data.

## AI-Enhanced Extraction Engine

The core innovation of this pipeline is the hybrid extraction model, which aims to maximize both accuracy and reliability.

### Components

-   **`PDFExtractor`:** The main entry point for extraction. It receives a PDF path and coordinates the various specialized extractors.
-   **`AIBankExtractor`:** The primary extractor for bank names. It uses a local LLM (Llama 3.1 8B) via Ollama.
-   **Regex Extractors:** A collection of specialized extractors (`DateExtractor`, `CurrencyExtractor`, etc.) that use regular expressions to find well-structured data.
-   **`BankExtractor` (Regex Fallback):** If the `AIBankExtractor` is unavailable or fails, the system falls back to a regex-based bank extractor for basic coverage.

### AI "Smart Chunking" Strategy

To overcome the context-window limitations of local LLMs and to improve accuracy, the `AIBankExtractor` employs a "smart chunking" strategy before sending data to the model:

1.  **Keyword Search:** The entire document text is scanned for a list of keywords related to financial underwriters (e.g., "manager", "arranger", "bookrunner", "syndicate").
2.  **Contextual Chunking:** Instead of sending the whole document, only the text surrounding these keywords (a "chunk" of ~1500 characters) is selected. This provides the LLM with the most relevant context.
3.  **Fallback Chunks:** If no keywords are found, the extractor falls back to analyzing the beginning and middle sections of the document.
4.  **Targeted Prompting:** Each chunk is sent to the LLM with a carefully crafted prompt, instructing it to identify and return a JSON array of bank names.
5.  **Result Aggregation:** Bank names extracted from all chunks are collected and deduplicated to form the final list.

This targeted approach is more efficient and accurate than naive, full-document analysis.

## Core Modules

-   **`processes/main.py`**: Pipeline orchestrator.
-   **`processes/esma_scraper.py`**: Handles all web scraping tasks. It is hardened with retry logic, session management, and anti-detection measures.
-   **`processes/pdf_extractor.py`**: Manages the data extraction process, orchestrating the AI and regex extractors.
-   **`processes/database_handler.py`**: Provides an interface for all database operations, abstracting the SQLite implementation.
-   **`processes/company_list_handler.py`**: Manages the list of companies and tracks the pipeline's progress.
-   **`processes/pdf_extraction/`**: Sub-package containing the core text extraction engine (`core.py`) and all specialized extractor classes.
-   **`processes/pipeline_components/`**: Contains modules for post-extraction tasks like validation, data aggregation, and final report generation.

## Data Flow Diagram

```
[Company List] -> [main.py] -> [ESMAScraper] -> [PDFs on Disk]
                                     |
                                     v
[PDFs on Disk] -> [main.py] -> [PDFExtractor] -> [Extracted Data]
                                     |
                                     v
[Extracted Data] -> [main.py] -> [DatabaseHandler] -> [SQLite DB]
                                     |
                                     v
[SQLite DB] -> [main.py] -> [DataAggregator] -> [OutputGenerator] -> [Excel Report]
``` 