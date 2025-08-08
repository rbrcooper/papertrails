# Papertrails Data Pipeline

Papertrails is a data processing pipeline designed to extract financial data from public documents for use by NGOs, think tanks, and journalists. It currently focuses on extracting bond underwriting data from ESMA (European Securities and Markets Authority) prospectus documents. Future plans include incorporating equity data from US 13F filings.

The core of this project is a hybrid data extraction system that uses a local LLM (via Ollama) for intelligent, context-aware data extraction, combined with traditional regex-based methods for reliability and speed.

## Current Status: In Development 🏗️

The project has a functional core pipeline but is undergoing development to become a fully automated, production-ready system.

-   **Extraction Engine:** ✅ (AI + Regex Hybrid)
-   **Web Scraper:** ✅ (Hardened against bot detection)
-   **Pipeline Orchestrator:** ✅ (Dynamically processes a list of companies)
-   **Validation & Error Handling:** 🚧 (Under development)
-   **Website/API:** ấp (Planned)

## Core Features

-   **Hybrid Data Extraction:** Combines AI (Llama 3.1 8B) for high-accuracy bank name extraction with regex for structured metadata like dates and currencies.
-   **Intelligent Chunking:** A custom AI strategy that finds relevant sections in large PDFs before sending them to the LLM, overcoming context window limitations.
-   **Dynamic Pipeline:** The main orchestrator can process a list of companies, running the scraper and extractor for each one.
-   **Robust Web Scraping:** Uses `undetected-chromedriver` and hardened techniques to reliably download documents from the ESMA portal.
-   **Modular Architecture:** The system is broken down into distinct, maintainable components for scraping, extraction, database handling, and more.

## Getting Started

### Prerequisites

1.  **Ollama:** You must have [Ollama](https://ollama.ai/) installed and running.
2.  **Llama 3.1 8B Model:** Pull the required model:
    ```bash
    ollama pull llama3.1:8b
    ```
3.  **Python 3.8+:** Ensure you have a compatible Python version.

### Installation

1.  Clone the repository:
    ```bash
    git clone <your-repo-url>
    cd <your-repo-name>
    ```
2.  Install the required Python packages:
    ```bash
    pip install -r docs/requirements.txt
    ```

### Running the Pipeline

To run the full pipeline, which will scrape new documents and then process them:

```bash
python -m processes.main
```

To run the pipeline but skip the scraping step (i.e., only process already downloaded PDFs):

```bash
python -m processes.main --skip-scraping
```

To limit the number of companies processed for a test run:

```bash
python -m processes.main --limit-companies 5
```

## Project Structure

-   `processes/`: The core application logic.
    -   `main.py`: The main pipeline orchestrator.
    -   `esma_scraper.py`: The web scraper for the ESMA portal.
    -   `pdf_extractor.py`: The hybrid AI/regex data extraction engine.
    -   `database_handler.py`: Manages the SQLite database.
    -   `pdf_extraction/`: Contains the individual extractor modules.
    -   `pipeline_components/`: Modules for validation, aggregation, and reporting.
-   `docs/`: Project documentation.
-   `data/`: Data files, including downloaded PDFs and processed output.
-   `logs/`: Application logs.

For more detailed information about the system's design, see `docs/ARCHITECTURE.md`. 