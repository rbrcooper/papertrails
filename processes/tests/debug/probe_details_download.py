#!/usr/bin/env python3
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from processes.esma_scraper import ESMAScraper
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

DOC_ID = "45331952"
ISIN = "XS2886118079"


def main():
    s = ESMAScraper(headless=False, download_dir=Path("data/downloads/_probe"))
    try:
        s.navigate_to_search()
        time.sleep(2)
        s.search_by_isin(ISIN)
        WebDriverWait(s.driver, 40).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "#resultsTable table tbody tr")) > 0
        )
        s.driver.execute_script("if (typeof setNavCookie === 'function') setNavCookie();")
        url = (
            "https://registers.esma.europa.eu/publication/details"
            f"?core=esma_registers_priii_securities&docId={DOC_ID}"
        )
        s.driver.get(url)
        time.sleep(8)
        links = [
            a.get_attribute("href")
            for a in s.driver.find_elements(By.CSS_SELECTOR, "a[href]")
            if a.get_attribute("href")
        ]
        print("current", s.driver.current_url)
        print("download links", [u for u in links if "download" in u.lower() or "fileId" in u][:10])
        for u in links:
            if "downloadFile" in u:
                p = s.download_document(u, doc_id="omv")
                if p:
                    print("PDF?", Path(p).read_bytes()[:8])
                    return
        Path("logs/page_sources").mkdir(parents=True, exist_ok=True)
        Path("logs/page_sources/probe_details.html").write_text(
            s.driver.page_source, encoding="utf-8"
        )
        print("saved probe_details.html")
    finally:
        s.close()


if __name__ == "__main__":
    main()
