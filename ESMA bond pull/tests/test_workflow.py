import unittest
from pathlib import Path
import json
import tempfile
import shutil
from datetime import datetime

from workflow import ESMAWorkflow
from process_manager import ProcessManager
from pdf_processor import PDFProcessor
from database.db_manager import DatabaseManager

class TestESMAWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        # Create temporary directories for testing
        cls.temp_dir = Path(tempfile.mkdtemp())
        cls.pdf_dir = cls.temp_dir / "pdfs"
        cls.financial_data_dir = cls.temp_dir / "financial_data"
        cls.pdf_dir.mkdir()
        cls.financial_data_dir.mkdir()
        
        # Load test configuration
        with open("config/test_config.json", "r") as f:
            cls.test_config = json.load(f)
            
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment"""
        shutil.rmtree(cls.temp_dir)
        
    def setUp(self):
        """Set up for each test"""
        self.workflow = ESMAWorkflow()
        self.process_manager = ProcessManager()
        self.pdf_processor = PDFProcessor()
        self.db = DatabaseManager()
        
    def test_workflow_initialization(self):
        """Test workflow initialization"""
        self.workflow.initialize()
        self.assertIsNotNone(self.workflow.driver)
        self.assertEqual(self.workflow.workflow_status["status"], "running")
        
    def test_company_processing(self):
        """Test processing of a single company"""
        company = {
            "name": "TotalEnergies",
            "lei": "549300GXQGKXQJK5QF55",
            "industry": "Oil and Gas",
            "country": "France"
        }
        
        result = self.process_manager.process_company(company)
        self.assertIsNotNone(result)
        self.assertTrue(result["success"])
        
    def test_bond_data_collection(self):
        """Test bond data collection"""
        lei = "549300GXQGKXQJK5QF55"
        bonds = self.process_manager.collect_bond_data(lei)
        
        self.assertIsInstance(bonds, list)
        if bonds:  # If any bonds found
            bond = bonds[0]
            required_fields = self.test_config["validation_rules"]["required_fields"]
            for field in required_fields:
                self.assertIn(field, bond)
                
    def test_pdf_processing(self):
        """Test PDF download and processing"""
        test_url = "https://example.com/test.pdf"
        test_isin = "TEST123456789"
        test_doc_name = "test_document"
        
        result = self.pdf_processor.download_document(
            test_url,
            test_isin,
            test_doc_name
        )
        
        self.assertIsInstance(result, Path)
        self.assertTrue(result.exists())
        
    def test_data_validation(self):
        """Test data validation rules"""
        test_bond = {
            "isin": "TEST123456789",
            "issuer_name": "Test Company",
            "issue_date": "2023-01-01",
            "maturity_date": "2025-01-01",
            "currency": "EUR",
            "coupon_rate": 5.0,
            "face_value": 1000
        }
        
        validation_result = self.process_manager.validate_bond_data(test_bond)
        self.assertTrue(validation_result["valid"])
        
    def test_error_handling(self):
        """Test error handling and recovery"""
        # Test with invalid LEI
        invalid_lei = "INVALID_LEI"
        result = self.process_manager.collect_bond_data(invalid_lei)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)
        
    def test_database_integrity(self):
        """Test database operations and integrity"""
        test_data = {
            "issuer_name": "Test Company",
            "lei": "TEST123456789",
            "industry": "Test Industry",
            "country": "Test Country"
        }
        
        # Test insert
        issuer_id = self.db.insert_issuer(test_data)
        self.assertIsNotNone(issuer_id)
        
        # Test retrieve
        retrieved = self.db.get_issuer(issuer_id)
        self.assertEqual(retrieved["name"], test_data["issuer_name"])
        
        # Test update
        updated_data = {"industry": "Updated Industry"}
        self.db.update_issuer(issuer_id, updated_data)
        retrieved = self.db.get_issuer(issuer_id)
        self.assertEqual(retrieved["industry"], updated_data["industry"])
        
        # Test delete
        self.db.delete_issuer(issuer_id)
        retrieved = self.db.get_issuer(issuer_id)
        self.assertIsNone(retrieved)

if __name__ == '__main__':
    unittest.main() 