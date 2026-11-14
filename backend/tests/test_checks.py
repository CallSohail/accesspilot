"""Unit tests for the deterministic accessibility checks.

These tests exercise the checks directly against hand-crafted Block lists
so we can assert specific findings without going through the extractors.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.checks import run_checks
from app.models import Block, BlockType, DocumentKind, FindingSource, Severity


def _blocks(*specs: tuple) -> list[Block]:
    """Build a Block list from (index, kind, text, heading_level) tuples."""
    return [
        Block(
            index=i,
            kind=BlockType(kind),
            text=text,
            heading_level=level,
            page=1,
        )
        for i, (kind, text, level) in enumerate(specs, start=1)
    ]


# --------------------------------------------------------------------------- #
# Empty document
# --------------------------------------------------------------------------- #


def test_empty_document_raises_finding():
    findings = run_checks([], DocumentKind.PDF, {"is_tagged": True}, [])
    assert any(f.rule == "content.empty" for f in findings)


def test_non_empty_no_empty_finding():
    blocks = _blocks(("paragraph", "Some text.", None))
    findings = run_checks(blocks, DocumentKind.DOCX, {}, [])
    assert not any(f.rule == "content.empty" for f in findings)


# --------------------------------------------------------------------------- #
# Heading checks
# --------------------------------------------------------------------------- #


def test_no_headings_flagged_for_docx():
    blocks = _blocks(
        ("paragraph", "Body text one.", None),
        ("paragraph", "Body text two.", None),
    )
    findings = run_checks(blocks, DocumentKind.DOCX, {}, [])
    assert any(f.rule == "headings.none" for f in findings)


def test_no_headings_flagged_for_pdf():
    blocks = _blocks(("paragraph", "Plain text.", None))
    findings = run_checks(blocks, DocumentKind.PDF, {"is_tagged": False}, [])
    assert any(f.rule == "headings.none" for f in findings)


def test_heading_hierarchy_skip_detected():
    # H1 then H3 (skipping H2)
    blocks = _blocks(
        ("heading", "Title", 1),
        ("paragraph", "Body.", None),
        ("heading", "Skipped", 3),
    )
    findings = run_checks(blocks, DocumentKind.DOCX, {}, [])
    hierarchy = [f for f in findings if f.rule == "headings.hierarchy"]
    assert len(hierarchy) >= 1
    assert hierarchy[0].suggestion is not None


def test_first_heading_not_h1():
    blocks = _blocks(
        ("heading", "Section", 2),
        ("paragraph", "Body.", None),
    )
    findings = run_checks(blocks, DocumentKind.DOCX, {}, [])
    first = [f for f in findings if f.rule == "headings.first"]
    assert len(first) == 1
    assert first[0].severity == Severity.INFO


def test_clean_heading_hierarchy_no_warnings():
    blocks = _blocks(
        ("heading", "Title", 1),
        ("paragraph", "Body.", None),
        ("heading", "Section A", 2),
        ("paragraph", "More body.", None),
        ("heading", "Section B", 2),
    )
    findings = run_checks(blocks, DocumentKind.DOCX, {}, [])
    assert not any(f.rule == "headings.hierarchy" for f in findings)
    assert not any(f.rule == "headings.first" for f in findings)


# --------------------------------------------------------------------------- #
# Link checks
# --------------------------------------------------------------------------- #


def test_generic_link_label_flagged():
    blocks = [
        Block(index=1, kind=BlockType.PARAGRAPH, text="Some text.", page=1),
        Block(
            index=2,
            kind=BlockType.LINK,
            text="https://example.com/syllabus",
            link_label="click here",
            page=1,
        ),
    ]
    findings = run_checks(blocks, DocumentKind.DOCX, {}, [])
    generic = [f for f in findings if f.rule == "links.generic_label"]
    assert len(generic) == 1
    assert generic[0].source == FindingSource.DETERMINISTIC


def test_url_as_link_text_flagged():
    blocks = [
        Block(
            index=1,
            kind=BlockType.LINK,
            text="https://example.com/syllabus",
            link_label="https://example.com/syllabus",
            page=1,
        ),
    ]
    findings = run_checks(blocks, DocumentKind.DOCX, {}, [])
    url = [f for f in findings if f.rule == "links.url_as_text"]
    assert len(url) == 1


def test_duplicate_link_labels_flagged():
    blocks = [
        Block(
            index=1,
            kind=BlockType.LINK,
            text="https://example.com/a",
            link_label="read the syllabus",
            page=1,
        ),
        Block(
            index=2,
            kind=BlockType.LINK,
            text="https://example.com/b",
            link_label="read the syllabus",
            page=1,
        ),
    ]
    findings = run_checks(blocks, DocumentKind.DOCX, {}, [])
    dup = [f for f in findings if f.rule == "links.duplicate"]
    assert len(dup) == 1


def test_unique_link_labels_not_flagged():
    blocks = [
        Block(
            index=1,
            kind=BlockType.LINK,
            text="https://example.com/a",
            link_label="read the syllabus",
            page=1,
        ),
        Block(
            index=2,
            kind=BlockType.LINK,
            text="https://example.com/b",
            link_label="view the assignment",
            page=1,
        ),
    ]
    findings = run_checks(blocks, DocumentKind.DOCX, {}, [])
    assert not any(f.rule == "links.duplicate" for f in findings)


# --------------------------------------------------------------------------- #
# Image alt text
# --------------------------------------------------------------------------- #


def test_missing_image_alt_flagged():
    blocks = [
        Block(
            index=1,
            kind=BlockType.IMAGE,
            text="Figure 1",
            has_alt_text=False,
            page=1,
        )
    ]
    findings = run_checks(blocks, DocumentKind.DOCX, {}, [])
    missing = [f for f in findings if f.rule == "images.missing_alt"]
    assert len(missing) == 1
    assert missing[0].severity == Severity.ERROR


def test_unknown_image_alt_no_false_positive():
    """has_alt_text=None (unknown) should NOT produce a missing_alt finding."""
    blocks = [
        Block(
            index=1,
            kind=BlockType.IMAGE,
            text="Figure",
            has_alt_text=None,
            page=1,
        )
    ]
    findings = run_checks(blocks, DocumentKind.DOCX, {}, [])
    # No images.missing_alt, but for PDF/PPTX we get a human review item.
    missing = [f for f in findings if f.rule == "images.missing_alt"]
    assert not missing


def test_pdf_image_unknown_gets_human_review():
    blocks = [
        Block(
            index=1,
            kind=BlockType.IMAGE,
            text="Image",
            has_alt_text=None,
            page=1,
        )
    ]
    findings = run_checks(blocks, DocumentKind.PDF, {"is_tagged": False}, [])
    review = [f for f in findings if f.rule == "images.alt_review"]
    assert len(review) == 1
    assert review[0].source == FindingSource.HUMAN


# --------------------------------------------------------------------------- #
# PDF tagging
# --------------------------------------------------------------------------- #


def test_pdf_untagged_flagged():
    blocks = _blocks(("heading", "Title", 1), ("paragraph", "Body.", None))
    findings = run_checks(blocks, DocumentKind.PDF, {"is_tagged": False}, [])
    untagged = [f for f in findings if f.rule == "pdf.untagged"]
    assert len(untagged) == 1


def test_pdf_tagged_not_flagged():
    blocks = _blocks(("heading", "Title", 1), ("paragraph", "Body.", None))
    findings = run_checks(blocks, DocumentKind.PDF, {"is_tagged": True}, [])
    assert not any(f.rule == "pdf.untagged" for f in findings)


# --------------------------------------------------------------------------- #
# Source tagging
# --------------------------------------------------------------------------- #


def test_deterministic_findings_have_correct_source():
    blocks = _blocks(("paragraph", "Just body.", None))
    findings = run_checks(blocks, DocumentKind.DOCX, {}, [])
    for f in findings:
        if f.source != FindingSource.HUMAN:
            assert f.source == FindingSource.DETERMINISTIC


def test_human_findings_are_labelled():
    blocks = [
        Block(
            index=1,
            kind=BlockType.IMAGE,
            text="Image",
            has_alt_text=None,
            page=1,
        )
    ]
    findings = run_checks(blocks, DocumentKind.PDF, {"is_tagged": False}, [])
    human = [f for f in findings if f.source == FindingSource.HUMAN]
    assert human  # at least one human review item for PDF
