#!/usr/bin/env python3
import re
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from processes.esma_scraper import ESMAScraper
from selenium.webdriver.common.by import By

DOC_ID = "45331952"
ISIN = "XS2886118079"


def main():
    s = ESMAScraper(headless=False, download_dir=Path("data/downloads/_probe"))
    try:
        s.navigate_to_search()
        time.sleep(2)
        s.search_by_isin(ISIN)
        time.sleep(15)
        s.driver.execute_script("if (typeof setNavCookie === 'function') setNavCookie();")
        url = (
            "https://registers.esma.europa.eu/publication/details"
            f"?core=esma_registers_priii_securities&docId={DOC_ID}"
        )
        s.driver.get(url)
        time.sleep(8)
        html = s.driver.page_source
        out = Path("logs/page_sources/probe_details_full.html")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print("saved", out, "len", len(html))
        for pat in [r"downloadFile[^\"']+", r"\.pdf", r"Download", r"fileId"]:
            hits = re.findall(pat, html, re.I)
            print(pat, len(hits), hits[:3])
        print("buttons", len(s.driver.find_elements(By.TAG_NAME, "button")))
        print("inputs", [(i.get_attribute("type"), i.get_attribute("value")) for i in s.driver.find_elements(By.TAG_NAME, "input")[:10]])
    finally:
        s.close()


if __name__ == "__main__":
    main()
