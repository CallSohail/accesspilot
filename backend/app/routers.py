"""API router for AccessPilot."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response

from .analysis import Analysis
from .assistant import Assistant
from .config import Settings
from .jobstore import JobStore
from .models import (
    AssistantRequest,
    AssistantResponse,
    DocumentKind,
    Report,
)
from .report import to_html, to_json
from .storage import JobStorage, new_job_id

router = APIRouter(prefix="/api")

_EXT_TO_KIND = {
    ".pdf": DocumentKind.PDF,
    ".docx": DocumentKind.DOCX,
    ".pptx": DocumentKind.PPTX,
}


def get_store() -> JobStore:
    from . import app as app_module

    # ``app_module`` is the ``app.app`` module; the FastAPI instance (which
    # carries ``.state``) is the module-level ``app`` name inside it.
    return app_module.app.state.store


def get_assistant() -> Assistant:
    from . import app as app_module

    return app_module.app.state.assistant


def get_settings() -> Settings:
    from . import app as app_module

    return app_module.app.state.settings


def _detect_kind(filename: str) -> DocumentKind | None:
    lower = filename.lower()
    for ext, kind in _EXT_TO_KIND.items():
        if lower.endswith(ext):
            return kind
    return None


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.version,
        "ai_configured": settings.ai_configured(),
        "ai_model": settings.ai_model,
    }


@router.post(
    "/analyze",
    response_model=Report,
    summary="Upload a PDF/DOCX/PPTX and run the accessibility analysis.",
)
async def analyze(
    file: UploadFile = File(...),
    store: JobStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> Report:
    name = file.filename or "upload"
    kind = _detect_kind(name)
    if kind is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type. Upload a .pdf, .docx, or .pptx file.",
        )

    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = await file.read()
    if len(data) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_mb} MB upload limit.",
        )

    job_id = new_job_id()
    storage = JobStorage(settings, job_id)
    try:
        path = storage.save_upload(data, name)
        analysis = Analysis(path=path, kind=kind, size_bytes=len(data), filename=name)
        report = analysis.run()
        store.add(report)
        return report
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {exc.__class__.__name__}: {exc}",
        )
    finally:
        storage.dispose()


@router.get(
    "/reports/{report_id}",
    response_model=Report,
    summary="Fetch a previously generated report by ID.",
)
def get_report(report_id: str, store: JobStore = Depends(get_store)) -> Report:
    report = store.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found or expired.")
    return report


@router.get(
    "/reports/{report_id}/download.json",
    summary="Download the report as JSON.",
)
def download_json(report_id: str, store: JobStore = Depends(get_store)) -> Response:
    report = store.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found or expired.")
    safe = report.document.filename or "report"
    return Response(
        content=to_json(report),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{safe}.accesspilot.json"'
        },
    )


@router.get(
    "/reports/{report_id}/download.html",
    summary="Download the report as a self-contained HTML file.",
)
def download_html(report_id: str, store: JobStore = Depends(get_store)) -> Response:
    report = store.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found or expired.")
    safe = report.document.filename or "report"
    return Response(
        content=to_html(report),
        media_type="text/html",
        headers={
            "Content-Disposition": f'attachment; filename="{safe}.accesspilot.html"'
        },
    )


@router.post(
    "/assistant",
    response_model=AssistantResponse,
    summary="Ask the (optional) AI assistant a question about the analysis.",
)
def assistant(
    payload: AssistantRequest,
    assistant: Assistant = Depends(get_assistant),
) -> AssistantResponse:
    result = assistant.ask(payload.question, payload.context)
    return AssistantResponse(**result)
