#!/usr/bin/env python3
"""
Diagnostic Script: Why does AI fail to extract banks in 60% of cases?
Tests 7 potential theories systematically.
"""

import os
import json
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from processes.pdf_extraction.core import ExtractionEngine

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FailureDiagnostic:
    """Diagnose why AI bank extraction fails"""
    
    def __init__(self):
        self.extraction_engine = ExtractionEngine()
    
    def theory_1_text_quality(self, pdf_path):
        """Theory 1: Poor text extraction quality"""
        try:
            text = self.extraction_engine.extract_text(pdf_path)
            
            analysis = {
                "total_length": len(text),
                "word_count": len(text.split()),
                "line_count": len(text.split('\n')),
                "readable_ratio": self._calculate_readable_ratio(text),
                "has_garbled_text": self._detect_garbled_text(text),
                "sample_text": text[:500] + "..." if len(text) > 500 else text
            }
            
            logger.info(f"Text Quality Analysis for {Path(pdf_path).name}:")
            logger.info(f"  Length: {analysis['total_length']} chars, {analysis['word_count']} words")
            logger.info(f"  Readable ratio: {analysis['readable_ratio']:.2f}")
            logger.info(f"  Garbled text detected: {analysis['has_garbled_text']}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return {"error": str(e)}
    
    def theory_2_bank_name_variations(self, pdf_path):
        """Theory 2: Banks mentioned in different formats/sections"""
        try:
            text = self.extraction_engine.extract_text(pdf_path)
            
            # Common bank-related keywords in different contexts
            bank_keywords = [
                # Direct mentions
                "bank", "manager", "underwriter", "arranger", "dealer",
                # Legal entities  
                "AG", "S.A.", "Ltd", "plc", "Inc", "Corporation",
                # Financial terms
                "lead", "co-manager", "syndicate", "bookrunner",
                # Common bank names (fragments)
                "goldman", "morgan", "deutsche", "barclays", "bnp", "credit",
                "mediobanca", "societe", "unicredit", "santander", "ing"
            ]
            
            found_keywords = {}
            for keyword in bank_keywords:
                occurrences = text.lower().count(keyword.lower())
                if occurrences > 0:
                    found_keywords[keyword] = occurrences
            
            # Look for potential bank sections
            sections_with_banks = []
            text_lower = text.lower()
            
            # Find sections that might contain bank info
            potential_sections = [
                "underwriter", "manager", "arranger", "dealer", "syndicate",
                "bookrunner", "lead", "co-manager", "agent", "advisor"
            ]
            
            for section in potential_sections:
                if section in text_lower:
                    # Extract context around the keyword
                    start = max(0, text_lower.find(section) - 200)
                    end = min(len(text), text_lower.find(section) + 300)
                    context = text[start:end]
                    sections_with_banks.append({
                        "section_type": section,
                        "context": context
                    })
            
            analysis = {
                "bank_keywords_found": found_keywords,
                "total_bank_mentions": sum(found_keywords.values()),
                "potential_bank_sections": len(sections_with_banks),
                "section_contexts": sections_with_banks[:3]  # Top 3 for brevity
            }
            
            logger.info(f"Bank Variation Analysis for {Path(pdf_path).name}:")
            logger.info(f"  Bank-related keywords: {len(found_keywords)} types found")
            logger.info(f"  Total bank mentions: {analysis['total_bank_mentions']}")
            logger.info(f"  Potential bank sections: {analysis['potential_bank_sections']}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Bank variation analysis failed: {e}")
            return {"error": str(e)}
    
    def theory_3_document_type_confusion(self, pdf_path):
        """Theory 3: Wrong document types (not Final Terms)"""
        try:
            text = self.extraction_engine.extract_text(pdf_path)
            
            # Document type indicators
            doc_type_indicators = {
                "final_terms": ["final terms", "final term", "pricing supplement"],
                "base_prospectus": ["base prospectus", "programme", "framework"],
                "supplement": ["supplement", "amendment", "addendum"],
                "annual_report": ["annual report", "financial statements"],
                "regulatory": ["regulatory", "compliance", "filing"]
            }
            
            detected_types = {}
            text_lower = text.lower()
            
            for doc_type, keywords in doc_type_indicators.items():
                count = sum(text_lower.count(keyword) for keyword in keywords)
                if count > 0:
                    detected_types[doc_type] = count
            
            # Check filename patterns
            filename = Path(pdf_path).name.lower()
            filename_indicators = {
                "final_terms": "final" in filename and "terms" in filename,
                "base_prospectus": "base" in filename or "prospectus" in filename,
                "supplement": "supplement" in filename,
                "unknown": "unknown" in filename
            }
            
            analysis = {
                "detected_document_types": detected_types,
                "primary_type": max(detected_types.items(), key=lambda x: x[1])[0] if detected_types else "unknown",
                "filename_indicators": {k: v for k, v in filename_indicators.items() if v},
                "confidence": max(detected_types.values()) if detected_types else 0
            }
            
            logger.info(f"Document Type Analysis for {Path(pdf_path).name}:")
            logger.info(f"  Primary type: {analysis['primary_type']} (confidence: {analysis['confidence']})")
            logger.info(f"  Filename indicators: {list(analysis['filename_indicators'].keys())}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Document type analysis failed: {e}")
            return {"error": str(e)}
    
    def theory_4_text_truncation(self, pdf_path):
        """Theory 4: AI only sees first 1500 chars, banks might be later"""
        try:
            text = self.extraction_engine.extract_text(pdf_path)
            
            # Analyze where bank-related content appears
            bank_keywords = ["bank", "underwriter", "manager", "arranger", "dealer"]
            
            # Check distribution of bank keywords throughout document
            text_length = len(text)
            chunk_size = 1500
            chunks = [text[i:i+chunk_size] for i in range(0, text_length, chunk_size)]
            
            keyword_distribution = []
            for i, chunk in enumerate(chunks):
                chunk_keywords = {}
                for keyword in bank_keywords:
                    count = chunk.lower().count(keyword.lower())
                    if count > 0:
                        chunk_keywords[keyword] = count
                
                if chunk_keywords:
                    keyword_distribution.append({
                        "chunk_index": i,
                        "char_range": f"{i*chunk_size}-{min((i+1)*chunk_size, text_length)}",
                        "keywords": chunk_keywords,
                        "total_mentions": sum(chunk_keywords.values())
                    })
            
            analysis = {
                "total_text_length": text_length,
                "total_chunks": len(chunks),
                "ai_sees_first": 1500,
                "ai_coverage_percent": min(100, (1500 / text_length) * 100) if text_length > 0 else 0,
                "keyword_distribution": keyword_distribution,
                "banks_in_first_chunk": keyword_distribution[0] if keyword_distribution and keyword_distribution[0]["chunk_index"] == 0 else None,
                "banks_in_later_chunks": [d for d in keyword_distribution if d["chunk_index"] > 0]
            }
            
            logger.info(f"Text Truncation Analysis for {Path(pdf_path).name}:")
            logger.info(f"  AI sees: {analysis['ai_coverage_percent']:.1f}% of document")
            logger.info(f"  Bank mentions in first chunk: {bool(analysis['banks_in_first_chunk'])}")
            logger.info(f"  Bank mentions in later chunks: {len(analysis['banks_in_later_chunks'])}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Text truncation analysis failed: {e}")
            return {"error": str(e)}
    
    def _calculate_readable_ratio(self, text):
        """Calculate ratio of readable characters to total"""
        if not text:
            return 0.0
        
        readable_chars = sum(1 for c in text if c.isalnum() or c.isspace() or c in ".,!?()-")
        return readable_chars / len(text)
    
    def _detect_garbled_text(self, text):
        """Detect if text contains garbled/OCR artifacts"""
        if not text:
            return True
        
        # Look for common OCR/extraction artifacts
        artifacts = ["���", "□", "○", "●", "▪", "▫", "■", "□"]
        garbled_patterns = [
            lambda t: len([c for c in t if not c.isprintable()]) > len(t) * 0.05,  # >5% non-printable
            lambda t: any(artifact in t for artifact in artifacts),
            lambda t: len(t.split()) < len(t) * 0.1,  # Very few words vs characters
        ]
        
        return any(pattern(text) for pattern in garbled_patterns)

def main():
    # Test on the PDFs that failed AI extraction
    failed_pdfs = [
        "data/downloads/AKER BP ASA - 549300NFTY73920OYK69/Base prospectus without Final terms_02_11_2023.pdf",
        "data/downloads/AKER BP ASA - 549300NFTY73920OYK69/Final terms, including the  summary of the individual issue annexed to them_28_05_2024.pdf",
        "data/downloads/TotalEnergies SE_Final_terms_including_the_summary_of_the_individual_issue_annexed_to_them__downloadFile.pdf"
    ]
    
    diagnostic = FailureDiagnostic()
    
    for pdf_path in failed_pdfs:
        if not os.path.exists(pdf_path):
            logger.warning(f"PDF not found: {pdf_path}")
            continue
            
        filename = Path(pdf_path).name
        logger.info(f"\n{'='*60}")
        logger.info(f"DIAGNOSING: {filename}")
        logger.info(f"{'='*60}")
        
        # Theory 1: Text Quality
        logger.info("\n🔍 THEORY 1: Text Quality Issues")
        diagnostic.theory_1_text_quality(pdf_path)
        
        # Theory 2: Bank Name Variations
        logger.info("\n🔍 THEORY 2: Bank Name Variations")
        diagnostic.theory_2_bank_name_variations(pdf_path)
        
        # Theory 3: Document Type Confusion
        logger.info("\n🔍 THEORY 3: Document Type Confusion")
        diagnostic.theory_3_document_type_confusion(pdf_path)
        
        # Theory 4: Text Truncation
        logger.info("\n🔍 THEORY 4: Text Truncation Issues")
        diagnostic.theory_4_text_truncation(pdf_path)

if __name__ == "__main__":
    main() 