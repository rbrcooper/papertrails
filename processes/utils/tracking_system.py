"""
Tracking System
-------------
This module handles tracking of failed extractions, downloads, and processing attempts.
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class TrackingSystem:
    """Handles tracking of various system events and failures"""
    
    def __init__(self, base_dir='data'):
        """Initialize the tracking system"""
        self.base_dir = Path(base_dir)
        self.tracking_dir = self.base_dir / 'tracking'
        
        # Create tracking directory if it doesn't exist
        self.tracking_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize tracking files
        self.failed_extractions_file = self.tracking_dir / 'failed_extractions.json'
        self.download_status_file = self.tracking_dir / 'download_status.json'
        self.processing_attempts_file = self.tracking_dir / 'processing_attempts.json'
        self.recovery_log_file = self.tracking_dir / 'recovery_log.json'
        
        # Initialize tracking data
        self._init_tracking_files()
    
    def _init_tracking_files(self):
        """Initialize tracking files if they don't exist"""
        files = {
            self.failed_extractions_file: [],
            self.download_status_file: [],
            self.processing_attempts_file: [],
            self.recovery_log_file: []
        }
        
        for file, default_data in files.items():
            if not file.exists():
                with open(file, 'w') as f:
                    json.dump(default_data, f, indent=2)
    
    def _load_tracking_data(self, file_path):
        """Load tracking data from a file"""
        try:
            if not file_path.exists():
                return []
            with open(file_path, 'r') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Error loading tracking data from {file_path}: {str(e)}")
            return []
    
    def _save_tracking_data(self, file_path, data):
        """Save tracking data to a file"""
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving tracking data to {file_path}: {str(e)}")
    
    def track_failed_extraction(self, company_name, reason, details=None):
        """Track a failed extraction attempt"""
        data = self._load_tracking_data(self.failed_extractions_file)
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'company_name': company_name,
            'reason': reason,
            'details': details or {}
        }
        
        data.append(entry)
        self._save_tracking_data(self.failed_extractions_file, data)
        logger.warning(f"Tracked failed extraction for {company_name}: {reason}")
    
    def track_download_status(self, company_name, document_id, status, details=None):
        """Track the status of a document download"""
        data = self._load_tracking_data(self.download_status_file)
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'company_name': company_name,
            'document_id': document_id,
            'status': status,
            'details': details or {}
        }
        
        data.append(entry)
        self._save_tracking_data(self.download_status_file, data)
        logger.info(f"Tracked download status for {company_name} - {document_id}: {status}")
    
    def track_processing_attempt(self, company_name, document_id, status, details=None):
        """Track a document processing attempt"""
        data = self._load_tracking_data(self.processing_attempts_file)
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'company_name': company_name,
            'document_id': document_id,
            'status': status,
            'details': details or {}
        }
        
        data.append(entry)
        self._save_tracking_data(self.processing_attempts_file, data)
        logger.info(f"Tracked processing attempt for {company_name} - {document_id}: {status}")
    
    def log_recovery_attempt(self, company_name, document_id, action, result, details=None):
        """Log a recovery attempt"""
        data = self._load_tracking_data(self.recovery_log_file)
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'company_name': company_name,
            'document_id': document_id,
            'action': action,
            'result': result,
            'details': details or {}
        }
        
        data.append(entry)
        self._save_tracking_data(self.recovery_log_file, data)
        logger.info(f"Logged recovery attempt for {company_name} - {document_id}: {action} - {result}")
    
    def generate_failure_report(self):
        """Generate a report of all failures"""
        failed_extractions = self._load_tracking_data(self.failed_extractions_file)
        download_status = self._load_tracking_data(self.download_status_file)
        processing_attempts = self._load_tracking_data(self.processing_attempts_file)
        
        report = {
            'failed_extractions': failed_extractions,
            'failed_downloads': [d for d in download_status if d['status'] == 'failed'],
            'failed_processing': [p for p in processing_attempts if p['status'] == 'failed']
        }
        
        return report
    
    def export_to_excel(self, output_path=None):
        """Export tracking data to Excel"""
        if output_path is None:
            output_path = self.tracking_dir / 'tracking_report.xlsx'
        
        # Implementation for Excel export would go here
        # This is a placeholder for future implementation
        logger.info(f"Excel export would be saved to {output_path}") 