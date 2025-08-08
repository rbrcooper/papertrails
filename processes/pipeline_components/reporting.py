from collections import defaultdict, Counter
# Assuming DatabaseHandler will be imported or passed correctly.
# from .database_handler import DatabaseHandler

class ValidationReporter:
    def __init__(self, db_handler):
        # db_handler is an instance of DatabaseHandler
        self.db = db_handler
        
    def generate_validation_report(self):
        # Assumes db_handler.get_all_validation_results() method exists
        # and returns a list of dicts, where each dict represents a validation result record.
        # Each record is expected to have keys like: 
        # 'is_valid' (bool), 
        # 'confidence_scores' (dict), 
        # 'flags' (list of strings),
        # 'fields_present' (list of strings indicating which fields were extracted)
        results = self.db.get_all_validation_results()
        
        if not results:
            return {
                'total_documents': 0,
                'valid_documents': 0,
                'field_confidence_avg': {},
                'common_flags': {},
                'field_completion_rate': {},
                'message': 'No validation results found to generate a report.'
            }

        report = {
            'total_documents': len(results),
            'valid_documents': sum(1 for r in results if r.get('is_valid', False)),
            'field_confidence_raw': defaultdict(list), # Stores all confidence scores per field
            'common_flags': Counter(),
            'field_completion_count': defaultdict(int) # Counts how many times each field is present
        }
        
        required_fields_for_completion_tracking = set() # To dynamically get all possible fields

        for result in results:
            # Track confidence scores
            confidence_scores = result.get('confidence_scores', {})
            if isinstance(confidence_scores, dict):
                for field, score in confidence_scores.items():
                    try:
                        report['field_confidence_raw'][field].append(float(score))
                    except (ValueError, TypeError):
                        # Log or skip non-numeric scores
                        pass 
                        
            # Track validation flags
            flags = result.get('flags', [])
            if isinstance(flags, list):
                report['common_flags'].update(flags)
            
            # Track field completion based on 'fields_present' from validation result
            # The prompt snippet shows 'fields_present', but ExtractionValidator (Phase 2) doesn't explicitly create it.
            # Assuming it is added to the validation result elsewhere, or that required_fields from ExtractionValidator can be used.
            # For robustness, let's assume 'extraction_result' (that was validated) is available or its keys.
            # If 'fields_present' key exists in the result: 
            fields_present = result.get('fields_present') # This key was in the prompt for ValidationReporter
            if fields_present and isinstance(fields_present, list):
                for field in fields_present:
                    report['field_completion_count'][field] += 1
                    required_fields_for_completion_tracking.add(field)
            else: # Fallback: if 'fields_present' is not there, try to infer from extraction_result keys if available
                  # This part is speculative as 'extraction_result' is not directly passed here.
                  # If 'extraction_result' (the raw one) was part of the stored validation result, one could use its keys.
                  # For now, this part remains dependent on 'fields_present' being correctly populated in DB.
                  pass 

        # Calculate average confidence scores
        report['field_confidence_avg'] = {
            field: sum(scores) / len(scores) if scores else 0
            for field, scores in report['field_confidence_raw'].items()
        }
        # del report['field_confidence_raw'] # Optionally remove raw scores from final report

        # Calculate field completion rate
        report['field_completion_rate'] = {}
        if report['total_documents'] > 0:
            all_fields_ever_present = set(report['field_completion_count'].keys())
            for field_name in all_fields_ever_present: # Iterate over fields actually found
                count = report['field_completion_count'][field_name]
                report['field_completion_rate'][field_name] = (count / report['total_documents']) * 100
        
        # Convert Counter to dict for JSON serialization if needed later
        report['common_flags'] = dict(report['common_flags'])

        return report 