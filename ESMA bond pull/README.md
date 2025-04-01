# ESMA Bond Data Collection

This project is designed to collect and process bond issuance data from the European Securities and Markets Authority (ESMA) website for specific companies.

## Features

- Automated data collection from ESMA website
- PDF document download and storage
- Database storage using SQLAlchemy
- Support for multiple companies
- Robust error handling and logging
- Data validation and cleaning

## Project Structure

```
ESMA bond pull/
├── config/
│   └── settings.py         # Configuration settings
├── database/
│   ├── models.py          # SQLAlchemy models
│   └── db_manager.py      # Database operations
├── utils/
│   └── helpers.py         # Utility functions
├── data/
│   ├── pdfs/              # Downloaded PDF files
│   └── financial_data/    # Processed data files
├── main.py                # Main execution script
├── requirements.txt       # Project dependencies
└── README.md             # Project documentation
```

## Prerequisites

- Python 3.8 or higher
- Chrome WebDriver
- SQLite database

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ESMA-bond-pull
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up Chrome WebDriver:
- Download Chrome WebDriver matching your Chrome browser version
- Add the WebDriver to your system PATH or specify its location in the settings

## Configuration

The project can be configured through the following methods:

1. Environment variables:
```bash
export CHROME_DRIVER_PATH=/path/to/chromedriver
```

2. Settings file (`config/settings.py`):
- Modify company information
- Adjust timeouts and retry settings
- Configure file paths

## Usage

1. Run the main script:
```bash
python main.py
```

2. The script will:
- Initialize the database
- Collect bond data for configured companies
- Download and store PDF documents
- Process and validate the data
- Save results to the database

## Data Storage

### Database Schema

- Issuers: Company information
- Bonds: Bond issuance details
- Documents: PDF documents and metadata
- Underwriters: Underwriter information

### File Storage

- PDFs are stored in `data/pdfs/<isin>/`
- Processed data is saved in `data/financial_data/`

## Error Handling

The project includes comprehensive error handling:
- Web scraping errors
- Database operations
- File processing
- Data validation

All errors are logged to `esma_scraper.log`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 