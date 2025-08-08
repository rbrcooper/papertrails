# ESMA Bond Data Tracker - Unified Task Prompts

## Project Overview

The ESMA Bond Data Tracker extracts and aggregates bond underwriter information from ESMA Prospectus documents. This tool helps campaigners and researchers analyze relationships between companies and their bond underwriters.

**Key MVP Requirements:**
- Extract accurate bond data from downloaded ESMA prospectuses
- Focus fields: Issuer, Banks/Bookrunners, Issue Size & Currency, Dates, Coupon Rates
- Provide consolidated output in JSON and Excel formats
- Achieve >80-90% accuracy in field extraction

## Current Project State (Updated)

### Completed Components ✅
- Mature PDF extraction system with modular architecture
- Comprehensive test and debugging infrastructure
- Individual extractors for all key fields (dates, currency, coupon, banks)
- Extensive debugging and visualization tools
- Basic database schema implementation

### In Progress Components 🔄
- Extraction accuracy improvements (target: >80-90%)
- Pattern refinement based on debug results
- Bank name standardization

### Not Started Components ❌
- Pipeline integration with main workflow
- Final output generation (JSON/Excel)
- Full validation implementation
- Database population and querying

## Phase 1: Extraction Refinement (Current Focus)

### Task 1.1: Systematic Accuracy Improvement

```markdown
## CONTEXT
The extraction system has sophisticated components but needs systematic accuracy improvements. Current validation flags show issues like "no_dates_extracted", "no_currency_info_extracted", and "no_coupon_info_extracted" in some cases.

## CURRENT CODE STATUS
- Comprehensive extractors in `processes/pdf_extraction/extractors/`:
  - `date_extractor.py`: Date parsing with multiple formats
  - `currency_extractor.py`: Currency and amount extraction
  - `coupon_extractor.py`: Various coupon rate types
  - `bank_extractor.py`: Bank name identification
- Debug tools in `processes/tests/`:
  - `debug_extraction_report.py`: Detailed extraction analysis
  - `debug_extractions_visualizer.py`: Pattern matching visualization
  - `batch_debug_extractors.py`: Bulk testing utility

## SPECIFIC TASK
1. Use existing debug tools to analyze extraction failures:

   ```python
   # Example usage of debug tools
   from processes.tests.debug_extraction_report import ExtractionDebugger
   from processes.tests.debug_extractions_visualizer import PatternVisualizer
   
   # Initialize debugger
   debugger = ExtractionDebugger()
   
   # Analyze sample PDFs
   results = debugger.analyze_pdfs(
       pdf_dir="data/downloads/sample_pdfs",
       extractors=['date', 'currency', 'coupon'],
       output_format='detailed'
   )
   
   # Visualize patterns
   visualizer = PatternVisualizer()
   pattern_analysis = visualizer.analyze_patterns(
       results,
       show_context=True,
       highlight_matches=True
   )
   ```

2. For each extractor, implement systematic improvements:

   ```python
   # Example: Enhanced date extraction
   class DateExtractor:
       def __init__(self):
           self.patterns = {
               'high_confidence': [
                   # Explicit date labels
                   r'(?P<label>Issue Date|Maturity Date):\s*(?P<date>\d{1,2}[\s./-]\w+[\s./-]\d{2,4})',
                   r'(?P<label>Dated|Maturing):\s*(?P<date>\d{1,2}[\s./-]\w+[\s./-]\d{2,4})'
               ],
               'medium_confidence': [
                   # Date formats without explicit labels
                   r'\b(?P<date>\d{1,2}[\s./-]\w+[\s./-]\d{2,4})\b'
               ]
           }
           self.date_parser = DateParser(
               fuzzy=True,
               settings={
                   'PREFER_DAY_OF_MONTH': True,
                   'STRICT_PARSING': False
               }
           )
   
       def extract_with_confidence(self, text):
           results = []
           for confidence, patterns in self.patterns.items():
               for pattern in patterns:
                   matches = self._find_matches(text, pattern)
                   if matches:
                       results.append({
                           'date': matches.group('date'),
                           'confidence': confidence,
                           'context': self._get_context(text, matches)
                       })
           return self._resolve_conflicts(results)
   ```

3. Implement comprehensive metrics collection:
   ```python
   class ExtractionMetrics:
       def __init__(self):
           self.metrics = {
               'total_documents': 0,
               'successful_extractions': 0,
               'field_accuracy': defaultdict(list),
               'pattern_success': defaultdict(Counter),
               'error_types': Counter()
           }
   
       def record_extraction(self, result, ground_truth=None):
           self.metrics['total_documents'] += 1
           if result['success']:
               self.metrics['successful_extractions'] += 1
           
           # Record pattern successes
           for field, patterns in result['matched_patterns'].items():
               self.metrics['pattern_success'][field].update(patterns)
           
           # Record accuracy if ground truth available
           if ground_truth:
               for field in ['dates', 'currency', 'coupon']:
                   accuracy = self._calculate_accuracy(
                       result[field],
                       ground_truth[field]
                   )
                   self.metrics['field_accuracy'][field].append(accuracy)
   ```

## SUCCESS CRITERIA
- Achieve >80% accuracy for each field type, measured against test dataset
- Document all pattern improvements with examples
- Create comprehensive regression test suite
- Generate detailed accuracy reports per field type
```

### Task 1.2: Bank Name Standardization

```markdown
## CONTEXT
Bank names appear in various formats across documents (e.g., "Deutsche Bank AG", "Deutsche Bank", "DB AG"). Accurate relationship tracking requires standardizing these variations to canonical names.

## CURRENT CODE STATUS
- Basic standardization in bank_extractor.py using simple string matching
- Need fuzzy matching and comprehensive name mapping
- Current accuracy around 70-75%

## SPECIFIC TASK
1. Create comprehensive bank name mapping system:

   ```python
   class BankNameStandardizer:
       def __init__(self):
           self.canonical_names = self._load_canonical_names()
           self.fuzzy_matcher = FuzzyMatcher(
               threshold=0.85,
               scoring='weighted_ratio'
           )
           
       def standardize_name(self, raw_name):
           # Direct match attempt
           if raw_name in self.canonical_names:
               return {
                   'standardized_name': self.canonical_names[raw_name],
                   'confidence': 1.0,
                   'method': 'direct_match'
               }
           
           # Clean and normalize
           cleaned_name = self._clean_name(raw_name)
           if cleaned_name in self.canonical_names:
               return {
                   'standardized_name': self.canonical_names[cleaned_name],
                   'confidence': 0.95,
                   'method': 'cleaned_match'
               }
           
           # Fuzzy matching
           matches = self.fuzzy_matcher.find_matches(
               cleaned_name,
               self.canonical_names.keys()
           )
           
           if matches:
               best_match = matches[0]
               return {
                   'standardized_name': self.canonical_names[best_match],
                   'confidence': best_match.score,
                   'method': 'fuzzy_match'
               }
           
           return {
               'standardized_name': raw_name,
               'confidence': 0.0,
               'method': 'no_match'
           }
   
       def _clean_name(self, name):
           """
           Clean and normalize bank name:
           - Remove legal entity types (AG, Ltd, etc.)
           - Standardize spacing and punctuation
           - Handle common abbreviations
           """
           # Implementation details...
   ```

2. Integrate with extraction pipeline:

   ```python
   class BankExtractor:
       def __init__(self):
           self.standardizer = BankNameStandardizer()
           self.patterns = self._compile_patterns()
           
       def extract_banks(self, text):
           raw_banks = self._extract_raw_banks(text)
           standardized_banks = []
           
           for raw_bank in raw_banks:
               result = self.standardizer.standardize_name(raw_bank)
               if result['confidence'] >= 0.85:
                   standardized_banks.append({
                       'raw_name': raw_bank,
                       'standardized_name': result['standardized_name'],
                       'confidence': result['confidence'],
                       'method': result['method']
                   })
           
           return {
               'banks': standardized_banks,
               'validation_flags': self._generate_validation_flags(standardized_banks)
           }
   ```

## SUCCESS CRITERIA
- >90% accuracy in bank name standardization
- Documented mapping rules with examples
- Comprehensive test suite for name variations
- Clear confidence scoring system
```

## Phase 2: Pipeline Integration

### Task 2.1: Main Workflow Integration

```markdown
## CONTEXT
The refined extractors need to be integrated into the main pipeline for end-to-end processing. Currently, main.py only handles scraping without extraction.

## CURRENT CODE STATUS
- main.py runs scraper only
- Extractors work independently
- No pipeline integration
- Database schema exists but unused

## SPECIFIC TASK
1. Enhance main.py for full pipeline:

   ```python
   class ESMAProcessor:
       def __init__(self):
           self.scraper = ESMAScraper()
           self.extractor = PDFExtractor()
           self.db = DatabaseHandler()
           self.logger = self._setup_logger()
           
       def process_company(self, company):
           try:
               # Download documents
               pdfs = self.scraper.download_documents(company)
               
               # Process each PDF
               results = []
               for pdf in pdfs:
                   try:
                       # Extract data
                       extraction_result = self.extractor.process_single_pdf(pdf)
                       
                       # Validate
                       validation_result = self._validate_extraction(
                           extraction_result
                       )
                       
                       # Store if valid
                       if validation_result['is_valid']:
                           self.db.store_result(
                               company,
                               extraction_result,
                               validation_result
                           )
                           
                       results.append({
                           'pdf': pdf,
                           'extraction': extraction_result,
                           'validation': validation_result
                       })
                       
                   except Exception as e:
                       self.logger.error(f"Error processing {pdf}: {e}")
                       results.append({
                           'pdf': pdf,
                           'error': str(e)
                       })
                       
               return results
               
           except Exception as e:
               self.logger.error(f"Error processing company {company}: {e}")
               return None
   ```

2. Implement validation system:

   ```python
   class ExtractionValidator:
       def __init__(self):
           self.required_fields = ['issuer', 'banks', 'dates', 'currency']
           self.confidence_thresholds = {
               'banks': 0.85,
               'dates': 0.80,
               'currency': 0.90
           }
           
       def validate_extraction(self, result):
           validation = {
               'is_valid': True,
               'flags': [],
               'confidence_scores': {}
           }
           
           # Check required fields
           for field in self.required_fields:
               if not result.get(field):
                   validation['is_valid'] = False
                   validation['flags'].append(f'missing_{field}')
           
           # Check confidence scores
           for field, threshold in self.confidence_thresholds.items():
               if result.get(field):
                   confidence = result[field].get('confidence', 0)
                   validation['confidence_scores'][field] = confidence
                   
                   if confidence < threshold:
                       validation['flags'].append(f'low_confidence_{field}')
                       if confidence < threshold * 0.5:
                           validation['is_valid'] = False
           
           return validation
   ```

## SUCCESS CRITERIA
- End-to-end pipeline working reliably
- Proper error handling and recovery
- Comprehensive logging and monitoring
- >95% pipeline completion rate
```

## Phase 3: Output Generation

### Task 3.1: Data Aggregation and Export

```markdown
## CONTEXT
Need to generate consolidated outputs in JSON and Excel formats that provide both detailed data and useful summaries.

## CURRENT CODE STATUS
- No output generation implemented
- Database schema exists but unused
- No data aggregation logic

## SPECIFIC TASK
1. Implement data aggregation system:

   ```python
   class DataAggregator:
       def __init__(self, db_handler):
           self.db = db_handler
           
       def aggregate_results(self, start_date=None, end_date=None):
           # Get all results from DB
           results = self.db.get_results(
               start_date=start_date,
               end_date=end_date
           )
           
           # Aggregate by company
           aggregated = defaultdict(lambda: {
               'company_name': '',
               'total_bonds': 0,
               'total_amount': defaultdict(float),
               'banks': defaultdict(int),
               'bonds': []
           })
           
           for result in results:
               company = result['company_name']
               agg = aggregated[company]
               
               # Update company stats
               agg['total_bonds'] += 1
               if result.get('currency_info'):
                   currency = result['currency_info']['currency']
                   amount = result['currency_info']['amount']
                   agg['total_amount'][currency] += amount
                   
               # Update bank relationships
               for bank in result.get('banks', []):
                   agg['banks'][bank['standardized_name']] += 1
                   
               # Add bond details
               agg['bonds'].append({
                   'issue_date': result.get('issue_date'),
                   'maturity_date': result.get('maturity_date'),
                   'currency': result.get('currency_info', {}).get('currency'),
                   'amount': result.get('currency_info', {}).get('amount'),
                   'coupon_rate': result.get('coupon_info'),
                   'banks': [b['standardized_name'] for b in result.get('banks', [])]
               })
           
           return aggregated
   ```

2. Create output generators:

   ```python
   class OutputGenerator:
       def __init__(self, aggregator):
           self.aggregator = aggregator
           
       def generate_json(self, output_path):
           data = self.aggregator.aggregate_results()
           
           # Add metadata
           output = {
               'generated_at': datetime.now().isoformat(),
               'total_companies': len(data),
               'total_bonds': sum(c['total_bonds'] for c in data.values()),
               'companies': data
           }
           
           with open(output_path, 'w') as f:
               json.dump(output, f, indent=2)
               
       def generate_excel(self, output_path):
           data = self.aggregator.aggregate_results()
           
           # Create Excel writer
           with pd.ExcelWriter(output_path) as writer:
               # Summary sheet
               self._create_summary_sheet(data, writer)
               
               # Company details sheet
               self._create_company_sheet(data, writer)
               
               # Bond details sheet
               self._create_bond_sheet(data, writer)
               
               # Bank relationships sheet
               self._create_bank_sheet(data, writer)
   ```

3. Implement validation reporting:

   ```python
   class ValidationReporter:
       def __init__(self, db_handler):
           self.db = db_handler
           
       def generate_validation_report(self):
           results = self.db.get_all_validation_results()
           
           report = {
               'total_documents': len(results),
               'valid_documents': sum(1 for r in results if r['is_valid']),
               'field_confidence': defaultdict(list),
               'common_flags': Counter(),
               'field_completion': defaultdict(int)
           }
           
           for result in results:
               # Track confidence scores
               for field, score in result['confidence_scores'].items():
                   report['field_confidence'][field].append(score)
                   
               # Track validation flags
               report['common_flags'].update(result['flags'])
               
               # Track field completion
               for field in result['fields_present']:
                   report['field_completion'][field] += 1
                   
           return report
   ```

## SUCCESS CRITERIA
- Complete and accurate JSON/Excel outputs
- Useful summary statistics and visualizations
- Comprehensive validation reporting
- Clear documentation of output formats
```

## Using These Prompts

1. Start with Phase 1 tasks:
   - Use existing debug tools systematically
   - Document all improvements and patterns
   - Build comprehensive test cases

2. Move to Phase 2 once accuracy targets met:
   - Implement pipeline components incrementally
   - Test thoroughly at each integration point
   - Ensure proper error handling

3. Complete Phase 3 after stable pipeline:
   - Focus on data quality and completeness
   - Create useful aggregations and summaries
   - Implement comprehensive validation

## Success Metrics

- Extraction accuracy >80-90% for all fields
- Bank name standardization >90% accuracy
- Pipeline completion rate >95%
- Comprehensive validation reporting
- Complete and accurate outputs
- Clear documentation and examples 