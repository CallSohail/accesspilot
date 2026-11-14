# AccessPilot

**Autonomous accessibility engineer for university course materials (PDF, DOCX, PPTX).**

Upload a course file, get a structured report of accessibility findings — each with severity, source, WCAG reference, location and remediation — plus optional AI-assisted suggestions and JSON/HTML downloads.

---

## Features

- **Deterministic, rule-based accessibility checks** — runs with no external service and no API key:
  - Heading structure (presence, hierarchy, first heading)
  - Untagged / unstructured PDF detection
  - Link labels (missing, generic such as "click here", URL-as-text, duplicates)
  - Image alt-text
  - Overly long paragraphs
  - Empty documents
  - PDF reading-order items flagged for human review
- **Structured findings.** Every finding carries a severity (`error` / `warning` / `info`), a source (`deterministic` / `ai` / `human`), a WCAG reference where applicable, a location within the document, and a remediation note.
- **Optional AI assistant.** OpenAI-compatible endpoint (default: Nebius-hosted Nemotron). Fully opt-in; off by default. See [AI assistant / privacy](#ai-assistant--privacy).
- **Report downloads.** Every analysis produces a report available as both JSON and standalone HTML.
- **In-memory job store.** Reports are keyed by ID and held in memory. Old entries are evicted at roughly 200, and the store is cleared on restart.
- **Defensive extraction.** PDF (PyMuPDF), DOCX (python-docx) and PPTX (python-pptx) extractors handle common edge cases and fall back to readable output rather than crashing on malformed files.

## How it works

1. **Upload** — `POST /api/analyze` accepts a multipart `file` (PDF, DOCX or PPTX) and returns the finished report directly.
2. **Extract** — the matching extractor parses the document into a normalized intermediate structure. Uploads are written to a per-job temporary location under `.scratch/uploads` and removed after analysis.
3. **Deterministic checks** — the rule-based checks run over the extracted structure and produce findings.
4. **Optional AI pass** — if the AI is enabled (see flags below), a caller-chosen subset of context is sent to the configured OpenAI-compatible endpoint to obtain supplemental suggestions. Without opt-in, this step is skipped entirely.
5. **Report** — the findings are merged, stored in the in-memory job store, and served via JSON or HTML.

### Scope & limitations

- AccessPilot runs a **limited set of rule-based checks**. It is **not** a full WCAG 2.x / PDF-UA compliance engine.
- It **never claims or certifies WCAG / PDF-UA conformance** — the report says so explicitly.
- Untagged-PDF structural findings are **inferred** from layout heuristics, not from tag-tree inspection.
- Findings marked with `source: human` (e.g. PDF reading-order review) require a person to confirm.
- Uploads are stored in memory only; the server must be treated as stateless across restarts.

## Repository layout

```
.
├── backend/
│   ├── app/
│   │   ├── app.py            # FastAPI entrypoint (uvicorn target)
│   │   ├── routers.py        # API routes
│   │   ├── models.py         # Pydantic models
│   │   ├── config.py         # Env-driven settings
│   │   ├── analysis.py       # Analysis orchestration
│   │   ├── checks.py         # Deterministic checks
│   │   ├── report.py         # Report rendering (JSON/HTML)
│   │   ├── jobstore.py       # In-memory job store
│   │   ├── storage.py        # Upload handling
│   │   ├── assistant.py      # Optional AI assistant
│   │   └── extractors/
│   │       ├── pdf.py
│   │       ├── docx.py
│   │       └── pptx.py
│   ├── tests/                # conftest.py, test_api.py, test_extract.py
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/                 # React + Vite + TypeScript single-page app
│   └── ...                   # (dev server on :5173, proxies /api → :8000)
├── .env.example              # Environment variable template
├── .gitignore
└── LICENSE                   # Apache 2.0
```

The frontend is a single-page app that lets you upload a file, view the report with severity/source badges and before/after suggestions, download the report as JSON or HTML, and (when AI is enabled) use an AI assistant panel.

## Quickstart

**Prerequisites:** Python 3.11+, Node 18+.

### Backend

```bash
# from the repo root
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r backend/requirements.txt
# or, for an editable install:
# pip install -e backend/

copy .env.example .env      # Windows
# cp .env.example .env      # macOS / Linux
# then fill in the values in .env (see Configuration below)

cd backend
uvicorn app.app:app --reload --port 8000
```

The backend serves the API on <http://localhost:8000>.

> Without AI env vars set (or with the opt-in flags left at their defaults), the app runs in **deterministic-only mode** and needs no external service or API key.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Serves the app on <http://localhost:5173> and proxies `/api/*` to <http://localhost:8000>.

## Configuration

All settings are driven by `ACCESSPILOT_*` environment variables. Copy `.env.example` to `.env` and edit. No secrets are required to run the backend in deterministic-only mode.

| Variable | Default | Description |
| --- | --- | --- |
| `ACCESSPILOT_MAX_UPLOAD_MB` | `25` | Maximum upload size in megabytes. |
| `ACCESSPILOT_UPLOAD_DIR` | `.scratch/uploads` | Directory where temporary uploads are written during analysis (created automatically). |
| `ACCESSPILOT_AI_ENABLED` | `false` | Master switch for the AI assistant. AI runs only when this is `true` **and** `ACCESSPILOT_AI_API_KEY` is set **and** `ACCESSPILOT_AI_USER_CONFIRMED` is `true`. |
| `ACCESSPILOT_AI_BASE_URL` | `https://api.nebius.ai/llm/v1` | Base URL of the OpenAI-compatible API (no trailing slash). |
| `ACCESSPILOT_AI_MODEL` | `nemotron` | Model identifier. Must be a model your provider actually serves. |
| `ACCESSPILOT_AI_API_KEY` | *(empty)* | API key. Keep out of source control and chat; use a credential manager. |
| `ACCESSPILOT_AI_TIMEOUT_SECONDS` | `60` | Request timeout in seconds. |
| `ACCESSPILOT_AI_USER_CONFIRMED` | `false` | Explicit privacy opt-in flag. Must be `true` (along with the other two) for the AI path to run. |
| `ACCESSPILOT_APP_NAME` | `AccessPilot` | App name (informational). |
| `ACCESSPILOT_VERSION` | `0.1.0` | App version (informational). |
| `ACCESSPILOT_CORS_ORIGINS` | `http://localhost:5173` | Comma-separated list of allowed CORS origins. |

### AI opt-in flags

All three must be true for the AI path to run:

1. `ACCESSPILOT_AI_ENABLED=true`
2. `ACCESSPILOT_AI_API_KEY` set to a non-empty value
3. `ACCESSPILOT_AI_USER_CONFIRMED=true`

`ACCESSPILOT_AI_USER_CONFIRMED` exists as an explicit, human-confirmed privacy opt-in — see below.

## Testing

```bash
# from backend/
python -m pytest
```

39 tests are bundled in `backend/tests/` (API and extractor coverage) and pass under the project's venv.

> **Windows note:** if your default pytest temp dir is locked (e.g. by antivirus or OneDrive), pass an explicit `--basetemp`, e.g.
> `python -m pytest --basetemp=.scratch/ptmp`.

## API reference

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness / version probe. |
| `POST` | `/api/analyze` | Multipart upload (`file`) of a PDF, DOCX or PPTX. Returns the full report (JSON) including the new report ID. |
| `GET` | `/api/reports/{id}` | Full report (JSON) for the given analysis job. |
| `GET` | `/api/reports/{id}/download.json` | Download the report as JSON. |
| `GET` | `/api/reports/{id}/download.html` | Download the report as standalone HTML. |
| `POST` | `/api/assistant` | Send an assistant request (only works when the AI is enabled; otherwise returns an error). |

Reports are held in an **in-memory job store**. Old entries are evicted at roughly 200 jobs and the store is cleared on server restart, so reports are not persisted.

## AI assistant / privacy

- The AI path is **off by default**. It activates only when `ACCESSPILOT_AI_ENABLED`, a non-empty `ACCESSPILOT_AI_API_KEY`, and `ACCESSPILOT_AI_USER_CONFIRMED` are **all** true.
- No file contents are ever sent automatically. The caller explicitly chooses which context to include in each assistant request.
- `ACCESSPILOT_AI_USER_CONFIRMED` is a deliberate second gate so that enabling the feature requires a conscious decision about transmitting content to an external inference provider, rather than only setting an API key.
- If you don't set the API key (or leave either flag at `false`), the app runs entirely offline in deterministic-only mode.

## License

Apache License 2.0 — see [LICENSE](./LICENSE).
