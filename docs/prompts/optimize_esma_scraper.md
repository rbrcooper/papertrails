# TASK: Optimize ESMA Scraper and Create Efficient Testing Framework

## PROJECT CONTEXT
My ESMA Prospectus Scraper downloads documents from the European Securities and Markets Authority website. Currently, it faces several efficiency issues:
1. Bot detection triggers requiring frequent wait times
2. Entire test runs take too long with the full company list
3. Company name matching is problematic - ESMA database names often differ from my source list
4. Need to redownload documents repeatedly during debugging

## CURRENT CODE STRUCTURE
- `processes/esma_scraper.py` contains the ESMAScraper class that handles website interaction
- `processes/company_list_handler.py` manages company data
- Tests in `processes/utils/` run full processes that are too time-consuming for debugging
- The scraper uses Selenium with undetected_chromedriver to handle bot detection

## SPECIFIC TASKS
1. Create an optimized test framework that:
   - Uses a small, representative set of 3-5 companies known to have good data
   - Implements proper caching to avoid redownloading during debugging
   - Measures performance metrics (time per company, success rate)
   - Can be run quickly for iterative testing

2. Improve company name matching:
   - Create a fuzzy matching system with thresholds and manual verification
   - Build a company name alias database that maps source names to ESMA names
   - Implement a learning mechanism that remembers successful matches

3. Enhance bot detection handling:
   - Implement adaptive waiting based on website response patterns
   - Create reconnection strategies when detected
   - Add logging to track detection patterns

## IMPLEMENTATION DETAILS
1. Create `processes/tests/test_esma_optimized.py`:
   - Define a small set of test companies covering different document types
   - Implement proper test fixtures and teardown
   - Add performance metrics collection
   - Create visualization of scraping performance

2. For company name matching:
   - Create `processes/utils/company_matcher.py` with fuzzy matching
   - Build `data/company_aliases.json` to store known mappings
   - Integrate with CompanyListHandler

3. For bot detection:
   - Enhance ESMAScraper's session management
   - Implement exponential backoff with jitter
   - Add specialized error detection and recovery

## TESTING METHODOLOGY
1. Create a baseline test measuring:
   - Success rate (documents found/downloaded)
   - Time per company
   - Bot detection frequency

2. Test improvements iteratively:
   - Run with and without each optimization
   - Document improvements in each metric
   - Save detailed logs for analysis

3. Create a debugging mode that:
   - Uses cached documents when available
   - Falls back to download only when needed
   - Reports exactly where failures occur

## EXPECTED IMPROVEMENTS
1. 50%+ reduction in test run time
2. 90%+ success rate in company name matching
3. Reduced bot detection frequency 
4. Clear understanding of where failures occur

Please implement these optimizations with thorough documentation and metrics collection. The primary goal is to create a reliable, efficient testing framework that allows for rapid iteration while solving the underlying scraper issues. 