# Documentation: Fossil Fuel Finance Tracker - ESMA Bond Module

## Architecture Overview

* This module focuses on acquiring and processing bond prospectus data from ESMA.
* It consists of Python scripts for scraping the ESMA website (`esma_scraper.py` using Selenium) and extracting data from downloaded PDFs (`pdf_extractor.py` using PyPDF2/pdfplumber).
* Processed data is currently saved to JSON and Excel files in the `results/` directory.
* Future plans include integrating this data into a database and potentially a web application.

## Directory Structure

ff2/
├── processes/                    # Core processing scripts
│   ├── esma_scraper.py          # ESMA prospectus scraping
│   ├── pdf_extractor.py         # PDF data extraction
│   ├── extract_bank_info.py     # Bank information processing
│   ├── main.py                  # Main execution script
│   └── __pycache__/            # Python cache files
│
├── results/                     # Output data files
│   ├── bank_info.json          # Extracted bank information
│   ├── summary.json            # Summary statistics
│   ├── extracted_data.xlsx     # Excel output
│   └── extracted_data.json     # JSON output
│
├── log/                        # Log files
│   ├── bank_info_extraction.log
│   ├── esma_scraper.log
│   └── esma_process.log
│
├── downloads/                  # Downloaded files
├── venv/                      # Python virtual environment
├── .git/                      # Git repository
├── requirements.txt           # Python dependencies
├── PROJECT_MILESTONES.md      # Project tracking document
└── doccumentation.md          # Project documentation

## Data Flow

1. **Data Collection**
   - `esma_scraper.py` navigates ESMA website using Selenium
   - Downloads prospectus PDFs to `downloads/` directory
   - Logs progress to `log/esma_scraper.log`

2. **Data Extraction**
   - `pdf_extractor.py` processes each PDF using PyPDF2/pdfplumber
   - Extracts structured data using regex and layout analysis
   - Logs extraction results to `log/esma_process.log`

3. **Data Processing**
   - `extract_bank_info.py` processes extracted data
   - Generates summary statistics
   - Logs processing results to `log/bank_info_extraction.log`

4. **Output Generation**
   - Saves processed data to JSON/Excel in `results/`
   - Generates summary reports

## API Endpoints / Key Functions

### esma_scraper.py
```python
def scrape_esma_prospectuses(company_names: List[str], output_dir: str) -> List[str]:
    """
    Scrapes ESMA website for prospectuses matching company names.
    
    Args:
        company_names: List of company names to search for
        output_dir: Directory to save downloaded PDFs
        
    Returns:
        List of downloaded PDF filenames
    """
```

### pdf_extractor.py
```python
def extract_bond_data(pdf_path: str) -> Dict[str, Any]:
    """
    Extracts bond information from prospectus PDF.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Dictionary containing extracted bond data
    """
```

### extract_bank_info.py
```python
def process_bank_data(extracted_data: List[Dict]) -> Dict[str, Any]:
    """
    Processes extracted bond data to identify bank involvement.
    
    Args:
        extracted_data: List of dictionaries containing bond data
        
    Returns:
        Dictionary containing processed bank information
    """
```

## Database Schema (Planned)

* **Bonds Table (Proposed):**
    * `id` (Integer, Primary Key)
    * `esma_prospectus_id` (Text, Unique Identifier from ESMA if available)
    * `issuer_name` (Text)
    * `issue_date` (Date)
    * `maturity_date` (Date, Nullable)
    * `issue_size` (Numeric, Nullable)
    * `currency` (Text, Nullable)
    * `coupon_rate` (Text, Nullable) # Stored as text to handle variations
    * `underwriters` (Text Array or JSON) # List of banks/bookrunners
    * `stabilisation_manager` (Text, Nullable)
    * `ratings_sp` (Text, Nullable)
    * `ratings_moodys` (Text, Nullable)
    * `listing_info` (Text, Nullable)
    * `tranche_details` (Text or JSON, Nullable) # For complex structures
    * `pdf_filename` (Text) # Reference to downloaded file
    * `pdf_url` (Text) # Source URL if available
    * `extracted_on` (Timestamp)

## Key Libraries/Dependencies
```
selenium>=4.0.0
webdriver-manager>=4.0.1
PyPDF2>=3.0.0
pdfplumber>=0.10.3
pandas>=1.3.0
openpyxl==3.1.2
```

## Setup/Installation

1. Create a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
2. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3. Ensure appropriate WebDriver (e.g., ChromeDriver) is installed and accessible or managed by `webdriver-manager`.

## Usage

1. Edit the list of target companies in `main.py` if needed.
2. Run the main script: `python main.py`
3. Check the `results/` directory for output files (`extracted_data.json`, `extracted_data.xlsx`, `summary.json`).

## Error Handling

### Common Issues

1. **PDF Download Failures**
   - Check network connectivity
   - Verify ESMA website accessibility
   - Check `log/esma_scraper.log` for specific errors

2. **PDF Extraction Errors**
   - Verify PDF is not corrupted
   - Check if PDF is password-protected
   - Review `log/esma_process.log` for extraction issues

3. **Data Processing Errors**
   - Check input data format
   - Verify required fields are present
   - Review `log/bank_info_extraction.log` for processing errors

### Logging

- All scripts log to the `log/` directory
- Log files contain timestamps and detailed error messages
- Use log files for debugging and monitoring

## Testing

### Running Tests
```bash
python -m pytest tests/
```

### Test Data
- Sample PDFs in `tests/data/`
- Mock responses in `tests/mocks/`
- Expected outputs in `tests/expected/`

### Coverage Requirements
- Minimum 80% code coverage
- All critical paths must be tested
- PDF extraction accuracy > 90%









