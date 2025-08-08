# PDF Extractor Debugging Tools

This directory contains debugging tools for analyzing and troubleshooting the PDF extraction pipeline, particularly the extractors for dates, currencies, and coupon information.

## Overview

The debugging suite now includes a comprehensive set of tools for analyzing extraction issues:

1. **debug_all_extractors.py** - Tests all regex patterns against PDF content and provides detailed information
2. **debug_extractions_visualizer.py** - Provides visual highlighting of pattern matches with colored context
3. **batch_debug_extractors.py** - Processes multiple PDFs and generates aggregated statistics 
4. **debug_extraction_report.py** - Creates comprehensive HTML reports with visualizations and suggestions

These tools are designed to help:
- Identify why extractors might fail to extract certain information
- Visualize which patterns match and where they match in the document
- Generate actionable suggestions for improving extraction patterns
- Track extraction performance across multiple documents

## How to Use

### Basic Usage

For a quick analysis of a single PDF:

```bash
python debug_all_extractors.py "path/to/pdf/file.pdf"
```

The script will process the PDF and output detailed extraction information including:
- Pattern matches for issue dates, maturity dates, currency codes, issue sizes, and coupon information
- Extraction results from each extractor
- Statistics about which patterns were most successful
- Suggestions for improving extraction patterns

### Visual Debugging

For a more visual approach with highlighted pattern matches:

```bash
python debug_extractions_visualizer.py "path/to/pdf/file.pdf"
```

This tool provides color-coded highlighting of matches in their context, making it easier to understand why patterns are matching or not matching.

### Testing Custom Patterns

To test a specific regex pattern against a PDF:

```bash
python debug_extractions_visualizer.py "path/to/pdf/file.pdf" --test-pattern "your_regex_pattern" --pattern-type "date"
```

This allows you to interactively develop and test new patterns before adding them to the pattern registry.

### Batch Processing

To analyze multiple PDFs and generate statistics:

```bash
python batch_debug_extractors.py "path/to/pdf/directory/" --output-dir results
```

This processes multiple PDFs and provides:
- Success rate statistics for each field type
- Visualizations of extraction performance
- JSON and CSV reports of results

### Comprehensive Reporting

For the most detailed analysis with HTML reports and visualizations:

```bash
python debug_extraction_report.py "path/to/pdf/directory/" --output-dir report_results --interactive
```

This creates:
- Interactive HTML reports
- Field success rate visualizations
- Pattern usage statistics
- Detailed suggestions for pattern improvements

## Installation Requirements

The debugging tools require the following dependencies:
- colorama (for colored terminal output)
- pandas (for data analysis)
- matplotlib (for visualizations)
- tqdm (for progress bars)
- All dependencies of the main extraction pipeline

You can install these with:

```bash
pip install colorama pandas matplotlib tqdm
```

## Debugging Output Sections

### Date Extraction

This section shows:
- Which issue date and maturity date patterns match in the document
- Sample matches with surrounding context
- The final extracted date values
- Common date formats found in the document

### Currency Extraction

This section shows:
- Matches for issue size patterns
- Detected currency codes and symbols
- The final extracted currency and issue size values

### Coupon Extraction

This section shows:
- Matches for coupon rate patterns
- Detected coupon types
- The final extracted coupon information

### Improvement Suggestions

The tools automatically generate suggestions for improving extraction patterns based on the analysis, such as:
- Adding specific date patterns to match formats found in the document
- Adding currency patterns for detected currency codes
- Adding coupon rate patterns for percentage values found in the document

### Pattern Statistics

Shows which patterns were most successful across tested documents, helping identify:
- Patterns that are rarely used and might need revision
- Most effective patterns that capture many cases
- Patterns that might be too specific or too general

## Improving Extraction Performance

For a detailed guide on how to use these tools to improve extraction performance, see the comprehensive [README_debugging_tools.md](README_debugging_tools.md) file, which includes:

- Step-by-step workflows for pattern improvement
- Troubleshooting common extraction issues
- Best practices for adding new patterns
- Strategies for analyzing extraction statistics

## Example Output

```
================================================================================
Processing PDF: example.pdf
================================================================================

===== DEBUGGING DATE EXTRACTION =====

Testing issue date patterns:
Issue date Pattern 6: 4 matches
  Match 1: '13 FEBRUARY 2025' in context:
    ...SECOND SUPPLEMENT DATED 13 FEBRUARY 2025 TO THE DEBT ISSUANCE PROGRAMM...

DateExtractor results:
  issue_date: 2025-02-13
  maturity_date: Not found

===== DEBUGGING CURRENCY EXTRACTION =====

Testing issue size patterns:
Issue size Pattern 12: 3 matches
  Match 1: '$' in context:
    ... Brent prices remain volatile between $70 and $80/b, supported by the willingne...

CurrencyExtractor results:
  issue_size: 2525000.0
  currency: Not found
  issue_size_range: {'min': '2500000', 'max': '2550000'}

===== IMPROVEMENT SUGGESTIONS =====

1. Add maturity date patterns to match future dates like: 4 February 2026, 4 February 2026
2. Add currency pattern to detect 'USD' mentions

===== EXTRACTION SUMMARY =====

File: example.pdf
Extraction confidence: MEDIUM
Extraction time: 0.38 seconds
Validation flags: 1
Successfully extracted fields: 5
```

## Document Types

Different document types may require specific patterns:

- **Prospectuses**: Often contain standardized sections with issue and maturity dates
- **Final Terms**: Contain structured information about issue size, currency, and coupon rates
- **Supplements**: May reference original document dates

## Maintenance

Periodically run the debugging tools on a sample of documents to:
- Monitor extraction success rates
- Identify common failure patterns
- Add new patterns for emerging document formats 