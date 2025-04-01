from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

# Association tables for many-to-many relationships
bond_underwriter = Table('bond_underwriter', Base.metadata,
    Column('bond_id', Integer, ForeignKey('bonds.id')),
    Column('underwriter_id', Integer, ForeignKey('underwriters.id'))
)

bond_bookrunner = Table('bond_bookrunner', Base.metadata,
    Column('bond_id', Integer, ForeignKey('bonds.id')),
    Column('bookrunner_id', Integer, ForeignKey('underwriters.id'))
)

class Issuer(Base):
    __tablename__ = 'issuers'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    lei = Column(String(20), unique=True)
    country = Column(String(100))
    industry = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    bonds = relationship("Bond", back_populates="issuer")

class Underwriter(Base):
    __tablename__ = 'underwriters'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    lei = Column(String(20), unique=True)
    country = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    underwritten_bonds = relationship("Bond", secondary=bond_underwriter, back_populates="underwriters")
    bookrun_bonds = relationship("Bond", secondary=bond_bookrunner, back_populates="bookrunners")

class Bond(Base):
    __tablename__ = 'bonds'
    
    id = Column(Integer, primary_key=True)
    isin = Column(String(12), unique=True)
    name = Column(String(255), nullable=False)
    type = Column(String(100))
    issue_date = Column(DateTime)
    maturity_date = Column(DateTime)
    amount = Column(Float)
    currency = Column(String(3))
    coupon_rate = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Foreign keys
    issuer_id = Column(Integer, ForeignKey('issuers.id'))
    
    # Relationships
    issuer = relationship("Issuer", back_populates="bonds")
    underwriters = relationship("Underwriter", secondary=bond_underwriter, back_populates="underwritten_bonds")
    bookrunners = relationship("Underwriter", secondary=bond_bookrunner, back_populates="bookrun_bonds")
    documents = relationship("Document", back_populates="bond")

class Document(Base):
    __tablename__ = 'documents'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    type = Column(String(100))
    url = Column(String(1000))
    local_path = Column(String(1000))
    processed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Foreign keys
    bond_id = Column(Integer, ForeignKey('bonds.id'))
    
    # Relationships
    bond = relationship("Bond", back_populates="documents") 