"""Document extraction package.

Each extractor converts an uploaded file into a normalized list of
:class:`~app.models.Block` objects plus a small ``meta`` dict that carries
format-specific signals the checker uses (e.g. whether a PDF is tagged).

Extractors are defensive: a malformed or partially readable file should
yield as much as it can and never raise a crash that aborts the whole
analysis. Format-specific errors are recorded in ``warnings``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..models import Block, DocumentKind


@dataclass
class Extraction:
    blocks: list[Block] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class ExtractionError(Exception):
    """Raised when a file cannot be read as the declared type."""


def extract(path: Path, kind: DocumentKind) -> Extraction:
    """Dispatch to the right extractor for ``kind``.

    Defensive: a malformed or unreadable file yields an empty
    :class:`Extraction` with a recorded warning instead of raising, so the
    analysis pipeline can still produce a report (and surface the
    ``content.empty`` finding) rather than crashing.
    """
    try:
        if kind == DocumentKind.PDF:
            from .pdf import extract_pdf

            return extract_pdf(path)
        if kind == DocumentKind.DOCX:
            from .docx import extract_docx

            return extract_docx(path)
        if kind == DocumentKind.PPTX:
            from .pptx import extract_pptx

            return extract_pptx(path)
        raise ExtractionError(f"unsupported kind: {kind}")
    except ExtractionError:
        raise
    except Exception as exc:
        return Extraction(
            blocks=[],
            warnings=[
                f"{kind.value} extraction failed: {exc.__class__.__name__}: {exc}"
            ],
        )
