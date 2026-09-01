#!/usr/bin/env python3
"""Windowless downloadFile probe. Cron stays off. Does not start Chrome.

Cookie-reuse live GET only if data/chrome_profile/esma_cookies.json is usable.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from processes.esma_scraper import (
    admitted_esma_download_url,
    cookie_jar_is_usable,
    esma_cookie_jar_path,
    load_cookie_jar,
    probe_downloadfile_pdf,
)

# Known FTWS from website/data/deals.json (host-pinned downloadFile).
PROBE_URL = (
    "https://registers.esma.europa.eu/publication/downloadFile"
    "?fileId=46708211&checksum=0b67c4a8e624b335cc54daf9002fec26"
)
PROBE_ISIN = "XS3305214903"


def _url_from_deals() -> str:
    deals_path = Path("website/data/deals.json")
    if not deals_path.is_file():
        return PROBE_URL
    try:
        payload = json.loads(deals_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return PROBE_URL
    for d in payload.get("deals") or []:
        url = admitted_esma_download_url(d.get("source_url") or "")
        if url:
            return url
    return PROBE_URL


def main() -> int:
    url = admitted_esma_download_url(_url_from_deals()) or PROBE_URL
    jar = esma_cookie_jar_path()
    print(f"url={url}")
    print(f"isin_hint={PROBE_ISIN}")
    print(f"jar={jar}")
    if not cookie_jar_is_usable(jar):
        print("cookie_reuse=SKIPPED no usable cookie jar")
        return 0
    cookies = load_cookie_jar(jar)
    ok, head = probe_downloadfile_pdf(url, cookies=cookies)
    print(f"cookie_reuse={'YES' if ok else 'NO'} head={head!r}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
