"""Flask preview bind/debug lock and public payload strip."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from website.app import (  # noqa: E402
    _load_payload,
    _public_deals,
    app,
    preview_run_kwargs,
)


def test_debug_off_by_default():
    kwargs = preview_run_kwargs(env={})
    assert kwargs["debug"] is False


def test_debug_on_when_flask_debug_1():
    kwargs = preview_run_kwargs(env={"FLASK_DEBUG": "1"})
    assert kwargs["debug"] is True


def test_default_host_loopback():
    kwargs = preview_run_kwargs(env={})
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["host"] != "0.0.0.0"


def test_refuse_all_interfaces():
    with pytest.raises(ValueError, match="0.0.0.0"):
        preview_run_kwargs(host="0.0.0.0", env={})


def test_refuse_flask_host_all_interfaces():
    with pytest.raises(ValueError, match="0.0.0.0"):
        preview_run_kwargs(env={"FLASK_HOST": "0.0.0.0"})


def test_public_deals_omits_pdf_path():
    rows = _public_deals(
        [{"isin": "XS1", "issuer": "Acme", "pdf_path": "/tmp/secret.pdf"}]
    )
    assert rows == [{"isin": "XS1", "issuer": "Acme"}]
    assert "pdf_path" not in rows[0]


def test_load_payload_omits_pdf_path(tmp_path, monkeypatch):
    leftover = tmp_path / "deals.json"
    leftover.write_text(
        json.dumps(
            {
                "updated_at": "2026-01-01T00:00:00Z",
                "deals": [
                    {
                        "isin": "XS1",
                        "issuer": "Acme",
                        "pdf_path": "/tmp/secret.pdf",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    import website.app as website_app

    monkeypatch.setattr(website_app, "DEALS_PATH", leftover)
    payload = _load_payload()
    assert payload["deals"][0]["isin"] == "XS1"
    assert "pdf_path" not in payload["deals"][0]
    on_disk = json.loads(leftover.read_text(encoding="utf-8"))
    assert on_disk["deals"][0]["pdf_path"] == "/tmp/secret.pdf"


def test_api_deals_omits_pdf_path_leftover(tmp_path, monkeypatch):
    leftover = tmp_path / "deals.json"
    leftover.write_text(
        json.dumps(
            {
                "updated_at": "2026-01-01T00:00:00Z",
                "deals": [
                    {
                        "isin": "XS1",
                        "issuer": "Acme",
                        "pdf_path": "/tmp/secret.pdf",
                        "underwriters": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    import website.app as website_app

    monkeypatch.setattr(website_app, "DEALS_PATH", leftover)
    client = app.test_client()
    res = client.get("/api/deals")
    assert res.status_code == 200
    body = res.get_json()
    assert "pdf_path" not in body["deals"][0]
    on_disk = json.loads(leftover.read_text(encoding="utf-8"))
    assert on_disk["deals"][0]["pdf_path"] == "/tmp/secret.pdf"
