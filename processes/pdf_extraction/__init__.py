"""
PDF Extraction Package
----------------------
A modular package for extracting information from PDF documents.
"""

from .core import ExtractionEngine
from .extractors.bank_extractor import BankExtractor
from .extractors.date_extractor import DateExtractor
from .extractors.currency_extractor import CurrencyExtractor
from .extractors.coupon_extractor import CouponExtractor
from .utils.text_processing import TextProcessor

__all__ = [
    'ExtractionEngine',
    'BankExtractor',
    'DateExtractor',
    'CurrencyExtractor',
    'CouponExtractor',
    'TextProcessor'
] 