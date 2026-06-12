import logging
from pprint import pprint
from pathlib import Path
import sys

# Ensure project root is on sys.path
sys.path.append(str(Path(__file__).resolve().parents[3]))

from processes.esma_scraper import ESMAScraper


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    scraper = None
    try:
        scraper = ESMAScraper(debug_mode=True, headless=True)
        downloads = scraper.search_and_process('OMV')
        print('Downloaded files:')
        pprint(downloads)
    finally:
        if scraper:
            scraper.close()


if __name__ == '__main__':
    main()


