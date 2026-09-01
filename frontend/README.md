# PaperTrails frontend

Vite/React local UI at repo-root `frontend/`. Flask (`website/app.py`) stays local preview.

**Data:** `website/data/deals.json` is the canonical publish file. `frontend/src/data/deals.json` is a fallback snapshot only — do not treat it as a second source of truth. With Flask up, the app fetches `/api/deals`; otherwise it uses the embedded snapshot.

## Run locally

Prerequisites: Node.js

1. `npm install`
2. Optional: `py -3 -m website.app` (loopback) so the UI can fetch `/api/deals`
3. `npm run dev` — binds **127.0.0.1** only (not `0.0.0.0`)

No Gemini key. The story-lead modal is a template from filing fields.
