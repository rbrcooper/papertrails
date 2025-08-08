# Database Implementation for Bond Data

This document provides an overview of the database implementation for storing extracted bond data.

## Overview

The database implementation uses SQLite for simplicity and portability. It is designed to store:
- Bond metadata (dates, currency, coupon info)
- Document metadata (filename, path, company)
- Extraction metadata (confidence, validation status)

## Database Schema

The database consists of the following tables:

### Companies
- `id`: Primary key
- `name`: Company name
- `lei`: Legal Entity Identifier (optional)
- `created_at`: Timestamp of creation

### Documents
- `id`: Primary key
- `company_id`: Foreign key to companies
- `filename`: Name of the PDF file
- `file_path`: Path to the PDF file
- `document_type`: Type of document (e.g., 'bond_term_sheet')
- `extraction_date`: When the extraction was performed
- `extraction_status`: Status of extraction ('complete', 'partial', 'failed')
- `created_at`: Timestamp of creation

### Bonds
- `id`: Primary key
- `document_id`: Foreign key to documents
- `isin`: International Securities Identification Number
- `issue_date`: Date of bond issuance
- `maturity_date`: Date of bond maturity
- `issue_size`: Size of bond issue
- `currency`: Currency of bond
- `coupon_rate`: Interest rate
- `coupon_type`: Type of coupon (e.g., 'fixed', 'floating')
- `extraction_confidence`: Confidence score of extraction (0.0-1.0)
- `validation_status`: Status of validation ('unverified', 'verified', 'rejected')
- `created_at`: Timestamp of creation

### Banks
- `id`: Primary key
- `name`: Raw bank name from document
- `standard_name`: Standardized bank name
- `created_at`: Timestamp of creation

### Bond-Banks (Many-to-Many)
- `bond_id`: Foreign key to bonds
- `bank_id`: Foreign key to banks
- `role`: Role of bank (e.g., 'bookrunner', 'manager')
- `confidence`: Confidence score of extraction (0.0-1.0)
- `created_at`: Timestamp of creation

## Usage

### Storing Extraction Results

```python
from processes.database_handler import DatabaseHandler

# Initialize database handler
db = DatabaseHandler()

# Example extraction result
result = {
    "filename": "example.pdf",
    "file_path": "data/pdfs/example.pdf",
    "document_type": "bond_term_sheet",
    "metadata": {
        "isin": "XS1234567890",
        "issue_date": "2023-01-15",
        "maturity_date": "2028-01-15",
        "issue_size": 500000000,
        "currency": "EUR",
        "coupon_rate": 4.25,
        "coupon_type": "fixed",
        "extraction_confidence": 0.85
    },
    "extracted_banks": [
        {
            "raw_name": "Example Bank AG",
            "standard_name": "Example Bank",
            "role": "bookrunner",
            "confidence": 0.9
        }
    ]
}

# Store the result
db.store_extraction_result("Example Company", result)
```

### Retrieving Bond Data

```python
# Get all bonds for a company
bonds = db.get_company_bonds("Example Company")

# Get detailed information about a specific bond
bond_details = db.get_bond_details(bond_id)

# Update validation status
db.update_bond_validation(bond_id, "verified", 1.0)

# Get database statistics
stats = db.get_stats()
```

## Testing

A test script is provided to verify the database implementation:

```
python test_database.py
```

This script:
1. Creates a test database
2. Inserts sample data
3. Retrieves and verifies the data
4. Updates validation status
5. Displays database statistics 