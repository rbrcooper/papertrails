import sqlite3
import json
import pandas as pd
from pathlib import Path
import logging
from datetime import datetime
import re

class ESMADatabaseBuilder:
    def __init__(self, db_path: str = "esma_bonds.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.setup_logging()
        self.create_tables()
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
    def create_tables(self):
        """Create the database tables if they don't exist"""
        cursor = self.conn.cursor()
        
        # Create issuers table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS issuers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            lei TEXT,
            country TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create underwriters table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS underwriters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            lei TEXT,
            country TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create bonds table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bonds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isin TEXT UNIQUE NOT NULL,
            issuer_id INTEGER,
            document_type TEXT NOT NULL,
            issue_date DATE,
            maturity_date DATE,
            coupon_rate REAL,
            currency TEXT,
            issue_size REAL,
            issue_size_currency TEXT,
            rating TEXT,
            listing TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (issuer_id) REFERENCES issuers (id)
        )
        ''')
        
        # Create underwriting relationships table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS underwriting_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bond_id INTEGER,
            underwriter_id INTEGER,
            role TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (bond_id) REFERENCES bonds (id),
            FOREIGN KEY (underwriter_id) REFERENCES underwriters (id)
        )
        ''')
        
        self.conn.commit()
        
    def process_financial_data(self, data_dir: Path):
        """Process all financial data files and load into database"""
        # Get the most recent bond details file
        bond_files = list(data_dir.glob("totalenergies_bond_details_*.json"))
        if not bond_files:
            logging.error("No bond details files found")
            return
            
        latest_file = max(bond_files, key=lambda x: x.stat().st_mtime)
        logging.info(f"Processing bond details from {latest_file}")
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            bond_data = json.load(f)
            
        # Process each bond
        for bond in bond_data:
            self.process_bond(bond)
            
    def process_bond(self, bond_data: dict):
        """Process a single bond and its related data"""
        cursor = self.conn.cursor()
        
        # Insert or get issuer
        issuer_id = self.get_or_create_issuer(bond_data.get('issuer_info', {}))
        
        # Insert bond
        bond_id = self.insert_bond(bond_data, issuer_id)
        if not bond_id:
            return
            
        # Process underwriters
        self.process_underwriters(bond_data, bond_id)
        
    def get_or_create_issuer(self, issuer_info: dict) -> int:
        """Get or create an issuer record"""
        cursor = self.conn.cursor()
        
        # Try to find existing issuer
        cursor.execute(
            "SELECT id FROM issuers WHERE name = ?",
            (issuer_info.get('name', ''),)
        )
        result = cursor.fetchone()
        
        if result:
            return result[0]
            
        # Create new issuer
        cursor.execute('''
        INSERT INTO issuers (name, lei, country)
        VALUES (?, ?, ?)
        ''', (
            issuer_info.get('name', ''),
            issuer_info.get('lei', ''),
            issuer_info.get('country', '')
        ))
        
        self.conn.commit()
        return cursor.lastrowid
        
    def insert_bond(self, bond_data: dict, issuer_id: int) -> int:
        """Insert a bond record and return its ID"""
        cursor = self.conn.cursor()
        
        # Parse issue size
        issue_size = None
        issue_size_currency = None
        if 'issue_size' in bond_data:
            size_str = str(bond_data['issue_size'])
            match = re.search(r'(\d+(?:\.\d+)?)\s*([A-Z]{3})', size_str)
            if match:
                issue_size = float(match.group(1))
                issue_size_currency = match.group(2)
                
        # Parse dates
        issue_date = self.parse_date(bond_data.get('issue_date'))
        maturity_date = self.parse_date(bond_data.get('maturity_date'))
        
        try:
            cursor.execute('''
            INSERT INTO bonds (
                isin, issuer_id, document_type, issue_date, maturity_date,
                coupon_rate, currency, issue_size, issue_size_currency,
                rating, listing
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                bond_data.get('isin', ''),
                issuer_id,
                bond_data.get('document_type', ''),
                issue_date,
                maturity_date,
                bond_data.get('coupon'),
                bond_data.get('currency'),
                issue_size,
                issue_size_currency,
                bond_data.get('rating'),
                bond_data.get('listing')
            ))
            
            self.conn.commit()
            return cursor.lastrowid
            
        except sqlite3.IntegrityError:
            # Bond already exists, get its ID
            cursor.execute(
                "SELECT id FROM bonds WHERE isin = ?",
                (bond_data.get('isin', ''),)
            )
            return cursor.fetchone()[0]
            
    def process_underwriters(self, bond_data: dict, bond_id: int):
        """Process underwriters for a bond"""
        cursor = self.conn.cursor()
        
        # Process bookrunners
        for bookrunner in bond_data.get('bookrunners', []):
            underwriter_id = self.get_or_create_underwriter(bookrunner)
            if underwriter_id:
                cursor.execute('''
                INSERT INTO underwriting_relationships (bond_id, underwriter_id, role)
                VALUES (?, ?, ?)
                ''', (bond_id, underwriter_id, 'bookrunner'))
                
        # Process other underwriters
        for underwriter in bond_data.get('underwriters', []):
            underwriter_id = self.get_or_create_underwriter(underwriter)
            if underwriter_id:
                cursor.execute('''
                INSERT INTO underwriting_relationships (bond_id, underwriter_id, role)
                VALUES (?, ?, ?)
                ''', (bond_id, underwriter_id, 'underwriter'))
                
        self.conn.commit()
        
    def get_or_create_underwriter(self, underwriter_name: str) -> int:
        """Get or create an underwriter record"""
        cursor = self.conn.cursor()
        
        # Try to find existing underwriter
        cursor.execute(
            "SELECT id FROM underwriters WHERE name = ?",
            (underwriter_name,)
        )
        result = cursor.fetchone()
        
        if result:
            return result[0]
            
        # Create new underwriter
        cursor.execute('''
        INSERT INTO underwriters (name)
        VALUES (?)
        ''', (underwriter_name,))
        
        self.conn.commit()
        return cursor.lastrowid
        
    def parse_date(self, date_str: str) -> str:
        """Parse date string into SQLite date format"""
        if not date_str:
            return None
            
        try:
            # Handle different date formats
            formats = [
                '%d/%m/%Y',
                '%Y-%m-%d',
                '%d-%m-%Y',
                '%Y/%m/%d'
            ]
            
            for fmt in formats:
                try:
                    date = datetime.strptime(date_str, fmt)
                    return date.strftime('%Y-%m-%d')
                except ValueError:
                    continue
                    
            return None
            
        except Exception as e:
            logging.error(f"Error parsing date {date_str}: {str(e)}")
            return None
            
    def generate_summary(self):
        """Generate summary statistics from the database"""
        cursor = self.conn.cursor()
        
        # Get total number of bonds
        cursor.execute("SELECT COUNT(*) FROM bonds")
        total_bonds = cursor.fetchone()[0]
        
        # Get total number of underwriters
        cursor.execute("SELECT COUNT(*) FROM underwriters")
        total_underwriters = cursor.fetchone()[0]
        
        # Get top underwriters by number of deals
        cursor.execute('''
        SELECT u.name, COUNT(ur.id) as deal_count
        FROM underwriters u
        JOIN underwriting_relationships ur ON u.id = ur.underwriter_id
        GROUP BY u.id
        ORDER BY deal_count DESC
        LIMIT 10
        ''')
        top_underwriters = cursor.fetchall()
        
        # Get total issue size by currency
        cursor.execute('''
        SELECT issue_size_currency, SUM(issue_size) as total_size
        FROM bonds
        WHERE issue_size IS NOT NULL
        GROUP BY issue_size_currency
        ''')
        issue_sizes = cursor.fetchall()
        
        return {
            'total_bonds': total_bonds,
            'total_underwriters': total_underwriters,
            'top_underwriters': top_underwriters,
            'issue_sizes': issue_sizes
        }
        
    def close(self):
        """Close the database connection"""
        self.conn.close()

def main():
    # Initialize database builder
    builder = ESMADatabaseBuilder()
    
    try:
        # Process financial data
        data_dir = Path("ESMA bond pull/financial_data")
        builder.process_financial_data(data_dir)
        
        # Generate summary
        summary = builder.generate_summary()
        
        # Print summary
        print("\nDatabase Summary:")
        print(f"Total Bonds: {summary['total_bonds']}")
        print(f"Total Underwriters: {summary['total_underwriters']}")
        
        print("\nTop 10 Underwriters by Deal Count:")
        for name, count in summary['top_underwriters']:
            print(f"{name}: {count} deals")
            
        print("\nTotal Issue Size by Currency:")
        for currency, size in summary['issue_sizes']:
            print(f"{currency}: {size:,.2f}")
            
    finally:
        builder.close()

if __name__ == "__main__":
    main() 