"""
Shared Test Utilities
====================
Common utilities and fixtures for testing.
Consolidates shared functionality from multiple test files.
"""

import sys
import os
import tempfile
import shutil
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Add project root to sys.path to allow importing from processes
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))


class TestDataGenerator:
    """Generate test data for various testing scenarios."""
    
    @staticmethod
    def create_sample_extraction_result(company_name: str = "Test Company", 
                                       include_banks: bool = True) -> Dict[str, Any]:
        """Create a sample extraction result for testing."""
        result = {
            'filename': 'test_document.pdf',
            'file_path': '/path/to/test_document.pdf',
            'document_type': 'bond_term_sheet',
            'metadata': {
                'isin': 'TEST123456789',
                'issue_date': '2023-01-15',
                'maturity_date': '2028-01-15',
                'issue_size': 1000000,
                'currency': 'EUR',
                'coupon_rate': 3.5,
                'coupon_type': 'fixed',
                'extraction_confidence': 0.8
            },
            'validation_flags': [],
            'extracted_banks': [],
            'bank_sections': {}
        }
        
        if include_banks:
            result['extracted_banks'] = [
                {
                    'raw_name': 'Test Bank AG',
                    'standard_name': 'Test Bank',
                    'role': 'bookrunner',
                    'confidence': 0.9
                },
                {
                    'raw_name': 'Another Bank Ltd',
                    'standard_name': 'Another Bank',
                    'role': 'co-manager',
                    'confidence': 0.8
                }
            ]
            
            result['bank_sections'] = {
                'managers': 'Test Bank AG\nAnother Bank Ltd',
                'contact_info': 'Contact information for banks'
            }
        
        return result
    
    @staticmethod
    def create_sample_pdf_text(include_dates: bool = True, include_currency: bool = True,
                              include_banks: bool = True) -> str:
        """Create sample PDF text content for testing extractors."""
        text_parts = []
        
        if include_dates:
            text_parts.append("""
            ISSUE DATE: 15 January 2023
            MATURITY DATE: 15 January 2028
            Settlement Date: 17 January 2023
            """)
        
        if include_currency:
            text_parts.append("""
            ISSUE SIZE: EUR 1,000,000,000
            Currency: Euro (EUR)
            Denomination: EUR 1,000
            """)
        
        if include_banks:
            text_parts.append("""
            BOOKRUNNERS:
            Deutsche Bank AG
            J.P. Morgan Securities plc
            
            CO-MANAGERS:
            Barclays Bank PLC
            BNP Paribas
            """)
        
        return "\n".join(text_parts)
    
    @staticmethod
    def create_test_company_data() -> Dict[str, List[str]]:
        """Create test company data structure for batch testing."""
        return {
            "Test Company A": [
                "/path/to/company_a_doc1.pdf",
                "/path/to/company_a_doc2.pdf"
            ],
            "Test Company B": [
                "/path/to/company_b_doc1.pdf"
            ],
            "Test Company C": [
                "/path/to/company_c_doc1.pdf",
                "/path/to/company_c_doc2.pdf",
                "/path/to/company_c_doc3.pdf"
            ]
        }


class TestFileManager:
    """Manage temporary files and directories for testing."""
    
    def __init__(self):
        self.temp_dirs = []
        self.temp_files = []
    
    def create_temp_dir(self, prefix: str = "test_") -> str:
        """Create a temporary directory."""
        temp_dir = tempfile.mkdtemp(prefix=prefix)
        self.temp_dirs.append(temp_dir)
        return temp_dir
    
    def create_temp_file(self, content: str = "", suffix: str = ".txt", prefix: str = "test_") -> str:
        """Create a temporary file with content."""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix=prefix)
        temp_file.write(content.encode())
        temp_file.close()
        self.temp_files.append(temp_file.name)
        return temp_file.name
    
    def create_temp_json_file(self, data: Dict, prefix: str = "test_") -> str:
        """Create a temporary JSON file."""
        content = json.dumps(data, indent=2)
        return self.create_temp_file(content, ".json", prefix)
    
    def create_test_pdf_directory(self, file_count: int = 3) -> str:
        """Create a directory with dummy PDF files for testing."""
        test_dir = self.create_temp_dir("test_pdfs_")
        
        for i in range(file_count):
            # Create dummy PDF files (just empty files with .pdf extension)
            pdf_path = os.path.join(test_dir, f"test_document_{i+1}.pdf")
            with open(pdf_path, 'w') as f:
                f.write(f"Dummy PDF content for document {i+1}")
        
        return test_dir
    
    def cleanup(self):
        """Clean up all temporary files and directories."""
        # Remove temporary files
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except Exception as e:
                logging.warning(f"Failed to remove temp file {temp_file}: {e}")
        
        # Remove temporary directories
        for temp_dir in self.temp_dirs:
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            except Exception as e:
                logging.warning(f"Failed to remove temp dir {temp_dir}: {e}")
        
        self.temp_files = []
        self.temp_dirs = []
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup()


class TestLogger:
    """Standardized logging setup for tests."""
    
    @staticmethod
    def setup_test_logger(name: str, debug: bool = False) -> logging.Logger:
        """Set up a logger for testing."""
        level = logging.DEBUG if debug else logging.INFO
        
        # Create logger
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # Remove existing handlers to avoid duplicates
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(console_handler)
        
        return logger


class TestValidator:
    """Common validation utilities for test results."""
    
    @staticmethod
    def validate_extraction_result(result: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate that an extraction result has the expected structure."""
        errors = []
        
        # Check required top-level fields
        required_fields = ['filename', 'file_path', 'metadata', 'validation_flags']
        for field in required_fields:
            if field not in result:
                errors.append(f"Missing required field: {field}")
        
        # Check metadata structure
        if 'metadata' in result:
            metadata = result['metadata']
            expected_metadata_fields = ['issue_date', 'maturity_date', 'currency', 'issue_size']
            for field in expected_metadata_fields:
                if field not in metadata:
                    # Not an error, but note missing optional fields
                    pass
        
        # Check validation flags is a list
        if 'validation_flags' in result and not isinstance(result['validation_flags'], list):
            errors.append("validation_flags should be a list")
        
        # Check extracted_banks structure if present
        if 'extracted_banks' in result:
            banks = result['extracted_banks']
            if not isinstance(banks, list):
                errors.append("extracted_banks should be a list")
            else:
                for i, bank in enumerate(banks):
                    if not isinstance(bank, dict):
                        errors.append(f"Bank {i} should be a dictionary")
                    else:
                        bank_required_fields = ['raw_name']
                        for field in bank_required_fields:
                            if field not in bank:
                                errors.append(f"Bank {i} missing required field: {field}")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    @staticmethod
    def validate_database_result(result: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate database operation result."""
        errors = []
        
        if 'success' not in result:
            errors.append("Missing 'success' field in database result")
        
        if not result.get('success', False) and 'error' not in result:
            errors.append("Failed database operation should include 'error' field")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    @staticmethod
    def validate_workflow_result(result: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate workflow test result."""
        errors = []
        
        required_fields = ['success', 'steps']
        for field in required_fields:
            if field not in result:
                errors.append(f"Missing required field: {field}")
        
        if 'steps' in result:
            steps = result['steps']
            if not isinstance(steps, dict):
                errors.append("steps should be a dictionary")
            else:
                for step_name, step_result in steps.items():
                    if not isinstance(step_result, dict):
                        errors.append(f"Step '{step_name}' result should be a dictionary")
                    elif 'success' not in step_result:
                        errors.append(f"Step '{step_name}' missing 'success' field")
        
        is_valid = len(errors) == 0
        return is_valid, errors


class TestMetrics:
    """Collect and analyze test metrics."""
    
    def __init__(self):
        self.metrics = {
            'test_counts': {'passed': 0, 'failed': 0, 'skipped': 0},
            'execution_times': [],
            'error_types': {},
            'success_rates': {}
        }
    
    def record_test_result(self, test_name: str, success: bool, execution_time: float, 
                          error_type: str = None):
        """Record the result of a test."""
        if success:
            self.metrics['test_counts']['passed'] += 1
        else:
            self.metrics['test_counts']['failed'] += 1
            if error_type:
                self.metrics['error_types'][error_type] = self.metrics['error_types'].get(error_type, 0) + 1
        
        self.metrics['execution_times'].append({
            'test_name': test_name,
            'time': execution_time,
            'success': success
        })
    
    def record_success_rate(self, category: str, success_count: int, total_count: int):
        """Record success rate for a category."""
        rate = success_count / total_count * 100 if total_count > 0 else 0
        self.metrics['success_rates'][category] = {
            'success_count': success_count,
            'total_count': total_count,
            'rate': rate
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of collected metrics."""
        total_tests = sum(self.metrics['test_counts'].values())
        
        summary = {
            'total_tests': total_tests,
            'pass_rate': self.metrics['test_counts']['passed'] / total_tests * 100 if total_tests > 0 else 0,
            'execution_times': self.metrics['execution_times'],
            'error_distribution': self.metrics['error_types'],
            'success_rates': self.metrics['success_rates']
        }
        
        if self.metrics['execution_times']:
            times = [t['time'] for t in self.metrics['execution_times']]
            summary['time_statistics'] = {
                'average': sum(times) / len(times),
                'min': min(times),
                'max': max(times),
                'total': sum(times)
            }
        
        return summary


def setup_test_environment(debug: bool = False) -> Tuple[TestFileManager, logging.Logger, TestMetrics]:
    """Set up a complete test environment with file manager, logger, and metrics."""
    file_manager = TestFileManager()
    logger = TestLogger.setup_test_logger("TestEnvironment", debug)
    metrics = TestMetrics()
    
    logger.info("Test environment initialized")
    
    return file_manager, logger, metrics


def find_test_pdfs(directory: str = "data/downloads", max_files: int = 5) -> List[str]:
    """Find actual PDF files for testing."""
    pdf_dir = Path(directory)
    
    if not pdf_dir.exists():
        return []
    
    pdf_files = []
    
    # Look for PDFs in company subdirectories
    for company_dir in pdf_dir.iterdir():
        if company_dir.is_dir():
            for pdf_file in company_dir.glob("*.pdf"):
                pdf_files.append(str(pdf_file))
                if len(pdf_files) >= max_files:
                    break
        
        if len(pdf_files) >= max_files:
            break
    
    # If no PDFs found in subdirectories, look in main directory
    if not pdf_files:
        for pdf_file in pdf_dir.glob("*.pdf"):
            pdf_files.append(str(pdf_file))
            if len(pdf_files) >= max_files:
                break
    
    return pdf_files


# Pytest fixtures (if pytest is available)
try:
    import pytest
    
    @pytest.fixture
    def test_file_manager():
        """Pytest fixture for test file manager."""
        with TestFileManager() as manager:
            yield manager
    
    @pytest.fixture
    def sample_extraction_result():
        """Pytest fixture for sample extraction result."""
        return TestDataGenerator.create_sample_extraction_result()
    
    @pytest.fixture
    def sample_pdf_text():
        """Pytest fixture for sample PDF text."""
        return TestDataGenerator.create_sample_pdf_text()
    
    @pytest.fixture
    def test_metrics():
        """Pytest fixture for test metrics."""
        return TestMetrics()

except ImportError:
    # pytest not available, skip fixtures
    pass 