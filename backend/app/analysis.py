"""Analysis orchestration: extract -> check -> (optional) AI -> report.

This is the central pipeline. It is deliberately defensive: extraction and
checking are isolated so a partially readable file still produces a useful
report with explicit warnings rather than an opaque crash.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from . import checks
from .config import Settings
from .extractors import Extraction, extract
from .models import (
    Block,
    BlockType,
    DocumentKind,
    DocumentMeta,
    Finding,
    Report,
    Severity,
    SummaryStats,
)


def _count_stats(findings: list[Finding]) -> SummaryStats:
    stats = SummaryStats()
    for f in findings:
        if f.severity == Severity.ERROR:
            stats.errors += 1
        elif f.severity == Severity.WARNING:
            stats.warnings += 1
        else:
            stats.info += 1
    return stats


def _build_suggestions(findings: list[Finding]) -> list:
    """Promote findings that carry a real before/after suggestion.

    We only surface before/after text the checks actually produced, so we
    never present invented rewrites as recommendations.
    """
    from .models import Suggestion

    out: list[Suggestion] = []
    for f in findings:
        if not f.suggestion:
            continue
        parts = f.suggestion.split("\n", 1)
        before = parts[0].removeprefix("before:").strip() if parts else ""
        after = parts[1].removeprefix("after:  ").strip() if len(parts) > 1 else ""
        out.append(
            Suggestion(
                finding_id=f.id,
                location=f.location,
                before=before,
                after=after,
                rationale=f.remediation,
                source=f.source,
            )
        )
    return out


class Analysis:
    """One analysis run for a single uploaded document."""

    def __init__(self, path: Path, kind: DocumentKind, size_bytes: int, filename: str):
        self.path = path
        self.kind = kind
        self.size_bytes = size_bytes
        self.filename = filename

    def run(self) -> Report:
        ext = _safe_extract(self.path, self.kind)
        findings = checks.run_checks(ext.blocks, self.kind, ext.meta, ext.warnings)
        stats = _count_stats(findings)
        stats.total_blocks = len(ext.blocks)

        report = Report(
            report_id=uuid.uuid4().hex,
            document=DocumentMeta(
                filename=self.filename,
                kind=self.kind,
                size_bytes=self.size_bytes,
                num_blocks=len(ext.blocks),
            ),
            blocks=ext.blocks,
            findings=findings,
            suggestions=_build_suggestions(findings),
            summary=stats,
            notes=_derive_notes(self.kind, ext.meta, ext.warnings),
        )
        return report


def _safe_extract(path: Path, kind: DocumentKind) -> Extraction:
    try:
        return extract(path, kind)
    except Exception as exc:
        return Extraction(
            blocks=[],
            warnings=[f"{kind.value} extraction failed: {exc.__class__.__name__}: {exc}"],
        )


def _derive_notes(kind: DocumentKind, meta: dict, warnings: list[str]) -> list[str]:
    notes = [
        "This report is generated from a limited set of automated, rule-based "
        "checks. It does not certify WCAG conformance or PDF/UA validity. "
        "Review items flagged for human review with a domain expert before "
        "publishing."
    ]
    if warnings:
        notes.append(f"Extraction warnings: {'; '.join(warnings)}")
    if kind == DocumentKind.PDF and not meta.get("is_tagged"):
        notes.append(
            "Because this PDF is untagged, structural findings (headings, "
            "hierarchy) are inferred from font metrics and may be less "
            "reliable than for tagged PDFs."
        )
    return notes
