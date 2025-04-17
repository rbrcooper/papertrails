"""
Mock ESMA Scraper
----------------
A mock implementation of the ESMA scraper for testing purposes.
This avoids the need for a real browser and network connections.
"""

import os
import time
import json
import random
import logging
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

class MockESMAScraper:
    """Mock implementation of ESMAScraper for testing"""
    
    def __init__(self, download_dir=None, debug_mode=True, headless=True):
        """Initialize the mock scraper"""
        self.logger = logging.getLogger(__name__)
        
        # Set download directory
        if download_dir:
            self.download_dir = Path(download_dir)
        else:
            self.download_dir = Path("data/test_downloads")
            
        # Create download directory if it doesn't exist
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuration
        self.debug_mode = debug_mode
        self.headless = headless
        
        # Sample test data
        self.test_data = {
            "TotalEnergies SE": self._generate_totalenergies_documents(),
            "Aker BP ASA": self._generate_akerbp_documents(),
            "MEDIOBANCA": self._generate_mediobanca_documents(),
            # Add fallback data for any other company
            "default": self._generate_default_documents()
        }
        
        self.logger.info(f"Mock ESMA Scraper initialized with {len(self.test_data)} test data sets")
    
    def _generate_totalenergies_documents(self) -> List[Dict[str, Any]]:
        """Generate test documents for TotalEnergies"""
        return [
            {
                "id": hashlib.md5(f"https://example.com/doc1".encode()).hexdigest(),
                "url": "https://example.com/doc1",
                "issuer": "TotalEnergies SE",
                "type": "Base Prospectus",
                "date": "2023-05-15",
                "language": "EN"
            },
            {
                "id": hashlib.md5(f"https://example.com/doc2".encode()).hexdigest(),
                "url": "https://example.com/doc2",
                "issuer": "TotalEnergies SE",
                "type": "Final Terms",
                "date": "2023-06-22",
                "language": "EN"
            },
            {
                "id": hashlib.md5(f"https://example.com/doc3".encode()).hexdigest(),
                "url": "https://example.com/doc3",
                "issuer": "TotalEnergies SE",
                "type": "Supplement",
                "date": "2023-07-30",
                "language": "EN"
            },
            {
                "id": hashlib.md5(f"https://example.com/doc4".encode()).hexdigest(),
                "url": "https://example.com/doc4",
                "issuer": "TotalEnergies SE",
                "type": "Final Terms",
                "date": "2023-08-14",
                "language": "FR"
            },
            {
                "id": hashlib.md5(f"https://example.com/doc5".encode()).hexdigest(),
                "url": "https://example.com/doc5",
                "issuer": "TotalEnergies SE",
                "type": "Key Information Document",
                "date": "2023-09-05",
                "language": "EN"
            },
            {
                "id": hashlib.md5(f"https://example.com/doc6".encode()).hexdigest(),
                "url": "https://example.com/doc6",
                "issuer": "TotalEnergies SE",
                "type": "Final Terms",
                "date": "2023-10-12",
                "language": "EN"
            },
            {
                "id": hashlib.md5(f"https://example.com/doc7".encode()).hexdigest(),
                "url": "https://example.com/doc7",
                "issuer": "TotalEnergies SE",
                "type": "Base Prospectus",
                "date": "2024-01-20",
                "language": "EN"
            }
        ]
    
    def _generate_akerbp_documents(self) -> List[Dict[str, Any]]:
        """Generate test documents for Aker BP"""
        return [
            {
                "id": hashlib.md5(f"https://example.com/aker1".encode()).hexdigest(),
                "url": "https://example.com/aker1",
                "issuer": "Aker BP ASA",
                "type": "Base Prospectus",
                "date": "2023-04-10",
                "language": "EN"
            },
            {
                "id": hashlib.md5(f"https://example.com/aker2".encode()).hexdigest(),
                "url": "https://example.com/aker2",
                "issuer": "Aker BP ASA",
                "type": "Final Terms",
                "date": "2023-05-18",
                "language": "EN"
            },
            {
                "id": hashlib.md5(f"https://example.com/aker3".encode()).hexdigest(),
                "url": "https://example.com/aker3",
                "issuer": "Aker BP ASA",
                "type": "Key Information Document",
                "date": "2023-07-25",
                "language": "EN"
            }
        ]
    
    def _generate_mediobanca_documents(self) -> List[Dict[str, Any]]:
        """Generate test documents for MEDIOBANCA"""
        return [
            {
                "id": hashlib.md5(f"https://example.com/medio1".encode()).hexdigest(),
                "url": "https://example.com/medio1",
                "issuer": "MEDIOBANCA",
                "type": "Base Prospectus",
                "date": "2023-03-22",
                "language": "IT"
            },
            {
                "id": hashlib.md5(f"https://example.com/medio2".encode()).hexdigest(),
                "url": "https://example.com/medio2",
                "issuer": "MEDIOBANCA",
                "type": "Final Terms",
                "date": "2023-04-15",
                "language": "EN"
            },
            {
                "id": hashlib.md5(f"https://example.com/medio3".encode()).hexdigest(),
                "url": "https://example.com/medio3",
                "issuer": "MEDIOBANCA",
                "type": "Supplement",
                "date": "2023-06-10",
                "language": "IT"
            },
            {
                "id": hashlib.md5(f"https://example.com/medio4".encode()).hexdigest(),
                "url": "https://example.com/medio4",
                "issuer": "MEDIOBANCA",
                "type": "Key Information Document",
                "date": "2023-08-05",
                "language": "EN"
            }
        ]
    
    def _generate_default_documents(self) -> List[Dict[str, Any]]:
        """Generate default test documents for any company not specifically defined"""
        return [
            {
                "id": hashlib.md5(f"https://example.com/default1".encode()).hexdigest(),
                "url": "https://example.com/default1",
                "issuer": "Generic Company",
                "type": "Base Prospectus",
                "date": "2023-05-10",
                "language": "EN"
            },
            {
                "id": hashlib.md5(f"https://example.com/default2".encode()).hexdigest(),
                "url": "https://example.com/default2",
                "issuer": "Generic Company",
                "type": "Final Terms",
                "date": "2023-06-15",
                "language": "EN"
            }
        ]
    
    def search_documents(self, company_name: str) -> List[Dict[str, Any]]:
        """
        Mock implementation of search_documents that returns predefined test data.
        
        Args:
            company_name: The name of the company to search for
            
        Returns:
            A list of dictionaries containing document metadata
        """
        self.logger.info(f"Mock searching for documents related to: {company_name}")
        
        # Simulate some processing time
        time.sleep(random.uniform(0.5, 1.5))
        
        # Return test data for the company or default if not found
        documents = self.test_data.get(company_name, self.test_data["default"])
        
        # Replace issuer with actual company name for default documents
        if company_name not in self.test_data:
            for doc in documents:
                doc["issuer"] = company_name
        
        self.logger.info(f"Found {len(documents)} mock documents for {company_name}")
        return documents
    
    def download_document(self, url: str, doc_id: str = None) -> Optional[str]:
        """
        Mock implementation of download_document that creates a fake PDF file.
        
        Args:
            url: The URL to download the document from
            doc_id: Optional document ID for naming
            
        Returns:
            The path to the downloaded file or None if download fails
        """
        self.logger.info(f"Mock downloading document: {doc_id or url}")
        
        # Simulate some processing time
        time.sleep(random.uniform(1.0, 2.5))
        
        try:
            # Generate a filename if doc_id is not provided
            if not doc_id:
                doc_id = hashlib.md5(url.encode()).hexdigest()
                
            # Determine the output path
            output_path = self.download_dir / f"{doc_id}.pdf"
            
            # Check if file already exists
            if output_path.exists():
                self.logger.info(f"Document already exists at {output_path}")
                return str(output_path)
            
            # Create a temporary file path to avoid file access conflicts
            temp_path = self.download_dir / f"temp_{doc_id}.pdf"
            
            # Create a mock PDF file (just a text file with .pdf extension)
            with open(temp_path, 'w') as f:
                f.write(f"Mock PDF document for {url}\n")
                f.write(f"Created at: {datetime.now().isoformat()}\n")
                f.write(f"Document ID: {doc_id}\n")
                f.write("This is a mock PDF file for testing purposes.\n")
            
            # Make sure the file is closed properly before renaming
            time.sleep(0.1)
            
            # Rename to final path, only if it doesn't exist yet (to avoid conflicts)
            if not output_path.exists():
                try:
                    # Use os.replace which is atomic on most platforms
                    import os
                    os.replace(str(temp_path), str(output_path))
                except Exception as e:
                    self.logger.error(f"Error renaming file: {str(e)}")
                    if temp_path.exists() and not output_path.exists():
                        # Try traditional rename as fallback
                        temp_path.rename(output_path)
            else:
                # If the file already exists (race condition), just remove the temp file
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except Exception:
                        pass
            
            self.logger.info(f"Mock document successfully saved to {output_path}")
            return str(output_path)
                
        except Exception as e:
            self.logger.error(f"Error creating mock document {doc_id or url}: {str(e)}")
            return None
    
    def close(self):
        """Mock close method"""
        self.logger.info("Mock scraper closed")
        
    def random_delay(self, min_delay=None, max_delay=None):
        """Mock random delay method"""
        min_d = min_delay if min_delay is not None else 0.1
        max_d = max_delay if max_delay is not None else 0.5
        time.sleep(random.uniform(min_d, max_d))
        
    def take_screenshot(self, filename):
        """Mock screenshot method"""
        self.logger.debug(f"Mock screenshot: {filename}")
        
    def save_page_source(self, filename):
        """Mock page source save method"""
        self.logger.debug(f"Mock page source save: {filename}") 