from pathlib import Path
import os
import json

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PDF_DIR = DATA_DIR / "pdfs"
FINANCIAL_DATA_DIR = DATA_DIR / "financial_data"

# Create directories if they don't exist
for directory in [DATA_DIR, PDF_DIR, FINANCIAL_DATA_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Database settings
DATABASE_URL = f"sqlite:///{BASE_DIR}/esma_bonds.db"

# ESMA website settings
ESMA_BASE_URL = "https://registers.esma.europa.eu/solr/esma_registers"
ESMA_SEARCH_URL = f"{ESMA_BASE_URL}/fir_details/select"
ESMA_DOC_URL = f"{ESMA_BASE_URL}/fir_documents/select"

# Web scraping settings
CHROME_DRIVER_PATH = os.getenv("CHROME_DRIVER_PATH", "chromedriver")
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
PAGE_LOAD_TIMEOUT = 30  # seconds
ELEMENT_TIMEOUT = 10  # seconds

# PDF processing settings
PDF_PROCESSING_TIMEOUT = 300  # seconds
MAX_PDF_SIZE = 50 * 1024 * 1024  # 50MB

# Logging settings
LOG_LEVEL = "DEBUG"  # Changed to DEBUG for more detailed logging
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = BASE_DIR / "esma_scraper.log"

# Load companies from JSON file
try:
    with open(BASE_DIR / "config" / "companies.json", "r") as f:
        companies_data = json.load(f)
        COMPANIES = {company["name"]: {
            "lei": company["lei"],
            "country": company["country"],
            "industry": company["industry"]
        } for company in companies_data["companies"]}
except Exception as e:
    print(f"Warning: Could not load companies.json: {e}")
    # Fallback to default companies
    COMPANIES = {
        "TotalEnergies": {
            "lei": "969500TZFM9XZWXG9N31",
            "country": "FR",
            "industry": "Oil and Gas"
        },
        "Glencore": {
            "lei": "213800Z8N5UJPOALKQ05",
            "country": "CH",
            "industry": "Mining and Commodities"
        },
        "Repsol": {
            "lei": "549300GXQGKXQJK5QF55",
            "country": "ES",
            "industry": "Oil and Gas"
        },
        "Eni": {
            "lei": "549300GXQGKXQJK5QF55",
            "country": "IT",
            "industry": "Oil and Gas"
        },
        "Equinor": {
            "lei": "549300GXQGKXQJK5QF55",
            "country": "NO",
            "industry": "Oil and Gas"
        }
    }

# Document types
DOCUMENT_TYPES = {
    "FINAL_TERMS": "Final Terms",
    "PROSPECTUS": "Prospectus",
    "SUPPLEMENT": "Prospectus Supplement",
    "OTHER": "Other"
}

# Data validation settings
REQUIRED_BOND_FIELDS = [
    "isin",
    "name",
    "issuer_id",
    "issue_date",
    "maturity_date",
    "currency",
    "nominal_amount"
]

REQUIRED_ISSUER_FIELDS = [
    "name",
    "lei",
    "country"
]

REQUIRED_UNDERWRITER_FIELDS = [
    "name",
    "lei",
    "country"
] 