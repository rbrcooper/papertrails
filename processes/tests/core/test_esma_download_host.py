"""Host-pin for ESMA downloadFile GET (not substring 'downloadFile' in url)."""

import logging
from unittest.mock import MagicMock, patch

from processes.esma_scraper import (
    ESMAScraper,
    admitted_esma_download_url,
    resolve_download_url,
)

REAL = (
    "https://registers.esma.europa.eu/publication/downloadFile"
    "?fileId=&checksum="
)
REAL_FILLED = (
    "https://registers.esma.europa.eu/publication/downloadFile"
    "?fileId=14857148&checksum=dfc16224b5c7ada6f83c5d0566174e81"
)
RELATIVE = "/publication/downloadFile?fileId=&checksum="
DETAILS = (
    "https://registers.esma.europa.eu/publication/details"
    "?core=esma_registers_priii_securities&docId=20387494"
)


def _bare_scraper():
    scraper = ESMAScraper.__new__(ESMAScraper)
    scraper.logger = logging.getLogger("test_esma_download_host")
    scraper.requests_count = 0
    scraper.driver = MagicMock()
    scraper.user_agent = "test"
    scraper.http_proxy = None
    scraper.https_proxy = None
    return scraper


class TestAdmittedEsmaDownloadUrl:
    def test_accepts_real_downloadfile(self):
        assert admitted_esma_download_url(REAL) == REAL
        assert admitted_esma_download_url(REAL_FILLED) == REAL_FILLED

    def test_accepts_root_relative_after_normalize(self):
        assert admitted_esma_download_url(RELATIVE) == REAL

    def test_rejects_http(self):
        assert admitted_esma_download_url(
            "http://registers.esma.europa.eu/publication/downloadFile?fileId=1&checksum=abc"
        ) == ""

    def test_rejects_wrong_host(self):
        assert admitted_esma_download_url(
            "https://evil.example/publication/downloadFile?fileId=1&checksum=abc"
        ) == ""

    def test_rejects_suffix_host(self):
        assert admitted_esma_download_url(
            "https://registers.esma.europa.eu.attacker/publication/downloadFile?fileId=1&checksum=abc"
        ) == ""

    def test_rejects_downloadfile_on_other_host_path(self):
        assert admitted_esma_download_url("https://evil.example/downloadFile") == ""

    def test_rejects_downloadfile_in_query_on_other_host(self):
        assert admitted_esma_download_url(
            "https://evil.example/foo?x=downloadFile"
        ) == ""

    def test_rejects_details_url(self):
        assert admitted_esma_download_url(DETAILS) == ""


class TestResolveDownloadUrl:
    def test_admits_download_url_field(self):
        assert resolve_download_url({"download_url": REAL_FILLED, "url": DETAILS}) == REAL_FILLED

    def test_admits_url_field_when_download_url_missing(self):
        assert resolve_download_url({"url": RELATIVE}) == REAL

    def test_rejects_details_and_evil(self):
        assert resolve_download_url({"url": DETAILS}) == ""
        assert resolve_download_url({
            "download_url": "https://evil.example/downloadFile",
            "url": DETAILS,
        }) == ""


class TestDownloadDocumentNoGetOnReject:
    def test_returns_none_without_get(self):
        scraper = _bare_scraper()
        rejects = [
            "https://evil.example/downloadFile",
            "https://registers.esma.europa.eu.attacker/publication/downloadFile?fileId=1&checksum=abc",
            "http://registers.esma.europa.eu/publication/downloadFile?fileId=1&checksum=abc",
            DETAILS,
            "https://evil.example/foo?x=downloadFile",
        ]
        with patch("processes.esma_scraper.requests.get") as get:
            for url in rejects:
                assert scraper.download_document(url, doc_id="1") is None
            get.assert_not_called()
        assert scraper.driver.mock_calls == []
