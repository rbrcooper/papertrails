"""
Database Handler
---------------
Handles storage and retrieval of extracted PDF data in a SQLite database.
"""

import sqlite3
import json
from pathlib import Path
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import re

class DatabaseHandler:
    def __init__(self, db_path: str = "data/bond_data.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self._init_db()
        
        # Load canonical bank mappings
        self.bank_canonical_map = self._load_bank_canonical_map()
        
        # Define role enum for normalization
        self.role_normalization = {
            'lead manager': 'Lead Manager',
            'lead': 'Lead Manager',
            'lead arranger': 'Lead Manager',
            'joint lead manager': 'Joint Lead Manager',
            'joint lead': 'Joint Lead Manager',
            'joint lead arranger': 'Joint Lead Manager',
            'bookrunner': 'Bookrunner',
            'book runner': 'Bookrunner',
            'book-runner': 'Bookrunner',
            'co-manager': 'Co-Manager',
            'co manager': 'Co-Manager',
            'dealer': 'Dealer',
            'market maker': 'Dealer'
        }
        
    def _load_bank_canonical_map(self) -> Dict[str, Dict[str, Any]]:
        """Load canonical bank mappings from disk."""
        canonical_map_file = Path("data/bank_names.json")
        if not canonical_map_file.exists():
            self.logger.info(f"Bank canonical map not found at {canonical_map_file}, proceeding without canonicalization")
            return {}
        
        try:
            with open(canonical_map_file, 'r', encoding='utf-8') as f:
                map_data = json.load(f)
                self.logger.info(f"Loaded {len(map_data)} bank canonical mappings")
                return map_data
        except Exception as e:
            self.logger.warning(f"Could not load bank canonical map: {e}")
            return {}
    
    def _normalize_bank_name(self, raw_name: str) -> str:
        """
        Normalize bank name to canonical form using mapping.
        Returns standard_name if found, otherwise returns raw_name.
        """
        if not raw_name or not isinstance(raw_name, str):
            return raw_name
        
        raw_name = raw_name.strip()
        if not raw_name:
            return raw_name
        
        # Exact match on lookup key (case-insensitive)
        for key, mapping in self.bank_canonical_map.items():
            if key.lower() == raw_name.lower():
                return mapping.get('standard_name', mapping.get('canonical_name', key))
        
        # Check aliases
        for key, mapping in self.bank_canonical_map.items():
            aliases = mapping.get('aliases', [])
            if any(alias.lower() == raw_name.lower() for alias in aliases):
                return mapping.get('standard_name', mapping.get('canonical_name', key))
        
        # No match found, return original
        return raw_name
    
    def _normalize_role(self, role: str) -> str:
        """Normalize role to enum value."""
        if not role or not isinstance(role, str):
            return 'Unknown'
        
        role_lower = role.lower().strip()
        return self.role_normalization.get(role_lower, 'Unknown')
        
    def _init_db(self):
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create companies table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS companies (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    lei TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create documents table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    document_type TEXT,
                    extraction_date TIMESTAMP,
                    extraction_status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (company_id) REFERENCES companies(id)
                )
            ''')
            
            # Create bonds table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bonds (
                    id INTEGER PRIMARY KEY,
                    document_id INTEGER,
                    isin TEXT,
                    issue_date TEXT,
                    maturity_date TEXT,
                    issue_size REAL,
                    currency TEXT,
                    coupon_rate REAL,
                    coupon_type TEXT,
                    extraction_confidence REAL,
                    validation_status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES documents(id)
                )
            ''')
            
            # Create banks table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS banks (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    standard_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create bond_banks table (many-to-many relationship)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bond_banks (
                    bond_id INTEGER,
                    bank_id INTEGER,
                    role TEXT,
                    confidence REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (bond_id, bank_id),
                    FOREIGN KEY (bond_id) REFERENCES bonds(id),
                    FOREIGN KEY (bank_id) REFERENCES banks(id)
                )
            ''')
            
            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_documents_company ON documents(company_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_bonds_document ON bonds(document_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_bonds_isin ON bonds(isin)')
            
            conn.commit()
            
    def store_extraction_result(self, company_name: str, result: Dict):
        """Store extraction results in the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Insert or get company
                cursor.execute(
                    "INSERT OR IGNORE INTO companies (name) VALUES (?)",
                    (company_name,)
                )
                company_id = cursor.lastrowid or cursor.execute(
                    "SELECT id FROM companies WHERE name = ?",
                    (company_name,)
                ).fetchone()[0]
                
                # Insert document
                cursor.execute(
                    """INSERT INTO documents 
                    (company_id, filename, file_path, document_type, extraction_date, extraction_status) 
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        company_id, 
                        result['filename'], 
                        result['file_path'],
                        result.get('document_type', 'unknown'),
                        datetime.now().isoformat(),
                        result.get('extraction_status', 'complete')
                    )
                )
                document_id = cursor.lastrowid
                
                # Insert bond
                metadata = result.get('metadata', {})
                cursor.execute(
                    """INSERT INTO bonds 
                    (document_id, isin, issue_date, maturity_date, issue_size, currency, 
                    coupon_rate, coupon_type, extraction_confidence, validation_status) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        document_id,
                        metadata.get('isin'),
                        metadata.get('issue_date'),
                        metadata.get('maturity_date'),
                        metadata.get('issue_size'),
                        metadata.get('currency'),
                        metadata.get('coupon_rate'),
                        metadata.get('coupon_type', 'fixed'),
                        metadata.get('extraction_confidence', 0.0),
                        metadata.get('validation_status', 'unverified')
                    )
                )
                bond_id = cursor.lastrowid
                
                # Insert banks and relationships
                for bank_entry in result.get('extracted_banks', []):
                    # Handle both simple strings and dictionary entries for banks
                    if isinstance(bank_entry, dict):
                        bank_name = bank_entry.get('raw_name')
                        # Use canonical mapping to get standard_name
                        standard_name = self._normalize_bank_name(bank_name)
                        role_raw = bank_entry.get('role', 'Unknown')
                        role = self._normalize_role(role_raw)  # Normalize role to enum
                        confidence = bank_entry.get('confidence', 1.0)
                    else:
                        bank_name = str(bank_entry)
                        standard_name = self._normalize_bank_name(bank_name)  # Canonicalize
                        role = 'Unknown'  # Normalized role
                        confidence = 0.75 # Assign a default confidence for regex/simple extractions
                    
                    if not bank_name:
                        continue

                    # Normalize bank name and get canonical form
                    # Check if bank already exists by canonical name first to avoid duplicates
                    bank_id = None
                    
                    # First, try to find existing bank by canonical name
                    # This prevents duplicates when multiple aliases map to the same canonical name
                    if standard_name:  # Only check if we have a canonical name
                        cursor.execute(
                            "SELECT id FROM banks WHERE standard_name = ?",
                            (standard_name,)
                        )
                        row = cursor.fetchone()
                        if row:
                            bank_id = row[0]
                    
                    # If not found by canonical, try by raw name (for backward compatibility)
                    # Also check for legacy entries where standard_name might be NULL but name matches
                    if not bank_id:
                        cursor.execute(
                            "SELECT id, standard_name FROM banks WHERE name = ?",
                            (bank_name,)
                        )
                        row = cursor.fetchone()
                        if row:
                            bank_id = row[0]
                            existing_standard = row[1]
                            # Update to set canonical name if it wasn't set or needs updating
                            if not existing_standard or (standard_name and existing_standard != standard_name):
                                cursor.execute(
                                    "UPDATE banks SET standard_name = ? WHERE id = ?",
                                    (standard_name, bank_id)
                                )
                    
                    # Also check if canonical name exists as a bank name (legacy entry)
                    # Handles case: legacy entry has name="JPMorgan" with standard_name=NULL,
                    # and we're inserting an alias "J.P. Morgan" that maps to "JPMorgan"
                    if not bank_id and standard_name and standard_name != bank_name:
                        cursor.execute(
                            "SELECT id FROM banks WHERE name = ? AND (standard_name IS NULL OR standard_name = '')",
                            (standard_name,)
                        )
                        row = cursor.fetchone()
                        if row:
                            bank_id = row[0]
                            # Update existing entry to set the canonical name
                            cursor.execute(
                                "UPDATE banks SET standard_name = ? WHERE id = ?",
                                (standard_name, bank_id)
                            )
                    
                    # If still not found, insert new bank
                    if not bank_id:
                        cursor.execute(
                            "INSERT INTO banks (name, standard_name) VALUES (?, ?)",
                            (bank_name, standard_name)
                        )
                        bank_id = cursor.lastrowid
                    
                    if not bank_id:
                        self.logger.warning(f"Could not get or create bank_id for {bank_name}")
                        continue
                    
                    cursor.execute(
                        "INSERT OR IGNORE INTO bond_banks (bond_id, bank_id, role, confidence) VALUES (?, ?, ?, ?)",
                        (bond_id, bank_id, role, confidence)
                    )
                
                conn.commit()
                self.logger.info(f"Successfully stored extraction result for document: {result['filename']}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error storing extraction result: {str(e)}")
            return False
            
    def get_company_bonds(self, company_name: str) -> List[Dict]:
        """Retrieve all bonds for a company."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT b.*, d.filename, d.extraction_date
                    FROM bonds b
                    JOIN documents d ON b.document_id = d.id
                    JOIN companies c ON d.company_id = c.id
                    WHERE c.name = ?
                    ORDER BY b.created_at DESC
                ''', (company_name,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"Error retrieving company bonds: {str(e)}")
            raise

    def get_bond_details(self, bond_id: int) -> Dict:
        """Retrieve detailed information about a specific bond."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get bond information
                cursor.execute('''
                    SELECT b.*, d.filename, d.file_path, d.extraction_date, c.name as company_name
                    FROM bonds b
                    JOIN documents d ON b.document_id = d.id
                    JOIN companies c ON d.company_id = c.id
                    WHERE b.id = ?
                ''', (bond_id,))
                
                bond = dict(cursor.fetchone())
                
                # Get associated banks
                cursor.execute('''
                    SELECT bk.name, bk.standard_name, bb.role, bb.confidence
                    FROM bond_banks bb
                    JOIN banks bk ON bb.bank_id = bk.id
                    WHERE bb.bond_id = ?
                ''', (bond_id,))
                
                bond['banks'] = [dict(row) for row in cursor.fetchall()]
                
                return bond
                
        except Exception as e:
            self.logger.error(f"Error retrieving bond details: {str(e)}")
            raise
            
    def update_bond_validation(self, bond_id: int, validation_status: str, confidence: float = None):
        """Update the validation status of a bond."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                update_fields = ["validation_status = ?"]
                params = [validation_status]
                
                if confidence is not None:
                    update_fields.append("extraction_confidence = ?")
                    params.append(confidence)
                
                query = f"UPDATE bonds SET {', '.join(update_fields)} WHERE id = ?"
                params.append(bond_id)
                
                cursor.execute(query, params)
                conn.commit()
                self.logger.info(f"Successfully updated validation status for bond ID: {bond_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error updating bond validation: {str(e)}")
            return False
    
    def get_results(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """Retrieve results for aggregation, matching the structure DataAggregator expects."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                query = """
                    SELECT
                        c.name as company_name,
                        b.isin,
                        b.issue_date,
                        b.maturity_date,
                        b.issue_size,
                        b.currency,
                        b.coupon_rate,
                        b.coupon_type,
                        b.id as bond_id,
                        d.filename as document_filename
                    FROM bonds b
                    JOIN documents d ON b.document_id = d.id
                    JOIN companies c ON d.company_id = c.id
                """
                # Date filtering can be added here if needed, e.g., using d.extraction_date
                # For now, an example if start_date and end_date were used for b.issue_date:
                # params = []
                # if start_date:
                #     query += " WHERE b.issue_date >= ?"
                #     params.append(start_date)
                # if end_date:
                #     query += " AND b.issue_date <= ?" if start_date else " WHERE b.issue_date <= ?"
                #     params.append(end_date)
                # query += " ORDER BY c.name, b.issue_date;"
                # cursor.execute(query, params)

                cursor.execute(query + " ORDER BY c.name, b.issue_date;")
                
                raw_bonds = cursor.fetchall()
                results = []

                for bond_row in raw_bonds:
                    bond_dict = dict(bond_row)
                    
                    # Fetch banks for this bond
                    cursor.execute("""
                        SELECT bk.standard_name, bk.name as raw_name, bb.role, bb.confidence
                        FROM bond_banks bb
                        JOIN banks bk ON bb.bank_id = bk.id
                        WHERE bb.bond_id = ?
                    """, (bond_dict['bond_id'],))
                    
                    banks_data = []
                    for bank_row in cursor.fetchall():
                        banks_data.append({
                            'standardized_name': bank_row['standard_name'] if bank_row['standard_name'] else bank_row['raw_name'],
                            'role': bank_row['role'],
                            'confidence': bank_row['confidence']
                        })

                    result_item = {
                        'company_name': bond_dict['company_name'],
                        'currency_info': {
                            'currency': bond_dict['currency'],
                            'amount': bond_dict['issue_size']
                        },
                        'banks': banks_data, # List of dicts with 'standardized_name'
                        'issue_date': bond_dict['issue_date'],
                        'maturity_date': bond_dict['maturity_date'],
                        'coupon_info': bond_dict['coupon_rate'], # DataAggregator expects rate here
                        'isin': bond_dict['isin'],
                        'document_filename': bond_dict['document_filename'],
                        'bond_id': bond_dict['bond_id']
                        # Add other fields as needed by DataAggregator if current ones are insufficient
                    }
                    results.append(result_item)
                
                return results

        except Exception as e:
            self.logger.error(f"Error retrieving results for aggregation: {str(e)}", exc_info=True)
            return [] # Return empty list on error

    def get_all_validation_results(self) -> List[Dict]:
        """Retrieve all validation results for reporting."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        b.id as bond_id, 
                        d.id as document_id, 
                        c.name as company_name,
                        d.filename as document_filename,
                        b.validation_status,
                        b.extraction_confidence,
                        b.isin,
                        b.issue_date,
                        b.maturity_date
                    FROM bonds b
                    JOIN documents d ON b.document_id = d.id
                    JOIN companies c ON d.company_id = c.id
                    ORDER BY c.name, d.filename, b.id;
                """)
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            self.logger.error(f"Error retrieving all validation results: {str(e)}", exc_info=True)
            return [] # Return empty list on error

    def get_stats(self) -> Dict:
        """Get statistics about the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                stats = {}
                
                # Count of companies
                cursor.execute("SELECT COUNT(*) FROM companies")
                stats['company_count'] = cursor.fetchone()[0]
                
                # Count of documents
                cursor.execute("SELECT COUNT(*) FROM documents")
                stats['document_count'] = cursor.fetchone()[0]
                
                # Count of bonds
                cursor.execute("SELECT COUNT(*) FROM bonds")
                stats['bond_count'] = cursor.fetchone()[0]
                
                # Count by validation status
                cursor.execute('''
                    SELECT validation_status, COUNT(*) 
                    FROM bonds 
                    GROUP BY validation_status
                ''')
                stats['validation_stats'] = dict(cursor.fetchall())
                
                return stats
                
        except Exception as e:
            self.logger.error(f"Error getting database stats: {str(e)}")
            raise

    def get_all_company_names(self) -> List[str]:
        """Retrieve a list of all unique company names."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM companies ORDER BY name")
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            self.logger.error(f"Error retrieving all company names: {str(e)}", exc_info=True)
            return [] 