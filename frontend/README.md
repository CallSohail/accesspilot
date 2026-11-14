# AccessPilot — frontend

React 18 + Vite + TypeScript single-page app for the AccessPilot backend.

## Requirements

- Node.js (18+; developed on Node 24)
- The AccessPilot backend running on **http://localhost:8000**

  In dev the Vite dev server also proxies `/api` → `http://localhost:8000`,
  so either path works. The API base URL defaults to `http://localhost:8000`
  and can be overridden with the `VITE_API_BASE_URL` env var at build time.

## Run

```bash
npm install
npm run dev        # dev server at http://localhost:5173
npm run build      # type-check (tsc) + production bundle in dist/
npm run preview    # serve the production build locally
```

## What it does

- Uploads a `.pdf`, `.docx` or `.pptx` (drag & drop or file picker) to
  `POST /api/analyze`.
- Shows a health/status chip from `GET /api/health` (backend online, version,
  AI on/off) and a banner when the backend is unreachable.
- Renders the report: summary cards (errors/warnings/info/blocks), findings
  with severity and source badges, before/after suggestions, scope & caveats
  notes, and download buttons for the JSON and HTML report artifacts.
- Assistant panel posts to `POST /api/assistant` with a compact context
  derived from the current report (or an empty context for general questions).
