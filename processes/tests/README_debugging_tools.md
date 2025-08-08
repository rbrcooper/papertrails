# PDF Extraction Debugging Tools

This directory contains a comprehensive suite of debugging tools for analyzing, troubleshooting, and improving the PDF extraction pipeline. These tools help identify why extractors might fail to extract certain information and provide actionable suggestions for improving the extraction patterns.

## Overview

The debugging suite consists of several complementary tools:

1. **debug_all_extractors.py** - Tests all extraction patterns against a single PDF and shows detailed results
2. **debug_extractions_visualizer.py** - Provides visual highlighting of pattern matches in context
3. **batch_debug_extractors.py** - Processes multiple PDFs and generates aggregated statistics
4. **debug_extraction_report.py** - Creates comprehensive reports with visualizations and improvement suggestions

## Quick Start

### Debugging a Single PDF

To debug extraction issues in a single PDF:

```bash
python debug_all_extractors.py path/to/your/file.pdf
```

This will show which patterns match, what information is extracted, and suggestions for improvements.

### Visual Pattern Debugging

For a more visual approach with highlighted matches:

```bash
python debug_extractions_visualizer.py path/to/your/file.pdf
```

### Testing Custom Patterns

To test a specific regex pattern against a PDF:

```bash
python debug_extractions_visualizer.py path/to/your/file.pdf --test-pattern "your_regex_pattern" --pattern-type "date"
```

### Batch Processing

To analyze multiple PDFs and generate statistics:

```bash
python batch_debug_extractors.py path/to/pdf/directory/ --output-dir results
```

### Comprehensive Reporting

For detailed analysis with HTML reports and visualizations:

```bash
python debug_extraction_report.py path/to/pdf/directory/ --output-dir report_results --interactive
```

## Detailed Tool Descriptions

### debug_all_extractors.py

This script provides a detailed analysis of how each extractor performs on a single PDF:

- Shows which patterns match in the document
- Displays matched text with surrounding context
- Reports final extracted values
- Generates suggestions for improving extraction

**Options:**
- `--quiet` or `-q`: Suppress console output (for programmatic use)

**Example Output Sections:**
- Date Extraction: Shows issue date and maturity date pattern matches
- Currency Extraction: Shows currency code/symbol and issue size matches
- Coupon Extraction: Shows coupon rate and type pattern matches
- Improvement Suggestions: Provides specific ideas for enhancing extraction
- Pattern Statistics: Shows which patterns were most successful

### debug_extractions_visualizer.py

This tool provides a more visual approach to debugging extraction patterns:

- Highlights pattern matches in context with color coding
- Displays categorized results by pattern type
- Tests patterns directly and suggests similar patterns
- Generates JSON output for further analysis

**Options:**
- `--output-dir` or `-o`: Directory to save results
- `--quiet` or `-q`: Suppress console output
- `--test-pattern` or `-p`: Test a custom pattern against the PDF
- `--pattern-type` or `-t`: Type of pattern being tested (date, currency, coupon, etc.)

**Features:**
- Color-coded match highlighting
- Context display for each pattern match
- Pattern similarity suggestions when tests fail
- Interactive pattern testing

### batch_debug_extractors.py

This script runs the extraction process on multiple PDFs and provides aggregated statistics:

- Processes a directory of PDFs
- Generates success rate statistics
- Creates visualizations of extraction performance
- Outputs detailed reports in JSON and CSV formats

**Options:**
- `--output-dir`: Directory to save results (default: "extractor_results")
- `--limit`: Maximum number of PDFs to process
- `--pattern`: Glob pattern to filter PDFs (e.g., '**/*.pdf')

**Output:**
- Success rate charts as PNG files
- Confidence level visualizations
- JSON summary of extraction statistics
- CSV report with per-file results

### debug_extraction_report.py

This is the most comprehensive debugging tool, providing detailed reports:

- Processes multiple PDFs with detailed analysis
- Generates HTML reports with visualizations
- Provides pattern improvement suggestions
- Identifies patterns that rarely or never match

**Options:**
- `--output-dir`: Directory to save results (default: "extraction_debug_results")
- `--limit`: Maximum number of PDFs to process
- `--pattern`: Glob pattern to filter PDFs
- `--interactive`: Run in interactive mode with detailed visualizations

**Output:**
- HTML report with interactive elements
- Field success rate visualizations
- Pattern usage statistics
- Pattern improvement suggestions file
- Detailed JSON and CSV results

## Improving Extraction Patterns

The debugging tools provide specific suggestions for improving extraction patterns. Here's how to use them:

1. Run `debug_all_extractors.py` or `debug_extractions_visualizer.py` on problematic PDFs
2. Review the "Improvement Suggestions" section
3. Use the suggested patterns as a basis for enhancing PatternRegistry
4. Add new patterns to the appropriate sections in `pattern_registry.py`
5. Re-test with the debugging tools to verify improvements

### Common Pattern Improvement Workflow

1. **Identify problematic PDFs**: Use batch tools to find PDFs with low extraction confidence
2. **Analyze specific issues**: Run debug tools on those PDFs to identify missing patterns
3. **Test new patterns**: Use `debug_extractions_visualizer.py` to test new pattern ideas
4. **Update patterns**: Add successful patterns to the registry
5. **Validate improvements**: Run batch analysis again to confirm increased success rates

## Extraction Statistics and Reporting

The `debug_extraction_report.py` tool generates comprehensive reports showing:

- Field extraction success rates (which fields extract successfully most often)
- Pattern usage statistics (which patterns are most effective)
- Confidence levels across processed PDFs
- Specific pattern suggestions based on content analysis

These reports help prioritize pattern development efforts by identifying:

- Fields with the lowest extraction success rates
- Patterns that rarely or never match
- Content formats that aren't currently handled well

## Troubleshooting Common Issues

### No Pattern Matches

If no patterns match in a document:
1. Check if the text extraction is working properly
2. Look for unusual date/currency/number formats in the PDF
3. Try the `--test-pattern` option with simplified patterns
4. Review the raw text for encoding or formatting issues

### Incorrect Values Extracted

If incorrect values are extracted:
1. Examine the pattern matches in context
2. Check if multiple matches occur and the wrong one is selected
3. Make patterns more specific to target the correct instances
4. Add context requirements to patterns (e.g., "issue date:" before the date)

### Low Confidence Results

If extraction confidence is consistently low:
1. Check which fields are missing most often
2. Look for patterns in the failure cases
3. Run debug tools to identify common formats not being captured
4. Add new patterns targeting those specific formats

## Contributing New Patterns

When adding new patterns to the registry:

1. Test them thoroughly on multiple PDFs
2. Ensure they don't produce false positives
3. Add them to the appropriate category in `pattern_registry.py`
4. Include a comment explaining the format they're designed to match
5. Run the batch debugging tools again to validate improvements

## Best Practices

- **Start specific**: When debugging, start with specific PDFs known to have issues
- **Iterative improvement**: Add patterns incrementally and test after each addition
- **Monitor statistics**: Use batch tools to track improvement over time
- **Document patterns**: Comment new patterns with examples of what they match
- **Validate changes**: Always run thorough testing after pattern modifications 