"""
Consolidated Database Integration Test Suite
==========================================
This file consolidates all database testing from multiple scattered test files:
- test_database.py
- check_db.py
- check_test_db.py

Provides comprehensive testing for database operations and integration.
"""

import sys
import os
import sqlite3
import tempfile
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add project root to sys.path to allow importing from processes
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from processes.database_handler import DatabaseHandler


class TestDatabaseIntegration:
    """Consolidated database integration testing."""
    
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
        self.logger = self._setup_logging()
        self.test_db_path = None
        self.db_handler = None
    
    def _setup_logging(self):
        """Configure logging."""
        level = logging.DEBUG if self.debug_mode else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        return logging.getLogger('TestDatabaseIntegration')
    
    def setup_test_database(self) -> str:
        """Create a temporary test database."""
        # Create temporary file for test database
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db_path = temp_file.name
        temp_file.close()
        
        # Initialize database handler with test database
        self.db_handler = DatabaseHandler(db_path=self.test_db_path)
        
        self.logger.info(f"Created test database: {self.test_db_path}")
        return self.test_db_path
    
    def cleanup_test_database(self):
        """Clean up the test database."""
        if self.test_db_path and os.path.exists(self.test_db_path):
            try:
                os.unlink(self.test_db_path)
                self.logger.info(f"Cleaned up test database: {self.test_db_path}")
            except Exception as e:
                self.logger.error(f"Error cleaning up test database: {e}")
        self.test_db_path = None
        self.db_handler = None
    
    def test_database_schema(self) -> Dict[str, Any]:
        """Test that the database schema is created correctly."""
        self.logger.info("Testing database schema creation...")
        
        try:
            with sqlite3.connect(self.test_db_path) as conn:
                cursor = conn.cursor()
                
                # Check if all required tables exist
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                expected_tables = ['companies', 'documents', 'bonds', 'banks', 'bond_banks']
                missing_tables = [table for table in expected_tables if table not in tables]
                
                if missing_tables:
                    return {
                        'success': False,
                        'error': f'Missing tables: {missing_tables}',
                        'tables_found': tables
                    }
                
                # Check table structures
                table_structures = {}
                for table in expected_tables:
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = cursor.fetchall()
                    table_structures[table] = columns
                
                self.logger.info("✅ Database schema created successfully")
                return {
                    'success': True,
                    'tables': tables,
                    'table_structures': table_structures
                }
                
        except Exception as e:
            self.logger.error(f"Error testing database schema: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_company_operations(self) -> Dict[str, Any]:
        """Test company-related database operations."""
        self.logger.info("Testing company operations...")
        
        try:
            # Test company insertion
            test_company = "Test Company Ltd"
            
            # Create a dummy extraction result
            extraction_result = {
                'filename': 'test.pdf',
                'file_path': '/path/to/test.pdf',
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
                'extracted_banks': [
                    {
                        'raw_name': 'Test Bank AG',
                        'standard_name': 'Test Bank',
                        'role': 'bookrunner',
                        'confidence': 0.9
                    }
                ]
            }
            
            # Store the extraction result
            success = self.db_handler.store_extraction_result(test_company, extraction_result)
            
            if not success:
                return {'success': False, 'error': 'Failed to store extraction result'}
            
            # Retrieve company bonds
            bonds = self.db_handler.get_company_bonds(test_company)
            
            if not bonds:
                return {'success': False, 'error': 'No bonds found for company'}
            
            if len(bonds) != 1:
                return {'success': False, 'error': f'Expected 1 bond, found {len(bonds)}'}
            
            bond = bonds[0]
            
            # Validate the stored data
            if bond['isin'] != 'TEST123456789':
                return {'success': False, 'error': f'ISIN mismatch: {bond["isin"]}'}
            
            if bond['currency'] != 'EUR':
                return {'success': False, 'error': f'Currency mismatch: {bond["currency"]}'}
            
            self.logger.info("✅ Company operations test passed")
            return {
                'success': True,
                'company': test_company,
                'bonds_count': len(bonds),
                'bond_data': bond
            }
            
        except Exception as e:
            self.logger.error(f"Error testing company operations: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_bond_operations(self) -> Dict[str, Any]:
        """Test bond-related database operations."""
        self.logger.info("Testing bond operations...")
        
        try:
            # Get bond details (assuming we have a bond from previous test)
            bonds = self.db_handler.get_company_bonds("Test Company Ltd")
            
            if not bonds:
                return {'success': False, 'error': 'No bonds found for testing'}
            
            bond_id = bonds[0]['id']
            
            # Test get_bond_details
            bond_details = self.db_handler.get_bond_details(bond_id)
            
            if not bond_details:
                return {'success': False, 'error': 'Failed to get bond details'}
            
            # Test validation status update
            success = self.db_handler.update_bond_validation(bond_id, 'verified', 1.0)
            
            if not success:
                return {'success': False, 'error': 'Failed to update bond validation'}
            
            # Verify the update
            updated_bond = self.db_handler.get_bond_details(bond_id)
            
            if updated_bond['validation_status'] != 'verified':
                return {'success': False, 'error': 'Validation status not updated'}
            
            self.logger.info("✅ Bond operations test passed")
            return {
                'success': True,
                'bond_id': bond_id,
                'bond_details': updated_bond
            }
            
        except Exception as e:
            self.logger.error(f"Error testing bond operations: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_bank_operations(self) -> Dict[str, Any]:
        """Test bank-related database operations."""
        self.logger.info("Testing bank operations...")
        
        try:
            # Test getting bond banks
            bonds = self.db_handler.get_company_bonds("Test Company Ltd")
            
            if not bonds:
                return {'success': False, 'error': 'No bonds found for testing'}
            
            bond_id = bonds[0]['id']
            
            # Get bond banks
            bond_banks = self.db_handler.get_bond_banks(bond_id)
            
            if not bond_banks:
                return {'success': False, 'error': 'No banks found for bond'}
            
            if len(bond_banks) != 1:
                return {'success': False, 'error': f'Expected 1 bank, found {len(bond_banks)}'}
            
            bank = bond_banks[0]
            
            # Validate bank data
            if bank['name'] != 'Test Bank AG':
                return {'success': False, 'error': f'Bank name mismatch: {bank["name"]}'}
            
            if bank['role'] != 'bookrunner':
                return {'success': False, 'error': f'Bank role mismatch: {bank["role"]}'}
            
            self.logger.info("✅ Bank operations test passed")
            return {
                'success': True,
                'bond_id': bond_id,
                'banks_count': len(bond_banks),
                'bank_data': bank
            }
            
        except Exception as e:
            self.logger.error(f"Error testing bank operations: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_database_statistics(self) -> Dict[str, Any]:
        """Test database statistics retrieval."""
        self.logger.info("Testing database statistics...")
        
        try:
            stats = self.db_handler.get_stats()
            
            # Validate stats structure
            expected_keys = ['total_companies', 'total_documents', 'total_bonds', 'total_banks']
            missing_keys = [key for key in expected_keys if key not in stats]
            
            if missing_keys:
                return {'success': False, 'error': f'Missing stats keys: {missing_keys}'}
            
            # Validate stats values (should have at least our test data)
            if stats['total_companies'] < 1:
                return {'success': False, 'error': 'Expected at least 1 company'}
            
            if stats['total_bonds'] < 1:
                return {'success': False, 'error': 'Expected at least 1 bond'}
            
            self.logger.info("✅ Database statistics test passed")
            return {
                'success': True,
                'stats': stats
            }
            
        except Exception as e:
            self.logger.error(f"Error testing database statistics: {e}")
            return {'success': False, 'error': str(e)}
    
    def check_database_integrity(self, db_path: str = None) -> Dict[str, Any]:
        """Check database integrity and consistency."""
        check_db_path = db_path or self.test_db_path
        self.logger.info(f"Checking database integrity: {check_db_path}")
        
        try:
            with sqlite3.connect(check_db_path) as conn:
                cursor = conn.cursor()
                
                # Run integrity check
                cursor.execute("PRAGMA integrity_check")
                integrity_result = cursor.fetchone()[0]
                
                if integrity_result != 'ok':
                    return {'success': False, 'error': f'Integrity check failed: {integrity_result}'}
                
                # Check foreign key constraints
                cursor.execute("PRAGMA foreign_key_check")
                fk_violations = cursor.fetchall()
                
                if fk_violations:
                    return {'success': False, 'error': f'Foreign key violations: {fk_violations}'}
                
                # Get table counts
                table_counts = {}
                tables = ['companies', 'documents', 'bonds', 'banks', 'bond_banks']
                
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    table_counts[table] = cursor.fetchone()[0]
                
                self.logger.info("✅ Database integrity check passed")
                return {
                    'success': True,
                    'integrity_check': integrity_result,
                    'table_counts': table_counts
                }
                
        except Exception as e:
            self.logger.error(f"Error checking database integrity: {e}")
            return {'success': False, 'error': str(e)}
    
    def run_full_test_suite(self) -> Dict[str, Any]:
        """Run the complete database test suite."""
        self.logger.info("Running full database test suite...")
        
        results = {
            'overall_success': True,
            'test_results': {},
            'error_count': 0
        }
        
        try:
            # Setup test database
            self.setup_test_database()
            
            # Run all tests
            tests = [
                ('schema', self.test_database_schema),
                ('company_operations', self.test_company_operations),
                ('bond_operations', self.test_bond_operations),
                ('bank_operations', self.test_bank_operations),
                ('statistics', self.test_database_statistics),
                ('integrity', self.check_database_integrity)
            ]
            
            for test_name, test_func in tests:
                self.logger.info(f"\n--- Running {test_name} test ---")
                
                try:
                    result = test_func()
                    results['test_results'][test_name] = result
                    
                    if not result.get('success', False):
                        results['overall_success'] = False
                        results['error_count'] += 1
                        self.logger.error(f"❌ {test_name} test failed: {result.get('error', 'Unknown error')}")
                    else:
                        self.logger.info(f"✅ {test_name} test passed")
                        
                except Exception as e:
                    results['test_results'][test_name] = {'success': False, 'error': str(e)}
                    results['overall_success'] = False
                    results['error_count'] += 1
                    self.logger.error(f"❌ {test_name} test failed with exception: {e}")
            
            # Print summary
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"DATABASE TEST SUITE SUMMARY")
            self.logger.info(f"{'='*60}")
            self.logger.info(f"Overall result: {'PASS' if results['overall_success'] else 'FAIL'}")
            self.logger.info(f"Tests passed: {len(tests) - results['error_count']}/{len(tests)}")
            self.logger.info(f"Errors: {results['error_count']}")
            
            if results['error_count'] > 0:
                self.logger.info(f"\nFailed tests:")
                for test_name, result in results['test_results'].items():
                    if not result.get('success', False):
                        self.logger.info(f"  - {test_name}: {result.get('error', 'Unknown error')}")
            
        finally:
            # Cleanup
            self.cleanup_test_database()
        
        return results


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Database Integration Test Suite")
    parser.add_argument("--db-path", help="Path to existing database to check (optional)")
    parser.add_argument("--debug", action='store_true', help="Enable debug mode")
    args = parser.parse_args()
    
    tester = TestDatabaseIntegration(debug_mode=args.debug)
    
    if args.db_path:
        # Check existing database
        if not os.path.exists(args.db_path):
            print(f"Error: Database file not found: {args.db_path}")
            return
        
        result = tester.check_database_integrity(args.db_path)
        if result['success']:
            print("✅ Database integrity check passed")
            print(f"Table counts: {result['table_counts']}")
        else:
            print(f"❌ Database integrity check failed: {result['error']}")
    else:
        # Run full test suite
        results = tester.run_full_test_suite()
        
        if results['overall_success']:
            print("\n🎉 All database tests passed!")
        else:
            print(f"\n❌ {results['error_count']} test(s) failed")
            exit(1)


if __name__ == "__main__":
    main() 