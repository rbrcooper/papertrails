from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from .models import Base, Issuer, Bond, Underwriter, Document

class DatabaseManager:
    def __init__(self, db_path: str = "esma_bonds.db"):
        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}')
        self.Session = sessionmaker(bind=self.engine)
        self.setup_logging()
        
    def setup_logging(self):
        self.logger = logging.getLogger(__name__)
        
    def init_db(self):
        """Initialize the database by creating all tables"""
        try:
            Base.metadata.create_all(self.engine)
            self.logger.info("Database initialized successfully")
        except SQLAlchemyError as e:
            self.logger.error(f"Error initializing database: {str(e)}")
            raise
            
    def get_session(self):
        """Get a new database session"""
        return self.Session()
        
    def get_or_create_issuer(self, data: Dict[str, Any]) -> int:
        """Get or create an issuer and return its ID"""
        session = self.get_session()
        try:
            # Try to find existing issuer by LEI
            issuer = session.query(Issuer).filter(Issuer.lei == data["lei"]).first()
            
            if not issuer:
                # Create new issuer
                issuer = Issuer(
                    name=data["name"],
                    lei=data["lei"],
                    country=data["country"],
                    industry=data.get("industry", "")
                )
                session.add(issuer)
                session.commit()
                self.logger.info(f"Created new issuer: {data['name']}")
            else:
                self.logger.info(f"Found existing issuer: {data['name']}")
            
            return issuer.id
            
        except SQLAlchemyError as e:
            session.rollback()
            self.logger.error(f"Error in get_or_create_issuer: {str(e)}")
            raise
        finally:
            session.close()
            
    def get_or_create_bond(self, data: Dict[str, Any], issuer_id: int) -> int:
        """Get or create a bond and return its ID"""
        session = self.get_session()
        try:
            # Try to find existing bond by ISIN
            bond = session.query(Bond).filter(Bond.isin == data["isin"]).first()
            
            if not bond:
                # Create new bond
                bond = Bond(
                    isin=data["isin"],
                    name=data["name"],
                    issuer_id=issuer_id,
                    issue_date=data.get("issue_date"),
                    maturity_date=data.get("maturity_date"),
                    currency=data.get("currency"),
                    nominal_amount=data.get("nominal_amount"),
                    coupon_rate=data.get("coupon_rate")
                )
                session.add(bond)
                session.commit()
                self.logger.info(f"Created new bond: {data['isin']}")
            else:
                self.logger.info(f"Found existing bond: {data['isin']}")
            
            return bond.id
            
        except SQLAlchemyError as e:
            session.rollback()
            self.logger.error(f"Error in get_or_create_bond: {str(e)}")
            raise
        finally:
            session.close()
            
    def get_or_create_underwriter(self, data: Dict[str, Any]) -> int:
        """Get or create an underwriter and return its ID"""
        session = self.get_session()
        try:
            # Try to find existing underwriter by LEI
            underwriter = session.query(Underwriter).filter(Underwriter.lei == data["lei"]).first()
            
            if not underwriter:
                # Create new underwriter
                underwriter = Underwriter(
                    name=data["name"],
                    lei=data["lei"],
                    country=data.get("country", "")
                )
                session.add(underwriter)
                session.commit()
                self.logger.info(f"Created new underwriter: {data['name']}")
            else:
                self.logger.info(f"Found existing underwriter: {data['name']}")
            
            return underwriter.id
            
        except SQLAlchemyError as e:
            session.rollback()
            self.logger.error(f"Error in get_or_create_underwriter: {str(e)}")
            raise
        finally:
            session.close()
            
    def add_issuer(self, name: str, lei: str = None, country: str = None):
        """Add a new issuer to the database"""
        session = self.get_session()
        try:
            issuer = Issuer(name=name, lei=lei, country=country)
            session.add(issuer)
            session.commit()
            return issuer
        except SQLAlchemyError as e:
            session.rollback()
            self.logger.error(f"Error adding issuer: {str(e)}")
            raise
        finally:
            session.close()
            
    def add_underwriter(self, name: str, lei: str = None, country: str = None):
        """Add a new underwriter to the database"""
        session = self.get_session()
        try:
            underwriter = Underwriter(name=name, lei=lei, country=country)
            session.add(underwriter)
            session.commit()
            return underwriter
        except SQLAlchemyError as e:
            session.rollback()
            self.logger.error(f"Error adding underwriter: {str(e)}")
            raise
        finally:
            session.close()
            
    def add_bond(self, isin: str, name: str, issuer_id: int, **kwargs):
        """Add a new bond to the database"""
        session = self.get_session()
        try:
            bond = Bond(isin=isin, name=name, issuer_id=issuer_id, **kwargs)
            session.add(bond)
            session.commit()
            return bond
        except SQLAlchemyError as e:
            session.rollback()
            self.logger.error(f"Error adding bond: {str(e)}")
            raise
        finally:
            session.close()
            
    def add_document(self, name: str, type: str, url: str, bond_id: int, local_path: str = None):
        """Add a new document to the database"""
        session = self.get_session()
        try:
            document = Document(
                name=name,
                type=type,
                url=url,
                bond_id=bond_id,
                local_path=local_path,
                processed_at=datetime.utcnow()
            )
            session.add(document)
            session.commit()
            return document
        except SQLAlchemyError as e:
            session.rollback()
            self.logger.error(f"Error adding document: {str(e)}")
            raise
        finally:
            session.close()
            
    def get_bond_by_isin(self, isin: str):
        """Get a bond by its ISIN"""
        session = self.get_session()
        try:
            return session.query(Bond).filter(Bond.isin == isin).first()
        finally:
            session.close()
            
    def get_issuer_by_name(self, name: str):
        """Get an issuer by its name"""
        session = self.get_session()
        try:
            return session.query(Issuer).filter(Issuer.name == name).first()
        finally:
            session.close()
            
    def get_underwriter_by_name(self, name: str):
        """Get an underwriter by its name"""
        session = self.get_session()
        try:
            return session.query(Underwriter).filter(Underwriter.name == name).first()
        finally:
            session.close()
            
    def link_bond_underwriter(self, bond_id: int, underwriter_id: int, is_bookrunner: bool = False):
        """Link a bond with an underwriter"""
        session = self.get_session()
        try:
            bond = session.query(Bond).get(bond_id)
            underwriter = session.query(Underwriter).get(underwriter_id)
            
            if is_bookrunner:
                bond.bookrunners.append(underwriter)
            else:
                bond.underwriters.append(underwriter)
                
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            self.logger.error(f"Error linking bond and underwriter: {str(e)}")
            raise
        finally:
            session.close()
            
    def get_or_create_document(self, session, name: str, type: str, url: str, bond_id: int) -> Document:
        """Get or create a document"""
        try:
            # Check if document exists
            document = session.query(Document).filter(
                Document.name == name,
                Document.bond_id == bond_id
            ).first()
            
            if document:
                self.logger.info(f"Found existing document: {name}")
                return document
                
            # Create new document
            document = Document(
                name=name,
                type=type,
                url=url,
                bond_id=bond_id,
                created_at=datetime.utcnow()
            )
            
            session.add(document)
            session.commit()
            
            self.logger.info(f"Created new document: {name}")
            return document
            
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error getting/creating document: {str(e)}")
            raise 