import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import json
import pandas as pd
import sys
from pathlib import Path

# Add the parent directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from config.settings import FINANCIAL_DATA_DIR

def setup_logging(name: str) -> logging.Logger:
    """Set up logging configuration"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Create handlers
    file_handler = logging.FileHandler("esma_scraper.log")
    console_handler = logging.StreamHandler()
    
    # Create formatters and add it to handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def save_json(data: Dict[str, Any], filename: str) -> None:
    """Save data to a JSON file"""
    filepath = FINANCIAL_DATA_DIR / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_json(filename: str) -> Dict[str, Any]:
    """Load data from a JSON file"""
    filepath = FINANCIAL_DATA_DIR / filename
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_excel(data: list, filename: str) -> None:
    """Save data to an Excel file"""
    filepath = FINANCIAL_DATA_DIR / filename
    df = pd.DataFrame(data)
    df.to_excel(filepath, index=False)

def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string to datetime object"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        try:
            return datetime.strptime(date_str, "%d/%m/%Y")
        except ValueError:
            return None

def format_date(date: datetime) -> str:
    """Format datetime object to string"""
    return date.strftime("%Y-%m-%d")

def clean_text(text: str) -> str:
    """Clean text by removing extra whitespace and special characters"""
    if not text:
        return ""
    return " ".join(text.split())

def validate_required_fields(data: Dict[str, Any], required_fields: list) -> bool:
    """Validate that all required fields are present in the data"""
    return all(field in data for field in required_fields)

def get_file_size(filepath: Path) -> int:
    """Get file size in bytes"""
    return filepath.stat().st_size

def is_valid_pdf(filepath: Path) -> bool:
    """Check if file is a valid PDF"""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(4)
            return header.startswith(b'%PDF')
    except Exception:
        return False 