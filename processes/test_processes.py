import unittest
import pandas as pd
import json
from pathlib import Path
import tempfile
import shutil
from processes.company_list_handler import CompanyListHandler
from processes.esma_scraper import ESMAScraper
from unittest.mock import patch, MagicMock

class TestCompanyListHandler(unittest.TestCase):
    def setUp(self):
        """Create a temporary test environment"""
        self.test_dir = Path(tempfile.mkdtemp())
        
        # Create a test Excel file
        self.excel_path = self.test_dir / "test_companies.xlsx"
        self.create_test_excel()
        
        # Create output directory
        self.output_dir = self.test_dir / "results"
        self.output_dir.mkdir()
        
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir)
        
    def create_test_excel(self):
        """Create a test Excel file with sample data"""
        # Create test data with various edge cases
        data = {
            'GOGEL 2023 - Upstream': ['', '', 'Company Name', '', 'Test Company 1', 'Test Company 2', '', 'Test Company 3'],
            'Unnamed: 1': ['', '', 'Subsidiary Name', '', 'Sub 1', '', '', ''],
            'Unnamed: 2': ['', '', 'Country of Headquarters', '', 'Country 1', 'Country 2', '', 'Country 3']
        }
        df = pd.DataFrame(data)
        
        # Create Excel writer with the correct sheet name
        with pd.ExcelWriter(self.excel_path) as writer:
            df.to_excel(writer, sheet_name='Upstream', index=False)
        
    def test_load_companies(self):
        """Test company loading with various cases"""
        handler = CompanyListHandler(str(self.excel_path))
        
        # Check if companies were loaded correctly
        self.assertEqual(len(handler.companies), 3)
        self.assertIn('Test Company 1', handler.companies)
        self.assertIn('Test Company 2', handler.companies)
        self.assertIn('Test Company 3', handler.companies)
        
        # Check company info structure
        company1 = handler.companies['Test Company 1']
        self.assertEqual(company1['name'], 'Test Company 1')
        self.assertEqual(company1['subsidiary'], 'Sub 1')
        self.assertEqual(company1['country'], 'Country 1')
        
        # Check company with missing subsidiary
        company2 = handler.companies['Test Company 2']
        self.assertEqual(company2['subsidiary'], '')
        
    def test_progress_tracking(self):
        """Test progress tracking functionality"""
        handler = CompanyListHandler(str(self.excel_path))
        
        # Check initial state
        unprocessed = handler.get_unprocessed_companies()
        self.assertEqual(len(unprocessed), 3)
        
        # Mark one company as processed
        handler.mark_company_as_processed('Test Company 1')
        unprocessed = handler.get_unprocessed_companies()
        self.assertEqual(len(unprocessed), 2)
        
        # Save and load progress
        handler.save_progress(str(self.output_dir))
        
        # Create new handler and load progress
        new_handler = CompanyListHandler(str(self.excel_path))
        new_handler.load_progress(str(self.output_dir / 'company_progress.json'))
        
        # Check if progress was loaded correctly
        unprocessed = new_handler.get_unprocessed_companies()
        self.assertEqual(len(unprocessed), 2)  # Should be 2 since we marked one as processed
        
    def test_error_handling(self):
        """Test error handling for various scenarios"""
        # Test with non-existent Excel file
        with self.assertRaises(Exception):
            CompanyListHandler("nonexistent.xlsx")
            
        # Test with non-existent progress file
        handler = CompanyListHandler(str(self.excel_path))
        handler.load_progress("nonexistent.json")  # Should log warning but not raise
        
        # Test marking non-existent company
        handler.mark_company_as_processed("NonExistentCompany")  # Should not raise or mark
        
    def test_data_integrity(self):
        """Test data integrity and cleaning"""
        handler = CompanyListHandler(str(self.excel_path))
        
        # Check if empty or whitespace company names are excluded
        for company_name in handler.companies:
            self.assertTrue(company_name.strip())
            
        # Check if all required fields are present
        for company_info in handler.companies.values():
            self.assertIn('name', company_info)
            self.assertIn('subsidiary', company_info)
            self.assertIn('country', company_info)
            
class TestESMAScraper(unittest.TestCase):
    def setUp(self):
        """Create a temporary test environment"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.scraper = ESMAScraper(str(self.test_dir))  # Convert to string
        
    def tearDown(self):
        """Clean up test environment"""
        self.scraper.close()
        shutil.rmtree(self.test_dir)
        
    @patch('processes.esma_scraper.webdriver')
    def test_initialization(self, mock_webdriver):
        """Test scraper initialization"""
        scraper = ESMAScraper(str(self.test_dir))  # Convert to string
        self.assertTrue(mock_webdriver.Chrome.called)
        self.assertEqual(scraper.base_dir, str(self.test_dir))
        
        # Check if directories are created
        for dir_name in ['critical_pdfs', 'extracted_data', 'temp', 'metadata']:
            dir_path = self.test_dir / dir_name
            self.assertTrue(dir_path.exists())
            
    @patch('processes.esma_scraper.webdriver')
    def test_search_and_process(self, mock_webdriver):
        """Test search and process functionality"""
        # Mock the webdriver's find_element and find_elements methods
        mock_driver = MagicMock()
        mock_webdriver.Chrome.return_value = mock_driver
        
        # Mock search results
        mock_result1 = MagicMock()
        mock_result1.text = "Final Terms Document 1"
        mock_result1.get_attribute.return_value = "http://test.com/doc1.pdf"
        mock_result1.find_element.return_value.text = "2024-01-01"
        
        mock_result2 = MagicMock()
        mock_result2.text = "Some Other Document"
        mock_result2.get_attribute.return_value = "http://test.com/doc2.pdf"
        mock_result2.find_element.return_value.text = "2024-01-02"
        
        mock_driver.find_elements.return_value = [mock_result1, mock_result2]
        
        # Create scraper and test search
        scraper = ESMAScraper(str(self.test_dir))
        with patch('processes.esma_scraper.requests.get') as mock_get:
            # Mock successful PDF download
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {'content-type': 'application/pdf'}
            mock_get.return_value = mock_response
            
            results = scraper.search_and_process("Test Company")
            
            # Verify search was performed
            self.assertTrue(mock_driver.get.called)
            self.assertTrue(mock_driver.find_elements.called)
            
            # Verify results
            self.assertEqual(len(results), 1)  # Only Final Terms document
            self.assertEqual(results[0]['title'], "Final Terms Document 1")
        
    def test_is_final_terms(self):
        """Test Final Terms document detection"""
        test_cases = [
            ("Final Terms Document.pdf", True),
            ("Some Random Document.pdf", False),
            ("FINAL TERMS.PDF", True),
            ("final_terms_20240101.pdf", True),
            ("terms_and_conditions.pdf", False),
            ("Company Report Final Terms.pdf", True)
        ]
        
        for filename, expected in test_cases:
            result = self.scraper.is_final_terms(filename)
            self.assertEqual(result, expected, f"Failed for filename: {filename}")
            
    @patch('processes.esma_scraper.requests.get')
    def test_document_processing(self, mock_get):
        """Test document processing"""
        # Mock successful PDF download
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'application/pdf'}
        mock_get.return_value = mock_response
        
        # Test processing a document
        doc_info = {
            'url': 'http://test.com/document.pdf',
            'title': 'Test Final Terms',
            'date': '2024-01-01'
        }
        
        result = self.scraper.process_document_stream(doc_info)
        self.assertIsNotNone(result)
        self.assertEqual(result['url'], doc_info['url'])
        self.assertEqual(result['title'], doc_info['title'])
        self.assertEqual(result['date'], doc_info['date'])
        self.assertEqual(result['type'], 'Final Terms')
        
    def test_error_handling(self):
        """Test error handling in document processing"""
        # Test with invalid URL
        doc_info = {
            'url': 'invalid_url',
            'title': 'Test Document',
            'date': '2024-01-01'
        }
        
        result = self.scraper.process_document_stream(doc_info)
        self.assertIsNone(result)
        
if __name__ == '__main__':
    unittest.main() 