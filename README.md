# BlackRock Holdings Tracker

A Python tool to collect and analyze BlackRock's latest 13F holdings data.

## Features
- Fetches latest and previous 13F filings from BlackRock
- Extracts complete holdings data
- Calculates position changes
- Generates portfolio metrics
- Saves data in JSON format

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Run the main script to collect and process data:
```bash
python blackrock_collector.py
```

This will:
- Fetch the latest 13F filings
- Process the holdings data
- Calculate changes and metrics
- Save the results to `blackrock_holdings.json`

2. Run tests:
```bash
python -m unittest test_collector.py
```

## Output Format

The script generates a JSON file with the following structure:
```json
{
    "filing_info": {
        "filing_date": "YYYY-MM-DD",
        "reporting_date": "YYYY-MM-DD",
        "total_value": 1234567890
    },
    "holdings": [
        {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "shares": 1000000,
            "value": 175000000,
            "filing_date": "YYYY-MM-DD"
        }
    ],
    "changes": {
        "new_positions": [...],
        "exited_positions": [...],
        "significant_changes": [...]
    },
    "portfolio_metrics": {
        "total_positions": 250,
        "top_10_holdings": [...],
        "total_value": 1234567890
    }
}
```

## Error Handling

The script includes comprehensive error handling and logging. All operations are logged to help track the data collection process and identify any issues.

## Future Enhancements
- Add database storage
- Implement API endpoints
- Add more analytics
- Include sector analysis
- Add visualization capabilities 