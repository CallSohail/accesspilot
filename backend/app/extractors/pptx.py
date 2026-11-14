"""PPTX extraction using python-pptx.

Slides are traversed in order. For each slide we emit the title (when a
title placeholder exists or a large-font text frame is found), the body
text, and one block per image. A ``has_alt_text`` heuristic for pictures:
python-pptx does not expose a reliable alt-text accessor in stable versions,
so we mark pictures as ``None`` (unknown) and rely on the checker to flag
them for human review rather than asserting a false finding.
"""

from __future__ import annotations

from pathlib import Path

from ..models import Block, BlockType
from . import Extraction

# Text frames whose font size is at or above this (pt) are treated as a
# slide heading candidate when no explicit title placeholder exists.
_HEADING_SIZE_PT = 24.0


def _shape_is_picture(shape) -> bool:
    try:
        return shape.shape_type == 13  # MSO_SHAPE_TYPE.PICTURE
    except Exception:  # pragma: no cover
        return False


def _shape_text(shape) -> str:
    if not shape.has_text_frame:
        return ""
    return shape.text_frame.text.strip()


def _max_font_size(shape) -> float | None:
    sizes: list[float] = []
    if shape.has_text_frame:
        for para in shape.text_frame.paragraphs:
            for run in para.runs:
                if run.font.size is not None:
                    sizes.append(run.font.size.pt)
    return max(sizes) if sizes else None


def extract_pptx(path: Path) -> Extraction:
    from pptx import Presentation

    result = Extraction()
    prs = Presentation(path)

    index = 0
    image_count = 0
    for slide_number, slide in enumerate(prs.slides, start=1):
        # Collect picture shapes first so the title heuristic can ignore them.
        pictures: list = []
        text_shapes: list = []
        for shape in slide.shapes:
            if _shape_is_picture(shape):
                pictures.append(shape)
            elif shape.has_text_frame and shape.text_frame.text.strip():
                text_shapes.append(shape)

        # Title: prefer an explicit title placeholder, else the largest text.
        title_text: str | None = None
        try:
            if slide.shapes.title is not None and slide.shapes.title.has_text_frame:
                title_text = slide.shapes.title.text_frame.text.strip() or None
        except Exception:  # pragma: no cover
            title_text = None

        body_text = "\n".join(
            _shape_text(s) for s in text_shapes if s is not slide.shapes.title
        )
        if body_text:
            index += 1
            result.blocks.append(
                Block(
                    index=index,
                    kind=BlockType.PARAGRAPH,
                    text=body_text[:600],
                    slide=slide_number,
                )
            )

        # Heading from title placeholder (or largest-font fallback).
        heading_text = title_text
        if not heading_text:
            largest = max(
                text_shapes,
                key=lambda s: _max_font_size(s) or 0.0,
                default=None,
            )
            if largest is not None and (_max_font_size(largest) or 0) >= _HEADING_SIZE_PT:
                heading_text = _shape_text(largest)
        if heading_text:
            index += 1
            result.blocks.append(
                Block(
                    index=index,
                    kind=BlockType.HEADING,
                    text=heading_text[:300],
                    heading_level=1,
                    slide=slide_number,
                )
            )

        for _ in pictures:
            image_count += 1
            index += 1
            result.blocks.append(
                Block(
                    index=index,
                    kind=BlockType.IMAGE,
                    text="Image",
                    has_alt_text=None,
                    slide=slide_number,
                )
            )

    result.meta["slide_count"] = len(prs.slides._sldIdLst)
    result.meta["image_count"] = image_count
    return result
