# ESMA Document File Organizer

A utility for organizing and managing PDF documents downloaded from the ESMA (European Securities and Markets Authority) website.

## Features

- Automatically organizes loose PDFs into company-specific folders
- Implements a consistent naming scheme: `{company_name}/{document_type}_{date}_{hash}.pdf`
- Detects document types (base prospectus, final terms, supplements, etc.)
- Extracts dates from document content or filenames
- Identifies company names from document content
- Prevents duplicate files through content hash comparison
- Provides detailed logging for auditing file operations
- Supports dry-run mode for testing before actual file moves

## Usage

### Command Line Usage

To organize files using the command line:

```bash
# Dry run (preview changes without moving files)
python -m processes.main --organize-only --dry-run

# Actually organize files
python -m processes.main --organize-only

# Include file organization after scraping
python -m processes.main --organize-files
```

### Running the Test Suite

```bash
# Run test suite
python processes/utils/test_file_organizer.py
```

### Python API

```python
from processes.utils.file_organizer import FileOrganizer

# Initialize with default settings
organizer = FileOrganizer()

# Initialize with custom settings
organizer = FileOrganizer(
    downloads_dir="custom/download/path",
    log_file="custom/log/path.log",
    dry_run=True,  # Don't actually move files
    max_workers=4  # Number of parallel workers
)

# Run organization process
stats = organizer.organize_files()

# Show statistics
print(f"Total files: {stats['total_files']}")
print(f"Organized files: {stats['organized_files']}")
print(f"Skipped files: {stats['skipped_files']}")
print(f"Error files: {stats['error_files']}")

# Process a single file
success, new_path = organizer.organize_file(Path("path/to/file.pdf"))
```

## Document Type Detection

The organizer automatically detects the following document types:

- `base_prospectus`: Base prospectuses, debt issuance programmes
- `final_terms`: Final terms, term sheets, pricing supplements
- `supplement`: Supplements to base prospectuses
- `annual_report`: Annual financial reports
- `quarterly_report`: Quarterly financial reports
- `unknown`: Documents that don't match known types

## Directory Structure

The organizer creates a directory structure like this:

```
data/downloads/
├── Company A/
│   ├── base_prospectus_20240101_abcd1234.pdf
│   ├── final_terms_20240215_efgh5678.pdf
│   └── supplement_20240301_ijkl9012.pdf
├── Company B/
│   ├── base_prospectus_20230601_mnop3456.pdf
│   └── final_terms_20230715_qrst7890.pdf
└── Unidentified/
    └── unknown_20240401_uvwx1234.pdf
```

## Dependencies

- PyMuPDF (fitz): PDF processing
- pathlib: Path handling
- concurrent.futures: Parallel processing (built into Python 3)
- Optional: pytesseract and Tesseract OCR for text extraction from images

## Troubleshooting

- **"Failed to calculate hash for file"**: The file may be corrupted or inaccessible
- **"Unable to identify company for file"**: The company name couldn't be detected; file will be moved to Unidentified folder
- **"Document type detection failed"**: The document type couldn't be determined; will use "unknown" type 