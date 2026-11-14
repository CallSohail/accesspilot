"""Extractor tests using the programmatically generated fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.extractors import extract
from app.models import BlockType, DocumentKind


def _kinds(blocks) -> set:
    return {b.kind for b in blocks}


# --------------------------------------------------------------------------- #
# PDF
# --------------------------------------------------------------------------- #


def test_pdf_extracts_headings_and_body(pdf_headings: Path):
    ext = extract(pdf_headings, DocumentKind.PDF)
    assert ext.blocks, "expected some blocks"
    kinds = _kinds(ext.blocks)
    assert BlockType.HEADING in kinds
    assert BlockType.PARAGRAPH in kinds
    # All blocks are page-numbered.
    assert all(b.page is not None for b in ext.blocks)
    # Body size is detected (positive).
    assert ext.meta.get("body_size", 0) > 0
    # Newly created PDF is not tagged.
    assert ext.meta.get("is_tagged") is False


def test_pdf_no_headings(pdf_no_headings: Path):
    ext = extract(pdf_no_headings, DocumentKind.PDF)
    headings = [b for b in ext.blocks if b.kind == BlockType.HEADING]
    # No large-text headings should be detected.
    assert not headings


def test_pdf_link_detection(pdf_link: Path):
    ext = extract(pdf_link, DocumentKind.PDF)
    links = [b for b in ext.blocks if b.kind == BlockType.LINK]
    assert links, "expected at least one link block"
    # The visible anchor text should have been captured.
    assert any("click" in (b.link_label or "").lower() for b in links)


def test_pdf_image_detection(pdf_image: Path):
    ext = extract(pdf_image, DocumentKind.PDF)
    images = [b for b in ext.blocks if b.kind == BlockType.IMAGE]
    assert len(images) == 1
    # PyMuPDF does not expose alt text reliably -> unknown.
    assert images[0].has_alt_text is None
    assert ext.meta.get("image_count") == 1


def test_pdf_untagged_flag(pdf_headings: Path):
    ext = extract(pdf_headings, DocumentKind.PDF)
    assert ext.meta.get("is_tagged") is False


# --------------------------------------------------------------------------- #
# DOCX
# --------------------------------------------------------------------------- #


def test_docx_headings_and_body(docx_headings: Path):
    ext = extract(docx_headings, DocumentKind.DOCX)
    headings = [b for b in ext.blocks if b.kind == BlockType.HEADING]
    # Two H1 (only one), two H2.
    levels = [b.heading_level for b in headings]
    assert 1 in levels
    assert 2 in levels
    # At least some body paragraphs.
    assert any(b.kind == BlockType.PARAGRAPH for b in ext.blocks)


def test_docx_heading_hierarchy_skip(docx_skip_heading: Path):
    ext = extract(docx_skip_heading, DocumentKind.DOCX)
    levels = [b.heading_level for b in ext.blocks if b.kind == BlockType.HEADING]
    assert 1 in levels and 3 in levels
    # No H2 in the fixture.
    assert 2 not in levels


def test_docx_no_headings(docx_no_headings: Path):
    ext = extract(docx_no_headings, DocumentKind.DOCX)
    assert not any(b.kind == BlockType.HEADING for b in ext.blocks)


# --------------------------------------------------------------------------- #
# PPTX
# --------------------------------------------------------------------------- #


def test_pptx_title_and_body(pptx_with_title: Path):
    ext = extract(pptx_with_title, DocumentKind.PPTX)
    headings = [b for b in ext.blocks if b.kind == BlockType.HEADING]
    assert len(headings) >= 2  # one per slide
    assert any("My Course" in b.text for b in headings)
    assert any("Week 1" in b.text for b in headings)
    assert ext.meta.get("slide_count") == 2


def test_pptx_no_title(pptx_no_title: Path):
    ext = extract(pptx_no_title, DocumentKind.PPTX)
    # Either the title is empty or missing; the extractor should still work
    # without crashing and produce at least the body text.
    assert ext.blocks, "expected at least one block"


# --------------------------------------------------------------------------- #
# Error handling: malformed file
# --------------------------------------------------------------------------- #


def test_malformed_pdf_returns_empty_with_warning(tmp_path: Path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"this is not a real pdf")
    ext = extract(bad, DocumentKind.PDF)
    # Should not raise; either return empty blocks or produce a warning.
    # PyMuPDF may raise on malformed PDFs — the extractor wraps nothing,
    # but the Analysis layer catches exceptions and records a warning.
    # Here we just assert it does not crash.
    assert ext.blocks == [] or ext.warnings


def test_malformed_docx_returns_empty_with_warning(tmp_path: Path):
    bad = tmp_path / "bad.docx"
    bad.write_bytes(b"not a zip at all")
    ext = extract(bad, DocumentKind.DOCX)
    assert ext.blocks == [] or ext.warnings
