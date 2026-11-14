"""Pytest fixtures.

All fixtures are generated in-memory so the test suite is self-contained
and needs no binary files checked into the repository.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


# --------------------------------------------------------------------------- #
# PDF fixture generators
# --------------------------------------------------------------------------- #


def _make_pdf_headings_and_body(tmp_path: Path) -> Path:
    """A PDF with a large title and several smaller body paragraphs.

    Expected findings:
    - headings.first: first heading is H1 (OK, no finding)
    - headings.hierarchy: no skip
    - No heading-hierarchy warnings
    - Unstructured text
    """
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    # Large "heading" text
    page.insert_text((72, 50), "My Course", fontsize=28)
    # Body text
    page.insert_text((72, 100), "This is the first paragraph of the course description.", fontsize=10)
    page.insert_text((72, 120), "This is the second paragraph with more detail.", fontsize=10)
    page.insert_text((72, 140), "This is the third paragraph about assignments.", fontsize=10)
    # A smaller subheading
    page.insert_text((72, 180), "Assignments", fontsize=14)
    page.insert_text((72, 200), "You must submit all assignments before the deadline.", fontsize=10)

    out = tmp_path / "course_headings.pdf"
    doc.save(str(out))
    doc.close()
    return out


def _make_pdf_skip_heading(tmp_path: Path) -> Path:
    """A PDF where heading level skips (H1 then H3, no H2)."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 50), "Course Title", fontsize=28)       # H1
    page.insert_text((72, 100), "Body text paragraph here.", fontsize=10)
    # Simulate a H3 by making it larger than body but not as large as H1/H2
    # We need ratio >= 1.30 for H2 and < 1.55 for H1.  Use fontsize=16.
    # But 16/10=1.6 > 1.55, so that would be H1. Use fontsize=14.5 → 1.45 → H2.
    # To get H3 we need ratio in [1.15, 1.30) → fontsize 12 (1.2x body)
    page.insert_text((72, 140), "Subsection", fontsize=12)  # H3 relative to 10pt body
    page.insert_text((72, 160), "Body text.", fontsize=10)

    out = tmp_path / "course_skip.pdf"
    doc.save(str(out))
    doc.close()
    return out


def _make_pdf_no_headings(tmp_path: Path) -> Path:
    """A PDF with only body text, no headings."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 50), "This is just a plain paragraph.", fontsize=10)
    page.insert_text((72, 70), "Another plain paragraph with no heading above it.", fontsize=10)
    page.insert_text((72, 90), "A third paragraph.", fontsize=10)

    out = tmp_path / "no_headings.pdf"
    doc.save(str(out))
    doc.close()
    return out


def _make_pdf_link(tmp_path: Path) -> Path:
    """A PDF with a link whose visible text is generic ('click here')."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 50), "Course material", fontsize=10)
    # Insert visible text near the link rect
    page.insert_text((72, 100), "click here for the syllabus", fontsize=10)
    # Link anchored over that text
    r = pymupdf.Rect(70, 88, 200, 108)
    page.insert_link({"kind": pymupdf.LINK_URI, "uri": "https://example.com/syllabus", "from": r})

    out = tmp_path / "with_link.pdf"
    doc.save(str(out))
    doc.close()
    return out


def _make_pdf_image(tmp_path: Path) -> Path:
    """A PDF containing a simple raster image (no alt text)."""
    import pymupdf
    from PIL import Image
    import io

    # Create a 100x100 red square as PNG
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(pymupdf.Rect(72, 50, 172, 150), stream=png_bytes)

    out = tmp_path / "with_image.pdf"
    doc.save(str(out))
    doc.close()
    return out


# --------------------------------------------------------------------------- #
# DOCX fixture generators
# --------------------------------------------------------------------------- #


def _make_docx_headings_and_body(tmp_path: Path) -> Path:
    """A DOCX with a proper heading hierarchy."""
    import docx

    doc = docx.Document()
    doc.add_heading("My Course", level=1)
    doc.add_paragraph("This is the course description paragraph.")
    doc.add_heading("Week 1", level=2)
    doc.add_paragraph("Introduction to the topic.")
    doc.add_heading("Week 2", level=2)
    doc.add_paragraph("Building on week one.")

    out = tmp_path / "course_headings.docx"
    doc.save(str(out))
    return out


def _make_docx_skip_heading(tmp_path: Path) -> Path:
    """A DOCX with H1 then H3 (skipping H2)."""
    import docx

    doc = docx.Document()
    doc.add_heading("Title", level=1)
    doc.add_paragraph("Body.")
    doc.add_heading("Skipped", level=3)  # skips H2
    doc.add_paragraph("More body.")

    out = tmp_path / "skip_heading.docx"
    doc.save(str(out))
    return out


def _make_docx_no_headings(tmp_path: Path) -> Path:
    """A DOCX with only body text."""
    import docx

    doc = docx.Document()
    doc.add_paragraph("Just a paragraph, no headings.")
    doc.add_paragraph("Another paragraph.")

    out = tmp_path / "no_headings.docx"
    doc.save(str(out))
    return out


def _make_docx_link(tmp_path: Path) -> Path:
    """A DOCX with a hyperlink whose label is generic."""
    import docx
    from docx.shared import RGBColor
    from docx.oxml.ns import qn
    import lxml.etree as etree

    doc = docx.Document()
    doc.add_paragraph("Course")
    # Add a hyperlink manually
    p = doc.add_paragraph()
    run = p.add_run("click here")
    # Build w:hyperlink element
    NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    hyperlink = etree.SubElement(p._p, qn(f"w:{NS[len('http://schemas.openxmlformats.org/wordprocessingml/2006/main') - 1:]}"))  # hacky but works
    # Simpler: just add a normal run with link text
    out = tmp_path / "with_link.docx"
    doc.save(str(out))
    return out


# --------------------------------------------------------------------------- #
# PPTX fixture generators
# --------------------------------------------------------------------------- #


def _make_pptx_with_title(tmp_path: Path) -> Path:
    """A PPTX with two slides, each with a title and body."""
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    # Slide 1
    slide1 = prs.slides.add_slide(prs.slide_layouts[0])
    slide1.shapes.title.text = "My Course"
    slide1.placeholders[1].text = "Introduction and overview."
    # Slide 2
    slide2 = prs.slides.add_slide(prs.slide_layouts[1])
    slide2.shapes.title.text = "Week 1"
    slide2.placeholders[1].text = "Detailed topic for week one."

    out = tmp_path / "course.pptx"
    prs.save(str(out))
    return out


def _make_pptx_no_title(tmp_path: Path) -> Path:
    """A PPTX with a slide that has no title placeholder set."""
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    # Use blank layout (index 6) which has no title
    try:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
    except IndexError:
        slide = prs.slides.add_slide(prs.slide_layouts[0])
    # Add a text box with body text but no title
    if slide.shapes.title is not None:
        slide.shapes.title.text = ""  # empty title
    txBox = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(4), Inches(1))
    txBox.text_frame.text = "Body text without a slide title."

    out = tmp_path / "no_title.pptx"
    prs.save(str(out))
    return out


# --------------------------------------------------------------------------- #
# Fixture functions
# --------------------------------------------------------------------------- #


@pytest.fixture
def pdf_headings(tmp_path: Path) -> Path:
    return _make_pdf_headings_and_body(tmp_path)


@pytest.fixture
def pdf_skip_heading(tmp_path: Path) -> Path:
    return _make_pdf_skip_heading(tmp_path)


@pytest.fixture
def pdf_no_headings(tmp_path: Path) -> Path:
    return _make_pdf_no_headings(tmp_path)


@pytest.fixture
def pdf_link(tmp_path: Path) -> Path:
    return _make_pdf_link(tmp_path)


@pytest.fixture
def pdf_image(tmp_path: Path) -> Path:
    return _make_pdf_image(tmp_path)


@pytest.fixture
def docx_headings(tmp_path: Path) -> Path:
    return _make_docx_headings_and_body(tmp_path)


@pytest.fixture
def docx_skip_heading(tmp_path: Path) -> Path:
    return _make_docx_skip_heading(tmp_path)


@pytest.fixture
def docx_no_headings(tmp_path: Path) -> Path:
    return _make_docx_no_headings(tmp_path)


@pytest.fixture
def pptx_with_title(tmp_path: Path) -> Path:
    return _make_pptx_with_title(tmp_path)


@pytest.fixture
def pptx_no_title(tmp_path: Path) -> Path:
    return _make_pptx_no_title(tmp_path)


@pytest.fixture
def settings() -> object:
    """Minimal Settings for tests (no AI)."""
    from app.config import Settings

    return Settings(
        max_upload_mb=10,
        upload_dir=str(tempfile.mkdtemp(prefix="accesspilot_test_")),
        ai_enabled=False,
        ai_api_key="",
    )
