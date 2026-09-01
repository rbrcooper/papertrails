"""Chrome profile path + cookie-jar reuse hooks (no live ESMA)."""

import json
import logging
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from processes.esma_scraper import (
    ESMAScraper,
    apply_cookie_jar_to_driver,
    chrome_user_data_dir_path,
    cookie_jar_is_usable,
    dump_cookie_jar,
    esma_cookie_jar_path,
    load_cookie_jar,
    probe_downloadfile_pdf,
    selenium_cookies_to_requests,
)

REAL_FILLED = (
    "https://registers.esma.europa.eu/publication/downloadFile"
    "?fileId=46708211&checksum=0b67c4a8e624b335cc54daf9002fec26"
)
EVIL = "https://evil.example/downloadFile"
DETAILS = (
    "https://registers.esma.europa.eu/publication/details"
    "?core=esma_registers_priii_securities&docId=20387494"
)


def _bare_scraper(tmp_path, cookie_jar_path=None, driver=None):
    scraper = ESMAScraper.__new__(ESMAScraper)
    scraper.logger = logging.getLogger("test_esma_session_persist")
    scraper.requests_count = 0
    scraper.driver = driver
    scraper.user_agent = "test"
    scraper.http_proxy = None
    scraper.https_proxy = None
    scraper.headless = True
    scraper.download_dir = Path(tmp_path) / "dl"
    scraper.download_dir.mkdir(parents=True, exist_ok=True)
    scraper.chrome_user_data_dir = Path(tmp_path) / "profile"
    scraper.chrome_user_data_dir.mkdir(parents=True, exist_ok=True)
    scraper.cookie_jar_path = (
        Path(cookie_jar_path)
        if cookie_jar_path
        else scraper.chrome_user_data_dir / "esma_cookies.json"
    )
    scraper.document_hashes = {}
    scraper.document_hashes_file = Path(tmp_path) / "hashes.json"
    scraper.current_company = None
    return scraper


class TestProfileAndJarPaths:
    def test_defaults_under_gitignored_data(self, monkeypatch):
        monkeypatch.delenv("ESMA_CHROME_USER_DATA_DIR", raising=False)
        monkeypatch.delenv("ESMA_COOKIE_JAR", raising=False)
        profile = chrome_user_data_dir_path()
        jar = esma_cookie_jar_path()
        assert profile == Path("data/chrome_profile")
        assert jar == Path("data/chrome_profile") / "esma_cookies.json"
        assert profile.parts[0] == "data"

    def test_env_and_override(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ESMA_CHROME_USER_DATA_DIR", str(tmp_path / "env_profile"))
        monkeypatch.setenv("ESMA_COOKIE_JAR", str(tmp_path / "env_jar.json"))
        assert chrome_user_data_dir_path() == tmp_path / "env_profile"
        assert esma_cookie_jar_path() == tmp_path / "env_jar.json"
        assert chrome_user_data_dir_path(tmp_path / "arg_profile") == tmp_path / "arg_profile"
        assert esma_cookie_jar_path(tmp_path / "arg_jar.json") == tmp_path / "arg_jar.json"

    def test_jar_nests_under_profile_when_no_jar_override(self, monkeypatch, tmp_path):
        monkeypatch.delenv("ESMA_COOKIE_JAR", raising=False)
        jar = esma_cookie_jar_path(user_data_dir=tmp_path / "p")
        assert jar == tmp_path / "p" / "esma_cookies.json"


class TestCookieJarRoundtrip:
    def test_dump_load_name_value_and_selenium_list(self, tmp_path):
        jar = tmp_path / "esma_cookies.json"
        dump_cookie_jar(jar, {"JSESSIONID": "abc"})
        assert load_cookie_jar(jar) == {"JSESSIONID": "abc"}
        assert cookie_jar_is_usable(jar)
        dump_cookie_jar(
            jar,
            [
                {
                    "name": "SESSION",
                    "value": "xyz",
                    "domain": "registers.esma.europa.eu",
                    "path": "/",
                }
            ],
        )
        assert load_cookie_jar(jar)["SESSION"] == "xyz"

    def test_missing_or_corrupt_jar_is_empty(self, tmp_path):
        missing = tmp_path / "nope.json"
        assert load_cookie_jar(missing) == {}
        assert not cookie_jar_is_usable(missing)
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        assert load_cookie_jar(bad) == {}

    def test_filters_foreign_domain_and_expired(self):
        now = time.time()
        cookies = [
            {"name": "keep", "value": "1", "domain": "registers.esma.europa.eu"},
            {"name": "google", "value": "2", "domain": "google.com"},
            {
                "name": "stale",
                "value": "3",
                "domain": "registers.esma.europa.eu",
                "expiry": now - 60,
            },
        ]
        assert selenium_cookies_to_requests(cookies) == {"keep": "1"}

    def test_apply_cookie_jar_skips_foreign_domain(self):
        driver = MagicMock()
        n = apply_cookie_jar_to_driver(
            driver,
            [
                {"name": "keep", "value": "1", "domain": "registers.esma.europa.eu"},
                {"name": "google", "value": "2", "domain": "google.com"},
            ],
        )
        assert n == 1
        driver.add_cookie.assert_called_once()
        assert driver.add_cookie.call_args.args[0]["name"] == "keep"


class TestChromeOptionsUserDataDir:
    def test_setup_chrome_options_pins_profile(self, tmp_path):
        scraper = _bare_scraper(tmp_path)
        options = scraper.setup_chrome_options()
        args = list(options.arguments)
        udd = [a for a in args if "user-data-dir" in a]
        assert len(udd) == 1
        assert str(scraper.chrome_user_data_dir.resolve()) in udd[0]
        assert any("headless" in a for a in args)


class TestCookieReuseHooks:
    def test_disk_jar_used_when_driver_has_no_cookies(self, tmp_path):
        jar = tmp_path / "esma_cookies.json"
        dump_cookie_jar(jar, {"JSESSIONID": "from-disk"})
        scraper = _bare_scraper(tmp_path, cookie_jar_path=jar, driver=None)
        assert scraper._request_cookie_dict()["JSESSIONID"] == "from-disk"

    def test_live_cookies_preferred_and_dumped(self, tmp_path):
        jar = tmp_path / "esma_cookies.json"
        dump_cookie_jar(jar, {"JSESSIONID": "old"})
        driver = MagicMock()
        driver.get_cookies.return_value = [
            {
                "name": "JSESSIONID",
                "value": "live",
                "domain": "registers.esma.europa.eu",
            }
        ]
        scraper = _bare_scraper(tmp_path, cookie_jar_path=jar, driver=driver)
        assert scraper._request_cookie_dict()["JSESSIONID"] == "live"
        assert load_cookie_jar(jar)["JSESSIONID"] == "live"

    def test_persist_session_cookies_writes_jar(self, tmp_path):
        jar = tmp_path / "esma_cookies.json"
        driver = MagicMock()
        driver.get_cookies.return_value = [
            {"name": "A", "value": "1", "domain": "registers.esma.europa.eu"}
        ]
        scraper = _bare_scraper(tmp_path, cookie_jar_path=jar, driver=driver)
        assert scraper.persist_session_cookies() == jar
        assert load_cookie_jar(jar) == {"A": "1"}

    def test_download_document_passes_disk_cookies(self, tmp_path):
        jar = tmp_path / "esma_cookies.json"
        dump_cookie_jar(jar, {"JSESSIONID": "abc123"})
        scraper = _bare_scraper(tmp_path, cookie_jar_path=jar, driver=None)
        pdf = b"%PDF-1.4 mock"
        resp = MagicMock()
        resp.headers = {"content-disposition": 'filename="x.pdf"'}
        resp.iter_content = lambda chunk_size=8192: [pdf]
        resp.raise_for_status = MagicMock()
        resp.close = MagicMock()
        with patch("processes.esma_scraper.requests.get", return_value=resp) as get:
            path = scraper.download_document(REAL_FILLED, doc_id="1")
        get.assert_called_once()
        assert get.call_args.kwargs["cookies"]["JSESSIONID"] == "abc123"
        assert path is not None
        assert Path(path).read_bytes().startswith(b"%PDF")

    def test_download_document_no_get_on_reject(self, tmp_path):
        scraper = _bare_scraper(tmp_path, driver=None)
        with patch("processes.esma_scraper.requests.get") as get:
            assert scraper.download_document(EVIL, doc_id="1") is None
            assert scraper.download_document(DETAILS, doc_id="1") is None
            get.assert_not_called()

    def test_session_download_no_get_on_reject(self, tmp_path):
        scraper = _bare_scraper(tmp_path, driver=MagicMock())
        with patch("processes.esma_scraper.requests.get") as get:
            assert scraper._download_binary_with_session(EVIL) is None
            get.assert_not_called()


class TestProbeDownloadfilePdf:
    def test_refuses_non_admitted_without_get(self):
        with patch("processes.esma_scraper.requests.get") as get:
            ok, head = probe_downloadfile_pdf(EVIL)
            assert ok is False
            assert head == b""
            get.assert_not_called()

    def test_cookie_reuse_on_admitted_url(self):
        resp = MagicMock()
        resp.content = b"%PDF-1.4xxxx"
        with patch("processes.esma_scraper.requests.get", return_value=resp) as get:
            ok, head = probe_downloadfile_pdf(REAL_FILLED, cookies={"JSESSIONID": "x"})
        assert ok is True
        assert head.startswith(b"%PDF")
        get.assert_called_once()
        assert get.call_args.args[0] == REAL_FILLED
        assert get.call_args.kwargs["cookies"] == {"JSESSIONID": "x"}
