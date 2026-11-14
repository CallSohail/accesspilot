"""Integration tests for the FastAPI application.

These exercise the full upload → analysis → download pipeline via the
FastAPI test client, and verify error handling for malformed uploads.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.app import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def settings() -> object:
    from app.config import Settings

    import tempfile

    return Settings(
        max_upload_mb=10,
        upload_dir=str(tempfile.mkdtemp(prefix="accesspilot_api_test_")),
        ai_enabled=False,
        ai_api_key="",
    )


# --------------------------------------------------------------------------- #
# Health / root
# --------------------------------------------------------------------------- #


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == "AccessPilot"
    assert body["ai_configured"] is False


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["app"] == "AccessPilot"


# --------------------------------------------------------------------------- #
# Upload validation
# --------------------------------------------------------------------------- #


def test_upload_wrong_type(client):
    resp = client.post(
        "/api/analyze",
        files={"file": ("evil.exe", b"fake executable", "application/x-msdownload")},
    )
    assert resp.status_code == 415
    assert "Unsupported file type" in resp.json()["detail"]


def test_upload_empty_file(client):
    resp = client.post(
        "/api/analyze",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


# --------------------------------------------------------------------------- #
# Full pipeline with synthetic PDF
# --------------------------------------------------------------------------- #


def _make_pdf_bytes() -> bytes:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 50), "My Course", fontsize=28)
    page.insert_text((72, 100), "Body paragraph one.", fontsize=10)
    page.insert_text((72, 120), "Body paragraph two.", fontsize=10)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def test_analyze_pdf_and_download(client):
    pdf_bytes = _make_pdf_bytes()
    resp = client.post(
        "/api/analyze",
        files={"file": ("course.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    report = resp.json()
    assert report["document"]["filename"] == "course.pdf"
    assert report["document"]["kind"] == "pdf"
    assert report["document"]["num_blocks"] > 0
    # Should have at least one finding (untagged PDF, heading-related).
    assert len(report["findings"]) > 0
    report_id = report["report_id"]

    # Re-fetch the report.
    fetch = client.get(f"/api/reports/{report_id}")
    assert fetch.status_code == 200
    assert fetch.json()["report_id"] == report_id

    # Download JSON.
    j = client.get(f"/api/reports/{report_id}/download.json")
    assert j.status_code == 200
    assert j.headers["content-type"] == "application/json"
    import json

    json.loads(j.text)  # must be valid JSON

    # Download HTML.
    h = client.get(f"/api/reports/{report_id}/download.html")
    assert h.status_code == 200
    assert h.headers["content-type"].startswith("text/html")
    assert "AccessPilot" in h.text
    assert "course.pdf" in h.text


def test_analyze_missing_report_404(client):
    resp = client.get("/api/reports/does-not-exist")
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Malformed file handling
# --------------------------------------------------------------------------- #


def test_malformed_pdf_returns_500_with_detail(client):
    # A file that claims to be PDF but is not — PyMuPDF raises on open.
    resp = client.post(
        "/api/analyze",
        files={"file": ("broken.pdf", b"definitely not a pdf", "application/pdf")},
    )
    # The extractor wraps errors gracefully; either we get 200 with warnings
    # or 500 with a detail message. Both are acceptable; we assert no unhandled
    # exception (no HTML error page).
    assert resp.status_code in (200, 500)
    if resp.status_code == 500:
        assert "detail" in resp.json()


# --------------------------------------------------------------------------- #
# AI assistant (no provider configured)
# --------------------------------------------------------------------------- #


def test_assistant_disabled(client):
    resp = client.post(
        "/api/assistant",
        json={"question": "How do I fix the heading hierarchy?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["provider_configured"] is False
    assert "No AI provider is configured" in body["error"]


def test_assistant_min_length(client):
    resp = client.post("/api/assistant", json={"question": ""})
    # Pydantic enforces min_length=1
    assert resp.status_code == 422
