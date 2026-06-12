#!/usr/bin/env python3
"""Probe ESMA UI for real download links (headed)."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from processes.esma_scraper import ESMAScraper

ISIN = "XS2886118079"


def main():
    scraper = ESMAScraper(debug_mode=True, headless=False, download_dir=Path("data/downloads/_probe"))
    try:
        scraper.navigate_to_search()
        scraper.search_by_isin(ISIN)
        for wait in (5, 15, 30):
            time.sleep(wait)
            rows = scraper.driver.find_elements("css selector", "#resultsTable tbody tr")
            print(f"after {wait}s: tbody rows={len(rows)}")
            if rows:
                break
        links = scraper.driver.find_elements("css selector", "a[href]")
        dl = [a.get_attribute("href") for a in links if a.get_attribute("href") and "download" in a.get_attribute("href").lower()]
        print("download links", dl[:5])
        if rows:
            d = scraper.get_document_details(rows[0])
            print("row0", d)
            path = scraper.download_from_results_table(isin=ISIN)
            print("download path", path)
            if path:
                print("head", Path(path).read_bytes()[:8])
    finally:
        scraper.close()


if __name__ == "__main__":
    main()
