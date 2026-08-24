"""
memos/pdf_generator.py
──────────────────────
Generates a PDF document containing the memo content with embedded
signatures from the maker and all approvers in workflow order.

Uses reportlab for PDF generation and html.parser for HTML-to-ReportLab conversion.
"""

from __future__ import annotations

import re
import tempfile
from html.parser import HTMLParser
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

    This is a safety net to catch edge cases in HTML-to-XML conversion.
    """
    # Remove empty tags
    text = re.sub(r"<([a-zA-Z]+)>\s*</\1>", "", text)
    # Remove tags with only whitespace
    text = re.sub(r"<([a-zA-Z]+)>\s+</\1>", "", text)
    # Fix mismatched nesting: <b><i></b> -> <b></b>
    text = re.sub(r"<([a-zA-Z]+)><([a-zA-Z]+)></\1>", r"<\1></\1>", text)
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

    styles.add(ParagraphStyle(
        name="Blockquote",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        leftIndent=20,
        textColor=colors.HexColor("#64748b"),
        fontName="Helvetica-Oblique",
    ))

    styles.add(ParagraphStyle(
        name="CodeBlock",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        fontName="Courier",
        textColor=colors.HexColor("#334155"),
        backColor=colors.HexColor("#f8fafc"),
        borderWidth=1,
        borderColor=colors.HexColor("#e2e8f0"),
        borderPadding=8,
    ))

    return styles


# ──────────────────────────────────────────────
# HTML-to-ReportLab converter
# ──────────────────────────────────────────────

def _escape_xml(text: str) -> str:
    """Escape XML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _apply_inline_formatting(text: str) -> str:
    """Convert HTML inline tags to ReportLab XML markup.

    The input text may contain HTML tags from the sanitized memo body.
    We convert supported tags to ReportLab-compatible XML.
    """
    # Escape XML first
    text = _escape_xml(text)

    # Convert HTML inline tags to ReportLab XML
    # Bold: <strong>, <b>
    text = re.sub(r"<strong>(.*?)</strong>", r"<b>\1</b>", text)
    text = re.sub(r"<b>(.*?)</b>", r"<b>\1</b>", text)

    # Italic: <em>, <i>
    text = re.sub(r"<em>(.*?)</em>", r"<i>\1</i>", text)
    text = re.sub(r"<i>(.*?)</i>", r"<i>\1</i>", text)

    # Underline: <u>
    # ReportLab supports <u> tags

    # Strikethrough: <s>, <strike>, <del>
    text = re.sub(r"<s>(.*?)</s>", r"<strike>\1</strike>", text)
    text = re.sub(r"<del>(.*?)</del>", r"<strike>\1</strike>", text)

    # Inline code: <code>
    text = re.sub(
        r"<code>(.*?)</code>",
        r'<font face="Courier" size="8" color="#e11d48">\1</font>',
        text,
    )

    # Links: <a href="url">text</a> -> text (strip URL for PDF)
    text = re.sub(r'<a[^>]*>(.*?)</a>', r"\1", text)

    # Images: <img ...> -> [Image: alt]
    text = re.sub(r'<img[^>]*alt="([^"]*)"[^>]*/?>', r"[Image: \1]", text)
    text = re.sub(r'<img[^>]*/?>', "[Image]", text)

    # Font tags: pass through (already ReportLab compatible)
    # Color: <font color="..."> -> pass through

    return text


class _HTMLToReportLabParser(HTMLParser):
    """Parse HTML body and convert to ReportLab Paragraph flowables."""

    def __init__(self, styles):
        super().__init__()
        self.styles = styles
        self.flowables: list = []
        self._current_text = ""
        self._tag_stack: list[str] = []
        self._in_pre = False
        self._pre_text = ""
        self._in_table = False
        self._table_rows: list[list[str]] = []
        self._current_row: list[str] = []
        self._current_cell = ""
        self._in_blockquote = False
        self._blockquote_text = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        tag = tag.lower()
        self._tag_stack.append(tag)

        if tag == "pre":
            self._flush_text()
            self._in_pre = True
            self._pre_text = ""
        elif tag == "table":
            self._flush_text()
            self._in_table = True
            self._table_rows = []
        elif tag == "tr":
            self._current_row = []
        elif tag in ("td", "th"):
            self._current_cell = ""
        elif tag == "blockquote":
            self._flush_text()
            self._in_blockquote = True
            self._blockquote_text = ""
        elif tag in ("ul", "ol"):
            self._flush_text()
        elif tag == "li":
            self._current_text += "\u2022  "
        elif tag == "br":
            self._current_text += "<br/>"
        elif tag == "hr":
            self._flush_text()
            self.flowables.append(Spacer(1, 4))
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._flush_text()
        elif tag == "p":
            self._flush_text()

    def handle_endtag(self, tag: str):
        tag = tag.lower()

        if tag == "pre" and self._in_pre:
            self._in_pre = False
            code_text = _escape_xml(self._pre_text.strip())
            code_text = code_text.replace("\n", "<br/>")
            if code_text:
                self.flowables.append(Paragraph(
                    f'<font face="Courier" size="8">{code_text}</font>',
                    self.styles["CodeBlock"],
                ))
                self.flowables.append(Spacer(1, 6))
            self._pre_text = ""
        elif tag == "table" and self._in_table:
            self._in_table = False
            self._render_table()
        elif tag == "tr" and self._in_table:
            self._table_rows.append(self._current_row)
        elif tag in ("td", "th") and self._in_table:
            self._current_row.append(self._current_cell.strip())
        elif tag == "blockquote" and self._in_blockquote:
            self._in_blockquote = False
            text = self._blockquote_text.strip()
            if text:
                text = _apply_inline_formatting(text)
                text = _sanitize_for_reportlab(text)
                self.flowables.append(Paragraph(
                    text,
                    self.styles["Blockquote"],
                ))
            self._blockquote_text = ""
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = self._current_text.strip()
            self._current_text = ""
            if text:
                text = _escape_xml(text)
                level = int(tag[1])
                if level <= 2:
                    self.flowables.append(Paragraph(text, self.styles["SectionHeader"]))
                else:
                    self.flowables.append(Paragraph(f"<b>{text}</b>", self.styles["BodyText2"]))
        elif tag == "p":
            text = self._current_text.strip()
            self._current_text = ""
            if text:
                text = _apply_inline_formatting(text)
                text = _sanitize_for_reportlab(text)
                self.flowables.append(Paragraph(text, self.styles["BodyText2"]))
        elif tag in ("ul", "ol"):
            self._flush_text()
        elif tag == "li":
            # List items are handled via the bullet character prefix
            pass

        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()

    def handle_data(self, data: str):
        if self._in_pre:
            self._pre_text += data
        elif self._in_blockquote:
            self._blockquote_text += data
        elif self._in_table:
            self._current_cell += data
        else:
            self._current_text += data

    def _flush_text(self):
        """Flush accumulated text as a paragraph."""
        text = self._current_text.strip()
        self._current_text = ""
        if text:
            text = _apply_inline_formatting(text)
            text = _sanitize_for_reportlab(text)
            self.flowables.append(Paragraph(text, self.styles["BodyText2"]))

    def _render_table(self):
        """Render collected table rows as a ReportLab Table."""
        if not self._table_rows:
            return

        # Sanitize all cell content
        sanitized_rows = []
        for row in self._table_rows:
            sanitized_row = []
            for cell in row:
                cell_text = _apply_inline_formatting(cell)
                cell_text = _sanitize_for_reportlab(cell_text)
                sanitized_row.append(cell_text)
            sanitized_rows.append(sanitized_row)

        if not sanitized_rows:
            return

        # Ensure all rows have the same number of columns
        max_cols = max(len(row) for row in sanitized_rows)
        for row in sanitized_rows:
            while len(row) < max_cols:
                row.append("")

        # Calculate column widths
        available_width = 480  # approximate A4 width minus margins
        col_width = available_width / max_cols if max_cols > 0 else available_width

        try:
            table = Table(sanitized_rows, colWidths=[col_width] * max_cols)
            table.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]))
            self.flowables.append(table)
            self.flowables.append(Spacer(1, 8))
        except Exception:
            # Fallback: render table as text
            for row in sanitized_rows:
                text = " | ".join(row)
                self.flowables.append(Paragraph(text, self.styles["BodyText2"]))


def _html_to_paragraphs(body: str, styles) -> List:
    """Convert HTML body to a list of reportlab Paragraph objects.

    This is the primary conversion function for the new rich-text editor content.
    """
    if not body or not body.strip():
        return [Paragraph("", styles["BodyText2"])]

    parser = _HTMLToReportLabParser(styles)
    try:
        parser.feed(body)
    except Exception:
        # Fallback: treat as plain text
        text = _escape_xml(body)
        text = text.replace("\n", "<br/>")
        return [Paragraph(text, styles["BodyText2"])]

    parser._flush_text()

    return parser.flowables if parser.flowables else [Paragraph("", styles["BodyText2"])]


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
        memo_body: The memo body in HTML format (pre-sanitized).
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
    body_paragraphs = _html_to_paragraphs(memo_body, styles)
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
