"""PDF extraction using PyMuPDF (imported as ``pymupdf``).

Extracts, per page in order: text blocks (with heading inference from font
size), external links (with the visible anchor text near each link rect),
and images. It also reports whether the document is tagged (a PDF/UA
structure tree), which is a strong, genuine accessibility signal.

Headings are inferred heuristically from font size. This is a real
deterministic heuristic; downstream findings are worded to reflect that
inference rather than claiming PDF/UA conformance.

Note: PyMuPDF 2.x exposes the API via ``import pymupdf`` (``import fitz`` is
deprecated). ``Document.is_tagged`` was removed in 2.x, so tagging is
detected by looking for a ``StructTreeRoot`` in the document catalog.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pymupdf  # PyMuPDF 2.x

from ..models import Block, BlockType
from . import Extraction


def _heading_level_for(size: float, body: float) -> int | None:
    if body <= 0:
        return None
    ratio = size / body
    if ratio >= 1.55:
        return 1
    if ratio >= 1.30:
        return 2
    if ratio >= 1.15:
        return 3
    return None


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _catalog_xref(doc: Any) -> int | None:
    """Return the document catalog xref, or None."""
    try:
        cat = doc.pdf_catalog()
        if cat and cat > 0:
            return cat
    except Exception:  # pragma: no cover - API differences
        pass
    try:
        for xref in range(1, doc.xref_length()):
            try:
                if "/Catalog" in doc.xref_object(xref, compressed=False):
                    return xref
            except Exception:
                continue
    except Exception:  # pragma: no cover
        pass
    return None


def _is_tagged(doc: Any) -> bool:
    """True if the PDF has a structure tree (tagged / PDF/UA-ish)."""
    cat = _catalog_xref(doc)
    if cat is None:
        return False
    try:
        value, _typ = doc.xref_get_key(cat, "StructTreeRoot")
        return value not in (None, "", "null")
    except Exception:  # pragma: no cover
        return False


def _text_in_rect(words: list[Any], x0: float, y0: float, x1: float, y1: float) -> str:
    picked: list[str] = []
    for w in words:
        wx0, wy0, wx1, wy1, word = w[0], w[1], w[2], w[3], w[4]
        cx = (wx0 + wx1) / 2.0
        cy = (wy0 + wy1) / 2.0
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            picked.append(word)
    return " ".join(picked).strip()


def extract_pdf(path: Path) -> Extraction:
    result = Extraction()
    doc = pymupdf.open(path)
    try:
        if doc.needs_pass:
            result.warnings.append("PDF is password-protected; text could not be read.")
            return result

        # First pass: estimate the body font size from all text spans.
        all_sizes: list[float] = []
        for page in doc:
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span.get("text", "").strip():
                            all_sizes.append(span["size"])
        body_size = _median(all_sizes)

        index = 0
        for page_number, page in enumerate(doc, start=1):
            # 1) Text blocks.
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:  # text block only
                    continue
                text_parts: list[str] = []
                max_size = 0.0
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text_parts.append(span.get("text", ""))
                        max_size = max(max_size, span.get("size", 0.0))
                text = "".join(text_parts).strip()
                if not text:
                    continue
                index += 1
                level = _heading_level_for(max_size, body_size) if max_size else None
                result.blocks.append(
                    Block(
                        index=index,
                        kind=BlockType.HEADING if level else BlockType.PARAGRAPH,
                        text=text[:500],
                        heading_level=level,
                        page=page_number,
                    )
                )

            # 2) External links on this page, with their visible anchor text.
            words = page.get_text("words")
            for link in page.get_links():
                if link.get("kind") not in (pymupdf.LINK_URI, pymupdf.LINK_LAUNCH):
                    continue
                rect = link.get("from")
                if rect is None:
                    continue
                label = _text_in_rect(words, rect.x0, rect.y0, rect.x1, rect.y1)
                if not label:
                    continue  # no visible anchor text -> nothing to judge
                index += 1
                result.blocks.append(
                    Block(
                        index=index,
                        kind=BlockType.LINK,
                        text=(link.get("uri") or link.get("file") or "")[:300],
                        link_label=label,
                        page=page_number,
                    )
                )

            # 3) Images on this page.
            for info in page.get_image_info(xrefs=True):
                index += 1
                result.blocks.append(
                    Block(
                        index=index,
                        kind=BlockType.IMAGE,
                        text="Image",
                        # PyMuPDF does not expose reliable alt text for images,
                        # so we mark it unknown (None) -> flagged for review.
                        has_alt_text=None,
                        page=page_number,
                    )
                )
                result.meta.setdefault("images", []).append(
                    {"page": page_number, "xref": info.get("xref")}
                )

        result.meta["is_tagged"] = _is_tagged(doc)
        result.meta["page_count"] = doc.page_count
        result.meta["body_size"] = body_size
        result.meta["image_count"] = len(result.meta.get("images", []))
    finally:
        doc.close()
    return result
