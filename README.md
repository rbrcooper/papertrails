# ESMA Document Processing System

This system is designed to scrape and process Final Terms documents from the ESMA website, specifically focusing on extracting bank information from these documents.

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