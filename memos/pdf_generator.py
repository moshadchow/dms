"""
memos/pdf_generator.py
──────────────────────
Generates a PDF document containing the memo content with embedded
signatures from the maker and all approvers in workflow order.

Uses reportlab for PDF generation.
"""

from __future__ import annotations

import re
import tempfile
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from core.config import settings


# ──────────────────────────────────────────────
# XML sanitizer for reportlab
# ──────────────────────────────────────────────

def _sanitize_for_reportlab(text: str) -> str:
    """Remove any malformed XML tags that could break reportlab's parser.

    This is a safety net to catch edge cases in markdown-to-XML conversion.
    """
    # Remove empty tags
    text = re.sub(r"<([a-zA-Z]+)>\s*</\1>", "", text)
    # Remove tags with only whitespace
    text = re.sub(r"<([a-zA-Z]+)>\s+</\1>", "", text)
    # Fix mismatched nesting: <b><i></b> -> <b></b>
    text = re.sub(r"<([a-zA-Z]+)><([a-zA-Z]+)></\1>", r"<\1></\1>", text)
    # Remove any remaining orphaned closing tags that don't match
    # This is a last resort - just strip any tag-like content that's not valid
    return text


# ──────────────────────────────────────────────
# Styles
# ──────────────────────────────────────────────

def _build_styles():
    """Create custom paragraph styles for the memo PDF."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="MemoTitle",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        spaceAfter=6,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1e293b"),
    ))

    styles.add(ParagraphStyle(
        name="MemoSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=2,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#64748b"),
    ))

    styles.add(ParagraphStyle(
        name="SectionHeader",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        spaceBefore=16,
        spaceAfter=8,
        textColor=colors.HexColor("#1e293b"),
        borderWidth=0,
        borderPadding=0,
    ))

    styles.add(ParagraphStyle(
        name="BodyText2",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=6,
        textColor=colors.HexColor("#334155"),
    ))

    styles.add(ParagraphStyle(
        name="SignatureLabel",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        spaceBefore=4,
        spaceAfter=2,
        textColor=colors.HexColor("#475569"),
        fontName="Helvetica-Bold",
    ))

    styles.add(ParagraphStyle(
        name="SignatureInfo",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        spaceAfter=2,
        textColor=colors.HexColor("#64748b"),
    ))

    styles.add(ParagraphStyle(
        name="ApprovalInfo",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        spaceAfter=4,
        textColor=colors.HexColor("#475569"),
    ))

    styles.add(ParagraphStyle(
        name="FooterText",
        parent=styles["Normal"],
        fontSize=7,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#94a3b8"),
    ))

    return styles


# ──────────────────────────────────────────────
# Markdown helpers
# ──────────────────────────────────────────────

def _strip_markdown(body: str) -> str:
    """Convert markdown body to plain text with basic formatting preserved."""
    text = body

    # Remove fenced code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)

    # Remove inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Remove bold/italic markers
    text = text.replace("**", "").replace("*", "").replace("__", "").replace("_", "")

    # Remove blockquote markers
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)

    # Remove heading markers but keep text
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Remove link markup but keep text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Remove image markup
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"[Image: \1]", text)

    # Clean up multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def _markdown_to_paragraphs(body: str, styles) -> List:
    """Convert markdown body to a list of reportlab Paragraph objects."""
    paragraphs = []
    lines = body.split("\n")
    in_code_block = False
    code_lines = []

    for line in lines:
        # Fenced code block toggle
        if line.strip().startswith("```"):
            if in_code_block:
                # End of code block
                code_text = "<br/>".join(code_lines)
                code_text = code_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                paragraphs.append(Paragraph(
                    f'<font face="Courier" size="8" color="#334155">{code_text}</font>',
                    styles["BodyText2"],
                ))
                paragraphs.append(Spacer(1, 6))
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        stripped = line.strip()

        # Empty line
        if not stripped:
            paragraphs.append(Spacer(1, 4))
            continue

        # Heading
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2)
            text = _escape_xml(text)
            if level <= 2:
                paragraphs.append(Paragraph(text, styles["SectionHeader"]))
            else:
                paragraphs.append(Paragraph(f"<b>{text}</b>", styles["BodyText2"]))
            continue

        # Blockquote
        if stripped.startswith(">"):
            text = stripped.lstrip("> ").strip()
            text = _escape_xml(text)
            paragraphs.append(Paragraph(
                f'<i>{text}</i>',
                ParagraphStyle(
                    "Quote",
                    parent=styles["BodyText2"],
                    leftIndent=20,
                    textColor=colors.HexColor("#64748b"),
                ),
            ))
            continue

        # Unordered list
        list_match = re.match(r"^[-*+]\s+(.+)$", stripped)
        if list_match:
            text = list_match.group(1)
            text = _escape_xml(text)
            paragraphs.append(Paragraph(f"\u2022  {text}", styles["BodyText2"]))
            continue

        # Ordered list
        ol_match = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        if ol_match:
            text = ol_match.group(1)
            text = _escape_xml(text)
            paragraphs.append(Paragraph(f"\u2022  {text}", styles["BodyText2"]))
            continue

        # Horizontal rule
        if re.match(r"^[-*_]{3,}$", stripped):
            paragraphs.append(Spacer(1, 4))
            continue

        # Regular paragraph - apply inline formatting
        text = _apply_inline_formatting(stripped)
        text = _sanitize_for_reportlab(text)
        paragraphs.append(Paragraph(text, styles["BodyText2"]))

    return paragraphs


def _escape_xml(text: str) -> str:
    """Escape XML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _apply_inline_formatting(text: str) -> str:
    """Convert markdown inline formatting to reportlab XML markup.

    Uses a safe approach: escape XML, strip formatting markers, and
    only apply bold for clearly-delimited cases. Avoids complex nesting
    that can produce malformed XML for reportlab's parser.
    """
    # Escape XML first
    text = _escape_xml(text)

    # Bold: **text** or __text__ (only if non-empty content between markers)
    # Use a placeholder approach to avoid re-matching
    bold_parts = []
    remaining = text
    for pattern in [r"\*\*(.+?)\*\*", r"__(.+?)__"]:
        parts = re.split(pattern, remaining)
        result = []
        is_content = False
        for part in parts:
            if is_content:
                if part.strip():
                    result.append(f"<b>{part}</b>")
                else:
                    result.append(part)
            else:
                result.append(part)
            is_content = not is_content
        remaining = "".join(result)
    text = remaining

    # Inline code: `text` (apply before italic to avoid conflicts)
    text = re.sub(
        r"`([^`]+)`",
        r'<font face="Courier" size="8" color="#e11d48">\1</font>',
        text,
    )

    # Strip remaining italic markers (*text* and _text_) to plain text
    # This avoids complex XML nesting issues with reportlab
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", text)

    # Links: [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    return text


# ──────────────────────────────────────────────
# Signature image helper
# ──────────────────────────────────────────────

def _load_signature_image(file_path: Path, max_width: float, max_height: float) -> Optional[Image]:
    """Load a signature image from disk and return a reportlab Image flowable.

    Returns None if the file doesn't exist or can't be loaded.
    """
    if not file_path.exists():
        return None

    try:
        img = Image(str(file_path))

        # Calculate aspect-preserving dimensions
        img_width, img_height = img.drawWidth, img.drawHeight
        if img_width <= 0 or img_height <= 0:
            return None

        aspect = img_width / img_height

        # Scale to fit within max dimensions
        if img_width > max_width:
            img_width = max_width
            img_height = img_width / aspect

        if img_height > max_height:
            img_height = max_height
            img_width = img_height * aspect

        img.drawWidth = img_width
        img.drawHeight = img_height

        return img
    except Exception:
        return None


# ──────────────────────────────────────────────
# Main PDF generation
# ──────────────────────────────────────────────

def generate_memo_pdf(
    *,
    memo_subject: str,
    memo_body: str,
    memo_date: str,
    author_name: str,
    author_signature_path: Optional[Path],
    workflow_name: str,
    approval_entries: List[dict],
    output_path: Path,
) -> Path:
    """Generate a PDF document for the final approved memo.

    Args:
        memo_subject: The memo subject/title.
        memo_body: The memo body in markdown format.
        memo_date: Formatted date string for the memo.
        author_name: Name of the memo author (Maker).
        author_signature_path: Path to the maker's signature image (or None).
        workflow_name: Name of the workflow definition.
        approval_entries: List of approval entries, each a dict with keys:
            - step_name (str)
            - acted_by_name (str)
            - action (str): "approve", "reject", "return", etc.
            - signature_path (Optional[Path])
            - acted_at (str): Formatted datetime string
        output_path: Where to write the generated PDF.

    Returns:
        The output_path on success.
    """
    styles = _build_styles()
    page_width, page_height = A4

    # Build the document
    doc = BaseDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id="main",
    )

    # Footer function
    def add_footer(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.setFillColor(colors.HexColor("#94a3b8"))
        canvas_obj.drawCentredString(
            page_width / 2,
            12 * mm,
            f"Document Management System - Final Draft - Generated {memo_date}",
        )
        canvas_obj.restoreState()

    template = PageTemplate(
        id="main",
        frames=[frame],
        onPage=add_footer,
    )
    doc.addPageTemplates([template])

    story = []

    # ── Title ──
    story.append(Paragraph("MEMO", styles["MemoTitle"]))
    story.append(Spacer(1, 4))

    # ── Metadata table ──
    meta_data = [
        ["Subject:", memo_subject],
        ["Date:", memo_date],
        ["Author:", author_name],
        ["Workflow:", workflow_name],
        ["Status:", "APPROVED"],
    ]

    meta_table = Table(meta_data, colWidths=[80, doc.width - 80])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#64748b")),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1e293b")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # ── Horizontal rule ──
    hr_table = Table([[""]], colWidths=[doc.width])
    hr_table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
    ]))
    story.append(hr_table)
    story.append(Spacer(1, 12))

    # ── Body content ──
    story.append(Paragraph("CONTENT", styles["SectionHeader"]))
    body_paragraphs = _markdown_to_paragraphs(memo_body, styles)
    story.extend(body_paragraphs)
    story.append(Spacer(1, 20))

    # ── Signatures section ──
    story.append(Paragraph("SIGNATURES", styles["SectionHeader"]))

    # Maker's signature
    story.append(Paragraph("Maker", styles["SignatureLabel"]))
    story.append(Paragraph(author_name, styles["SignatureInfo"]))

    if author_signature_path and author_signature_path.exists():
        img = _load_signature_image(author_signature_path, max_width=180, max_height=80)
        if img:
            story.append(img)
        else:
            story.append(Paragraph("[Signature image unavailable]", styles["SignatureInfo"]))
    else:
        story.append(Paragraph("[No signature on file]", styles["SignatureInfo"]))

    story.append(Spacer(1, 12))

    # Approver signatures
    for entry in approval_entries:
        step_name = entry.get("step_name", "Unknown Step")
        acted_by_name = entry.get("acted_by_name", "Unknown")
        action = entry.get("action", "unknown")
        sig_path = entry.get("signature_path")
        acted_at = entry.get("acted_at", "")

        # Label
        action_display = action.upper() if action else "UNKNOWN"
        story.append(Paragraph(
            f"Step: {step_name} - {action_display}",
            styles["SignatureLabel"],
        ))
        story.append(Paragraph(
            f"{acted_by_name} | {acted_at}",
            styles["SignatureInfo"],
        ))

        if sig_path and sig_path.exists():
            img = _load_signature_image(sig_path, max_width=180, max_height=80)
            if img:
                story.append(img)
            else:
                story.append(Paragraph("[Signature image unavailable]", styles["SignatureInfo"]))
        else:
            story.append(Paragraph("[No signature on file]", styles["SignatureInfo"]))

        story.append(Spacer(1, 8))

    # ── Approval summary table ──
    story.append(Spacer(1, 12))
    story.append(Paragraph("APPROVAL INFORMATION", styles["SectionHeader"]))

    summary_data = [
        ["Workflow", workflow_name],
        ["Final Status", "APPROVED"],
        ["Total Steps", str(len(approval_entries))],
    ]

    # Find the latest approval date
    if approval_entries:
        latest_date = max(e.get("acted_at", "") for e in approval_entries)
        summary_data.append(["Completed", latest_date])

    summary_table = Table(summary_data, colWidths=[100, doc.width - 100])
    summary_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#64748b")),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1e293b")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(summary_table)

    # Build the PDF
    doc.build(story)

    return output_path
