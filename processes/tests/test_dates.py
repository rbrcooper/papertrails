import sys
from pathlib import Path

# Add project root to sys.path to allow importing from processes
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from processes.pdf_extractor import PDFExtractor

def test_date_extraction():
    # Sample text with various date formats
    sample_texts = [
        """
        Issue Date: 15/04/2022
        Maturity Date: 15/04/2027
        """,
        
        """
        Date of Issue: 15 April 2022
        Final Maturity: 15 April 2027
        """,
        
        """
        Issuance Date: 2022-04-15
        Redemption Date: 2027-04-15
        """,
        
        """
        Issue Date: 15th April, 2022
        Maturity Date: 15th April, 2027
        """
    ]
    
    extractor = PDFExtractor()
    
    print("===== Date Extraction Test =====")
    for i, text in enumerate(sample_texts, 1):
        print(f"\nTest {i}:")
        print(f"Input Text:\n{text}")
        
        date_info = extractor._extract_dates(text)
        print(f"Extracted Dates: {date_info}")

if __name__ == "__main__":
    test_date_extraction() 