"""DOCX extraction using python-docx.

Walks the document body in reading order (paragraphs and tables), mapping
heading styles to levels, and flags inline images (which in DOCX carry no
meaningful accessible-name signal by default) and hyperlink labels.

Alt text: DOCX pictures can carry an ``a:title`` accessible name. We detect
whether a drawing has a non-empty title; if the API is unavailable we mark
``has_alt_text=None`` (unknown) rather than guessing.
"""

from __future__ import annotations

from pathlib import Path

from ..models import Block, BlockType
from . import Extraction

_HEADING_PREFIXES = ("Heading", "Title", "Subtitle", "Heading 1", "Heading 2")


def _heading_level(style_name: str) -> int | None:
    name = style_name.lower()
    if name.startswith("heading"):
        digits = "".join(ch for ch in name if ch.isdigit())
        if digits:
            return int(digits)
        return 1
    if name.startswith("title"):
        return 1
    if name.startswith("subtitle"):
        return 2
    return None


def _has_inline_image(paragraph) -> bool:
    try:
        import docx  # local import to keep module import light

        # Inline shapes live on the run's XML; check for blip/drawing elements.
        xml = paragraph._p.xml
        return "<a:blip " in xml or "<w:drawing>" in xml or "graphicData" in xml
    except Exception:  # pragma: no cover
        return False


def _image_has_title(paragraph) -> bool | None:
    """Return True/False if a title/alt is present, None if unknown."""
    try:
        xml = paragraph._p.xml
        if "<w:drawing>" in xml:
            # a:title is the accessible-name element inside a drawing.
            return ("<a:title " in xml) or ("<a:title>" in xml)
    except Exception:  # pragma: no cover
        pass
    return None


def _hyperlink_label(paragraph) -> str | None:
    """Return the visible text of a hyperlink run, or None."""
    try:
        # python-docx exposes hyperlinks via w:hyperlink in the run XML.
        xml = paragraph._p.xml
        if "<w:hyperlink " in xml or "<w:hyperlink>" in xml:
            # The hyperlink's visible text is part of the paragraph text.
            return paragraph.text.strip() or None
    except Exception:  # pragma: no cover
        pass
    return None


def extract_docx(path: Path) -> Extraction:
    import docx

    result = Extraction()
    document = docx.Document(path)

    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    body = document.element.body
    index = 0
    image_count = 0
    image_with_title = 0

    for child in body.iterchildren():
        tag = child.tag
        if tag.endswith("}p"):  # paragraph
            paragraph = Paragraph(child, document)
            text = paragraph.text.strip()
            style = paragraph.style.name if paragraph.style is not None else ""
            has_img = _has_inline_image(paragraph)
            if has_img:
                image_count += 1
                alt = _image_has_title(paragraph)
                if alt is True:
                    image_with_title += 1
                index += 1
                result.blocks.append(
                    Block(
                        index=index,
                        kind=BlockType.IMAGE,
                        text="" if not text else text[:300],
                        has_alt_text=alt,
                    )
                )
                if not text:
                    continue
            if not text:
                continue
            level = _heading_level(style)
            link_label = _hyperlink_label(paragraph) if text else None
            index += 1
            kind = (
                BlockType.HEADING
                if level
                else BlockType.LINK
                if link_label
                else BlockType.PARAGRAPH
            )
            result.blocks.append(
                Block(
                    index=index,
                    kind=kind,
                    text=text[:500],
                    heading_level=level,
                    link_label=link_label,
                )
            )
        elif tag.endswith("}tbl"):  # table
            table = Table(child, document)
            rows = len(table.rows)
            cols = len(table.columns) if table.rows else 0
            index += 1
            result.blocks.append(
                Block(
                    index=index,
                    kind=BlockType.TABLE,
                    text=f"Table with {rows} rows and {cols} columns",
                )
            )

    result.meta["image_count"] = image_count
    result.meta["image_with_title"] = image_with_title
    return result
