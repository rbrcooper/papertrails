"""
PaperTrails public surface: reverse-chronological deals from website/data/deals.json.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template_string

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEALS_PATH = Path(__file__).resolve().parent / "data" / "deals.json"

app = Flask(__name__)

PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>PaperTrails — fossil bond underwriting alerts</title>
  <style>
    :root { --ink:#1a1a1a; --muted:#555; --line:#ddd; --bg:#fafafa; }
    body { font-family: Georgia, "Times New Roman", serif; margin:0; background:var(--bg); color:var(--ink); }
    main { max-width: 52rem; margin: 0 auto; padding: 2rem 1.25rem 4rem; }
    h1 { font-size: 1.75rem; margin: 0 0 0.25rem; letter-spacing: -0.02em; }
    .tag { color: var(--muted); font-size: 0.95rem; margin-bottom: 1.5rem; }
    .meta { font-size: 0.85rem; color: var(--muted); margin-bottom: 2rem; }
    article { border-top: 1px solid var(--line); padding: 1.25rem 0; }
    article h2 { font-size: 1.15rem; margin: 0 0 0.35rem; }
    .banks { margin: 0.5rem 0 0; padding-left: 1.1rem; }
    .banks li { margin: 0.15rem 0; }
    a { color: #0b3d91; }
    .empty { color: var(--muted); font-style: italic; }
  </style>
</head>
<body>
<main>
  <h1>PaperTrails</h1>
  <p class="tag">EU fossil-fuel bond underwriters from public prospectuses (GOGEL STE-ranked watchlist).</p>
  <p class="meta">Updated: {{ updated_at or "—" }} · {{ deals|length }} deal(s)</p>
  {% if not deals %}
    <p class="empty">No published deals yet. Run <code>py -3 -m papertrails.run_alerts</code>.</p>
  {% endif %}
  {% for d in deals %}
  <article>
    <h2>{{ d.issuer }} · {{ d.isin }}</h2>
    <div class="meta">
      {% if d.issue_date %}Issue {{ d.issue_date }} · {% endif %}
      {% if d.currency %}{{ d.currency }}{% endif %}
      {% if d.amount %} · tranche {{ d.amount }}{% endif %}
      {% if d.programme_size %} · programme {{ d.programme_size }}{% endif %}
      {% if d.n_underwriters %} · {{ d.n_underwriters }} underwriter(s){% endif %}
      {% if d.allocated_amount is not none %} · 1/n {{ d.allocated_amount }}{% endif %}
      {% if d.watchlist_rank %} · STE rank {{ d.watchlist_rank }}{% endif %}
      {% if d.doc_type_code %} · {{ d.doc_type_code }}{% endif %}
      {% if d.extraction_method %} · {{ d.extraction_method }}{% endif %}
    </div>
    <ul class="banks">
      {% for b in d.underwriters %}
        <li>{{ b.raw_name }}{% if b.role and b.role != "Unknown" %} <span class="meta">({{ b.role }})</span>{% endif %}</li>
      {% endfor %}
    </ul>
    {% if d.source_url %}
      <p><a href="{{ d.source_url }}" rel="noopener">Prospectus / source</a></p>
    {% endif %}
  </article>
  {% endfor %}
</main>
</body>
</html>
"""


def _sort_deals(deals):
    return sorted(
        deals,
        key=lambda d: (bool(d.get("issue_date")), d.get("issue_date") or ""),
        reverse=True,
    )


def _public_deals(deals):
    out = []
    for d in deals:
        row = dict(d)
        row.pop("pdf_path", None)
        out.append(row)
    return out


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def preview_run_kwargs(host=None, env=None):
    """Bind/debug kwargs for local preview. Never binds non-loopback."""
    env = os.environ if env is None else env
    bind = host if host is not None else (env.get("FLASK_HOST") or "127.0.0.1")
    bind = str(bind).strip()
    if bind.lower() not in _LOOPBACK_HOSTS:
        raise ValueError(
            f"Refusing non-loopback bind host {bind!r}; "
            "Flask preview must stay on loopback"
        )
    debug = str(env.get("FLASK_DEBUG", "")).strip().lower() in {"1", "true", "yes"}
    port = int(env.get("PORT", "5000"))
    return {"host": bind, "port": port, "debug": debug}


def _load_payload():
    if not DEALS_PATH.exists():
        return {"updated_at": None, "deals": []}
    with DEALS_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return {"updated_at": None, "deals": _sort_deals(_public_deals(data))}
    return {
        "updated_at": data.get("updated_at"),
        "deals": _sort_deals(_public_deals(data.get("deals") or [])),
    }


@app.route("/")
def index():
    payload = _load_payload()
    return render_template_string(
        PAGE, deals=payload["deals"], updated_at=payload.get("updated_at")
    )


@app.route("/api/deals")
def api_deals():
    return jsonify(_load_payload())


if __name__ == "__main__":
    app.run(**preview_run_kwargs())
