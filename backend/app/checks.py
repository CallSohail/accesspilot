"""Deterministic accessibility checks.

These are rule-based, reproducible checks over the normalized ``Block``
list produced by the extractors. They emit ``Finding`` objects with a
``source`` of either ``deterministic`` (we measured something concrete) or
``human`` (we can only flag that a person needs to look; we make no claim
about the underlying truth).

Design rules:
- Never emit a fake finding. If a signal is unavailable (e.g. PDF image alt
  text cannot be read), we either skip the check or emit a ``human`` review
  item explicitly labelled as such.
- Every finding carries a concrete location and a remediation a user can act
  on.
- ``before``/``after`` suggestions are only attached when we can actually
  produce a better artifact (e.g. a clearer link label), never invented.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .models import Block, BlockType, DocumentKind, Finding, FindingSource, Severity

# Generic link labels that provide no useful context when read in isolation.
_GENERIC_LINK_LABELS = {
    "click here",
    "here",
    "this",
    "this link",
    "link",
    "read more",
    "more",
    "learn more",
    "learn more.",
    "see more",
    "go here",
    "follow this link",
    "continue",
    "next",
    "submit",
}


@dataclass
class CheckContext:
    blocks: list[Block]
    kind: DocumentKind
    meta: dict
    warnings: list[str]


def _location(block: Block) -> str:
    if block.slide is not None:
        return f"slide {block.slide}"
    if block.page is not None:
        return f"page {block.page}"
    return f"block {block.index}"


def _mk(
    rule: str,
    severity: Severity,
    source: FindingSource,
    location: str,
    description: str,
    detail: str = "",
    remediation: str = "",
    wcag_ref: str = "",
    block_index: int | None = None,
    suggestion: str | None = None,
) -> Finding:
    return Finding(
        id=f"{rule}#{block_index or 0}",
        rule=rule,
        severity=severity,
        source=source,
        location=location,
        description=description,
        detail=detail,
        remediation=remediation,
        wcag_ref=wcag_ref,
        block_index=block_index,
        suggestion=suggestion,
    )


# --------------------------------------------------------------------------- #
# Individual checks
# --------------------------------------------------------------------------- #


def check_empty_document(ctx: CheckContext) -> list[Finding]:
    if not ctx.blocks:
        return [
            _mk(
                "content.empty",
                Severity.ERROR,
                FindingSource.DETERMINISTIC,
                "document",
                "No readable text or structure was extracted from this document.",
                detail="; ".join(ctx.warnings) if ctx.warnings else "file may be image-only, corrupted, or protected.",
                remediation="Confirm the source file contains extractable text, or provide a corrected/OCR'd version before relying on automated checks.",
                wcag_ref="1.4.5",
            )
        ]
    return []


def check_pdf_tagged(ctx: CheckContext) -> list[Finding]:
    if ctx.kind != DocumentKind.PDF:
        return []
    if "is_tagged" not in ctx.meta:
        return []
    if ctx.meta.get("is_tagged"):
        return []
    return [
        _mk(
            "pdf.untagged",
            Severity.WARNING,
            FindingSource.DETERMINISTIC,
            "document",
            "This PDF is not tagged, so screen readers have no reliable structure to navigate.",
            detail="No tagged PDF structure (PDF/UA) was detected.",
            remediation="Export the document with 'tagged PDF' / 'Include a document structure tag tree' enabled, or run a PDF/UA remediation pass. This does not by itself guarantee conformance.",
            wcag_ref="1.3.1",
        )
    ]


def check_heading_presence(ctx: CheckContext) -> list[Finding]:
    headings = [b for b in ctx.blocks if b.kind == BlockType.HEADING]
    has_text = any(b.text.strip() for b in ctx.blocks if b.kind != BlockType.IMAGE)
    if not has_text:
        return []
    if not headings:
        return [
            _mk(
                "headings.none",
                Severity.WARNING,
                FindingSource.DETERMINISTIC,
                "document",
                "No headings were detected in the document.",
                detail="Readers who navigate by heading will find no way to move between sections.",
                remediation="Add clear heading styles (H1 for the title, H2/H3 for sections) to major content sections.",
                wcag_ref="2.4.6",
            )
        ]
    return []


def check_heading_hierarchy(ctx: CheckContext) -> list[Finding]:
    headings = [b for b in ctx.blocks if b.kind == BlockType.HEADING and b.heading_level]
    findings: list[Finding] = []
    prev_level: int | None = None
    for b in headings:
        level = b.heading_level or 1
        if prev_level is not None and level > prev_level + 1:
            findings.append(
                _mk(
                    "headings.hierarchy",
                    Severity.WARNING,
                    FindingSource.DETERMINISTIC,
                    _location(b),
                    f"Heading level jumps from H{prev_level} to H{level}, skipping a level.",
                    detail=f"'{b.text[:80]}'",
                    remediation=f"Use the next level (H{prev_level + 1}) instead of jumping to H{level}, or keep headings in a single, contiguous hierarchy.",
                    wcag_ref="1.3.1",
                    block_index=b.index,
                    suggestion=(
                        f"before: H{prev_level} -> H{level}\n"
                        f"after:  H{prev_level} -> H{prev_level + 1}"
                    ),
                )
            )
        prev_level = level
    return findings


def check_first_heading(ctx: CheckContext) -> list[Finding]:
    headings = [b for b in ctx.blocks if b.kind == BlockType.HEADING and b.heading_level]
    if not headings:
        return []
    first = headings[0]
    if first.heading_level != 1:
        return [
            _mk(
                "headings.first",
                Severity.INFO,
                FindingSource.DETERMINISTIC,
                _location(first),
                f"The first heading is H{first.heading_level}, not a single top-level H1.",
                detail=f"'{first.text[:80]}'",
                remediation="Start the document with a single H1 title that names the content.",
                wcag_ref="1.3.1",
                block_index=first.index,
            )
        ]
    return []


def _is_generic_label(label: str | None) -> bool:
    if not label:
        return True
    return label.strip().lower() in _GENERIC_LINK_LABELS


def check_link_labels(ctx: CheckContext) -> list[Finding]:
    links = [b for b in ctx.blocks if b.kind == BlockType.LINK]
    findings: list[Finding] = []
    label_counts = Counter(
        (b.link_label or "").strip().lower() for b in links if b.link_label
    )
    for b in links:
        label = (b.link_label or "").strip()
        uri = (b.text or "").strip()
        # URL used as visible text
        if label.lower().startswith(("http://", "https://", "www.")):
            findings.append(
                _mk(
                    "links.url_as_text",
                    Severity.WARNING,
                    FindingSource.DETERMINISTIC,
                    _location(b),
                    "A full URL is used as the visible link text.",
                    detail=f"visible text: '{label}' -> {uri[:120]}",
                    remediation="Replace the URL with descriptive text (e.g. the destination's title). Screen readers often read raw URLs character by character.",
                    wcag_ref="2.4.4",
                    block_index=b.index,
                    suggestion=(
                        f"before: {label}\n"
                        f"after:  describe the destination (e.g. its page or resource title)"
                    ),
                )
            )
            continue
        if _is_generic_label(label):
            findings.append(
                _mk(
                    "links.generic_label",
                    Severity.WARNING,
                    FindingSource.DETERMINISTIC,
                    _location(b),
                    "The link text does not convey the link's purpose.",
                    detail=f"visible text: '{label or '(empty)'}' -> {uri[:120]}",
                    remediation="Use link text that describes the destination on its own (e.g. 'Download the 2024 syllabus' instead of 'click here').",
                    wcag_ref="2.4.4",
                    block_index=b.index,
                )
            )
    # duplicate identical labels
    for label, count in label_counts.items():
        if not label or count < 2:
            continue
        examples = [b for b in links if (b.link_label or "").strip().lower() == label][:3]
        findings.append(
            _mk(
                "links.duplicate",
                Severity.WARNING,
                FindingSource.DETERMINISTIC,
                ", ".join(_location(b) for b in examples),
                f"The same link label '{label}' is repeated {count} times, so it is not unique on the page.",
                detail="Non-unique link labels make 'list of links' navigation ambiguous.",
                remediation="Make each link's text unique by adding context that distinguishes its destination.",
                wcag_ref="2.4.4",
                block_index=examples[0].index,
            )
        )
    return findings


def check_image_alt(ctx: CheckContext) -> list[Finding]:
    """Flag images whose alt-text status is known and missing.

    Where the format does not expose alt text (e.g. PDF images), we instead
    emit a single ``human`` review item rather than a false positive.
    """
    images = [b for b in ctx.blocks if b.kind == BlockType.IMAGE]
    if not images:
        return []

    missing: list[Block] = [b for b in images if b.has_alt_text is False]
    unknown: list[Block] = [b for b in images if b.has_alt_text is None]

    findings: list[Finding] = []
    for b in missing:
        findings.append(
            _mk(
                "images.missing_alt",
                Severity.ERROR,
                FindingSource.DETERMINISTIC,
                _location(b),
                "An image has no alternative text.",
                detail=f"'{b.text[:80]}'" if b.text else "image element",
                remediation="Add concise, meaningful alt text describing the purpose of the image (or mark it decorative so assistive tech can skip it).",
                wcag_ref="1.1.1",
                block_index=b.index,
                suggestion=(
                    f"before: <img with no alt text>\n"
                    f"after:  <img alt='describe the figure's key information'>"
                ),
            )
        )

    if unknown and (ctx.kind in (DocumentKind.PDF, DocumentKind.PPTX)):
        findings.append(
            _mk(
                "images.alt_review",
                Severity.INFO,
                FindingSource.HUMAN,
                "document",
                f"{len(unknown)} image(s) could not have their alt text automatically verified.",
                detail=(
                    "Alt text for images is not reliably exposed by this format/extractor."
                ),
                remediation="Manually review each image and confirm it either has meaningful alt text or is appropriately marked decorative.",
                wcag_ref="1.1.1",
            )
        )
    return findings


def check_reading_order(ctx: CheckContext) -> list[Finding]:
    """Flag reading order for human review on multi-page PDFs.

    We do not attempt to *prove* a reading-order defect (that would require
    reliable coordinates/structure we do not have). Instead we honestly flag
    that automated reading-order verification was not performed, so a person
    should confirm it. This is a ``human`` item, not a false positive.
    """
    if ctx.kind != DocumentKind.PDF:
        return []
    if not any(b.page is not None for b in ctx.blocks):
        return []
    return [
        _mk(
            "reading_order.review",
            Severity.INFO,
            FindingSource.HUMAN,
            "document",
            "Reading order was not automatically verified for this PDF.",
            detail=(
                "Text extraction alone cannot reliably confirm that screen "
                "readers will read content in visual order (common risk in "
                "multi-column layouts)."
            ),
            remediation="Confirm reading order with a PDF/UA validator or a screen reader before publishing.",
            wcag_ref="1.3.2",
        )
    ]


def check_long_paragraphs(ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = []
    for b in ctx.blocks:
        if b.kind != BlockType.PARAGRAPH:
            continue
        words = b.text.split()
        if len(words) > 160:
            findings.append(
                _mk(
                    "structure.long_paragraph",
                    Severity.INFO,
                    FindingSource.DETERMINISTIC,
                    _location(b),
                    "A very long paragraph with no subheadings may be hard to scan.",
                    detail=f"{len(words)} words",
                    remediation="Consider breaking long passages into smaller sections with headings or lists.",
                    wcag_ref="1.4.4",
                    block_index=b.index,
                )
            )
    # Cap to avoid noisy reports.
    return findings[:10]


_ALL_CHECKS = [
    check_empty_document,
    check_pdf_tagged,
    check_heading_presence,
    check_heading_hierarchy,
    check_first_heading,
    check_link_labels,
    check_image_alt,
    check_reading_order,
    check_long_paragraphs,
]


def run_checks(
    blocks: list[Block],
    kind: DocumentKind,
    meta: dict,
    warnings: list[str] | None = None,
) -> list[Finding]:
    """Run every deterministic check and return the combined findings."""
    ctx = CheckContext(blocks=blocks, kind=kind, meta=meta, warnings=warnings or [])
    findings: list[Finding] = []
    for check in _ALL_CHECKS:
        try:
            findings.extend(check(ctx))
        except Exception as exc:  # never let one bad check abort the report
            findings.append(
                _mk(
                    "internal.check_error",
                    Severity.WARNING,
                    FindingSource.DETERMINISTIC,
                    "document",
                    f"An internal check failed to run ({check.__name__}).",
                    detail=repr(exc),
                    remediation="This is a tooling issue, not a document issue.",
                )
            )
    return findings
