# PaperTrails frontend

Vite/React local UI at repo-root `frontend/`. It shows **this alert feed** (23 FTWS-live parents), not all of GOGEL. Flask (`website/app.py`) stays local preview.

**Canonical data:** `website/data/deals.json`. Embedded `src/data/deals.json` is a fallback snapshot only — not a second source of truth. With Flask up, the app fetches `/api/deals`; otherwise it uses the snapshot.

## Run locally

Prerequisites: Node.js

1. `npm install`
2. Optional: `py -3 -m website.app` (loopback) so the UI can fetch `/api/deals`
3. `npm run dev` — binds **127.0.0.1** only (not `0.0.0.0`)

No Gemini key. The story-lead modal is a template from filing fields.

## AI Studio drop

Download Studio output into `frontend/_aistudio_drop/` (gitignored so ZIPs and nested `node_modules` are not committed). Grok/Cursor merges updated UI chrome and **maintains** contract fixes.

**Merge:** copy layout, CSS, and components for chrome (header hide, fewer buttons). **Never overwrite without a diff:**

- `src/utils/formatters.ts`
- `src/utils/formatters.test.ts`
- `vite.config.ts` (loopback host + `/api` proxy)
- data-load + sanitize in `App.tsx` (fetch `/api/deals`, strip `pdf_path`, no “Live Data Feed”)

After merge: `npm test`.

## Update log

**2026-09-01** (`7eba500`) — contract fixes:

- Native-currency totals, not RON-as-EUR
- No programme-shelf sum
- Vite binds 127.0.0.1
- `/api/deals` from Flask
- `pdf_path` stripped
- https-only href
- Parent overlay hidden
- STE 1/n on compare
- Formatters tests

**Still in Studio:** sticky header; too many button-like controls.
