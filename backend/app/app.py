"""FastAPI application entrypoint.

Run with:
    uvicorn app.app:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .assistant import Assistant
from .config import load_settings
from .jobstore import JobStore
from .routers import router
from . import __version__


class _State:
    """Holds process-lifetime singletons (settings, store, assistant)."""

    def __init__(self) -> None:
        self.settings = load_settings()
        self.store = JobStore()
        self.assistant = Assistant(self.settings)


app = FastAPI(
    title="AccessPilot API",
    description=(
        "Upload PDF, DOCX or PPTX course materials and get a deterministic "
        "accessibility report. AI suggestions are optional and only run when "
        "a provider is explicitly configured and opted into."
    ),
    version=__version__,
)

app.state = _State()

app.add_middleware(
    CORSMiddleware,
    allow_origins=app.state.settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root() -> dict:
    return {
        "app": app.state.settings.app_name,
        "version": __version__,
        "docs": "/docs",
        "health": "/api/health",
    }


def main() -> None:  # pragma: no cover
    import uvicorn

    uvicorn.run("app.app:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":  # pragma: no cover
    main()
