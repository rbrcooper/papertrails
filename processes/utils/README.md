# Bank Name Standardizer

A utility for standardizing bank names using exact and fuzzy matching against a dictionary of known bank names and their variations.

## Features

- Exact and fuzzy matching of bank names
- Confidence scoring for matches
- Support for handling common variations in bank names
- Robust cleaning of suffixes, prefixes, and punctuation
- Utility functions for building and maintaining the bank names dictionary
- Country information for disambiguation

## Usage

### Basic Usage

```python
from processes.utils.bank_standardizer import BankStandardizer

# Initialize the standardizer
standardizer = BankStandardizer()

# Standardize a bank name
result = standardizer.standardize("JPMorgan Chase & Co")
if result:
    standard_name, confidence = result
    print(f"Standardized to: {standard_name} (confidence: {confidence:.2f})")
else:
    print("No match found")
```

### Adding a New Bank

```python
standardizer.add_bank(
    key="credit agricole",
    standard_name="Credit Agricole",
    aliases=["credit agricole", "crédit agricole", "ca-cib", "credit agricole cib"],
    country="France"
)
```

### Extracting Bank Names from Results

```python
# Extract unique bank names from previous extraction results
bank_names = BankStandardizer.extract_bank_names_from_results("data/extraction_results.json")
print(f"Found {len(bank_names)} unique bank names")
```

### Building a Bank Dictionary

```python
# Build a dictionary from a list of raw bank names
raw_names = ["HSBC Holdings", "HSBC Bank", "UBS AG", "UBS Limited"]
bank_dict = standardizer.build_bank_dictionary(raw_names)

# Save the dictionary to a file
with open("data/new_banks.json", "w") as f:
    json.dump(bank_dict, f, indent=2)
```

## Configuration

The standardizer uses a JSON file with bank name mappings. The default path is `data/bank_names.json`, but you can specify a different path when initializing the standardizer:

```python
standardizer = BankStandardizer(bank_names_file="path/to/your/bank_names.json")
```

### Bank Names JSON Format

```json
{
  "bank_key": {
    "standard_name": "Standard Bank Name",
    "aliases": ["alias1", "alias2", "alias3"],
    "country": "Country"
  }
}
```

## Requirements

- Python 3.7+
- fuzzywuzzy
- python-Levenshtein (optional, for better performance)

## Integration with PDF Extraction

This utility is integrated with the PDF extraction pipeline through the `BankExtractor` class in `processes/pdf_extraction/extractors/bank_extractor.py`. The integration provides more robust standardization of bank names extracted from documents.

### Integration Details

- `BankExtractor` initializes a `BankStandardizer` instance during initialization
- After extracting raw bank names, the extractor uses the standardizer to normalize bank names
- Standardized names are stored alongside raw names in the extraction results
- Confidence scores from the standardizer are included in the output
- The standardized names are used for deduplication and role association

### Example Extraction Output

With the integration, the bank extraction results now contain more detailed information:

```json
{
  "extracted_banks": [
    {
      "standard_name": "BNP Paribas",
      "raw_name": "BNP Paribas Securities",
      "confidence": 1.0,
      "roles": ["joint lead manager"]
    },
    {
      "standard_name": "Deutsche Bank AG",
      "raw_name": "Deutsche Bank AG",
      "confidence": 1.0,
      "roles": ["joint lead manager"]
    }
  ]
}
```

### Benefits of Integration

1. **Consistent Bank Names**: The same bank will have the same standardized name across all documents, regardless of how it appears in the original text
2. **Improved Bank Relationships**: More accurate tracking of bank roles across different bond issuances
3. **Better Data Quality**: Confidence scores help identify potential misidentifications
4. **Enhanced Analysis**: Standardized names enable more accurate aggregation and analysis of bank relationships

## Testing

Run the included test scripts to verify functionality:

```
python processes/utils/test_bank_standardizer.py
python processes/tests/test_bank_integration.py 