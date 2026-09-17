"""Correspondence PDF Generator

Generates a final PDF for correspondence with content, metadata, and signatures.
Follows the same pattern as memos/pdf_generator.py but with correspondence-specific layout.
"""
import html
import io
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
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

from company_profile.models import Company
from core.storage import storage_service
from correspondence.models import Correspondence, CorrespondenceStatus
from users.models import User
from workflow.models import WorkflowInstance, WorkflowStatus, WorkflowAction, WorkflowStep


def _load_signature_image(sig_path: str, company: Company) -> Optional[Image]:
    try:
        abs_path = storage_service.resolve_path(company, sig_path)
        img = Image(str(abs_path))
        max_w, max_h = 180 * mm, 30 * mm
        img_w, img_h = img.drawWidth, img.drawHeight
        ratio = min(max_w / img_w, max_h / img_h)
        img.drawWidth = img_w * ratio
        img.drawHeight = img_h * ratio
        return img
    except Exception:
        return None


def _apply_inline_formatting(text: str) -> str:
    """Convert HTML inline tags to ReportLab-compatible XML."""
    import re
    text = re.sub(r'<strong[^>]*>(.*?)</strong>', r'<b>\1</b>', text, flags=re.DOTALL)
    text = re.sub(r'<em[^>]*>(.*?)</em>', r'<i>\1</i>', text, flags=re.DOTALL)
    text = re.sub(r'<b[^>]*>(.*?)</b>', r'<b>\1</b>', text, flags=re.DOTALL)
    text = re.sub(r'<i[^>]*>(.*?)</i>', r'<i>\1</i>', text, flags=re.DOTALL)
    text = re.sub(r'<u[^>]*>(.*?)</u>', r'<u>\1</u>', text, flags=re.DOTALL)
    text = re.sub(r'<s[^>]*>(.*?)</s>', r'<strike>\1</strike>', text, flags=re.DOTALL)
    text = re.sub(r'<code[^>]*>(.*?)</code>', r'<font face="Courier" size="9">\1</font>', text, flags=re.DOTALL)
    text = re.sub(r'<a[^>]*>(.*?)</a>', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'<img[^>]*/?>', '', text)
    return text


def _sanitize_for_reportlab(text: str) -> str:
    import re
    text = re.sub(r'<([a-z]+)[^>]*>\s*</\1>', '', text)
    text = re.sub(r'<font[^>]*>\s*</font>', '', text)
    return text


class _HTMLToReportLabParser:
    """Convert correspondence body HTML into ReportLab flowables."""

    def __init__(self, body_style, heading_style, code_style):
        self.body_style = body_style
        self.heading_style = heading_style
        self.code_style = code_style
        self.flowables = []
        self._current_text = []

    def _flush_text(self):
        if self._current_text:
            raw = " ".join(self._current_text)
            raw = _apply_inline_formatting(raw)
            raw = _sanitize_for_reportlab(raw)
            if raw.strip():
                try:
                    self.flowables.append(Paragraph(raw, self.body_style))
                except Exception:
                    safe = raw.replace("<", "&lt;").replace(">", "&gt;")
                    self.flowables.append(Paragraph(safe, self.body_style))
            self._current_text = []

    def parse(self, html_content: str) -> list:
        from html.parser import HTMLParser

        class _Parser(HTMLParser):
            def __init__(self, outer):
                super().__init__()
                self.outer = outer

            def handle_starttag(self, tag, attrs):
                if tag in ('p', 'br'):
                    self.outer._flush_text()
                elif tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                    self.outer._flush_text()
                elif tag == 'li':
                    self.outer._current_text.append('• ')

            def handle_endtag(self, tag):
                if tag in ('p', 'div', 'blockquote'):
                    self.outer._flush_text()
                elif tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                    self.outer._flush_text()
                elif tag == 'li':
                    self.outer._flush_text()

            def handle_data(self, data):
                text = data.strip()
                if text:
                    self.outer._current_text.append(text)

        p = _Parser(self)
        p.feed(html_content)
        self._flush_text()
        return self.flowables


def generate_correspondence_pdf(
    session,
    correspondence: Correspondence,
    current_user: User,
) -> Path:
    from sqlmodel import select

    company = session.get(Company, correspondence.company_id)
    if not company:
        raise ValueError("Company not found")

    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        'CorrespondenceBody',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        spaceAfter=6,
    )
    heading_style = ParagraphStyle(
        'CorrespondenceHeading',
        parent=styles['Heading1'],
        fontSize=14,
        leading=18,
        spaceAfter=8,
    )
    code_style = ParagraphStyle(
        'CorrespondenceCode',
        parent=styles['Code'],
        fontSize=8,
        leading=10,
        spaceAfter=6,
    )
    small_style = ParagraphStyle(
        'CorrespondenceSmall',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=colors.grey,
    )

    # Build PDF in memory
    buffer = io.BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
    )
    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height,
        id='normal',
    )
    doc.addPageTemplates([PageTemplate(id='correspondence', frames=frame)])

    story = []

    # Header
    story.append(Paragraph(
        f"<b>{html.escape(company.full_name or company.short_name)}</b>",
        ParagraphStyle('Header', parent=styles['Title'], fontSize=16, alignment=1),
    ))
    story.append(Spacer(1, 4))

    # Reference & metadata table
    meta_data = [
        ["Reference:", correspondence.reference_number, "Direction:", correspondence.direction.value.upper()],
        ["Date:", correspondence.created_at.strftime("%d %b %Y"), "Priority:", correspondence.priority.value.title()],
        ["Status:", correspondence.status.value.replace("_", " ").title(), "", ""],
    ]
    meta_table = Table(meta_data, colWidths=[80, 150, 70, 120])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#475569')),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#475569')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8))

    # Sender/Recipient
    if correspondence.sender_name or correspondence.recipient_name:
        sr_data = []
        if correspondence.sender_name:
            sr_data.append(["From:", f"{correspondence.sender_name} ({correspondence.sender_organization or ''})"])
        if correspondence.recipient_name:
            sr_data.append(["To:", f"{correspondence.recipient_name} ({correspondence.recipient_organization or ''})"])
        if sr_data:
            sr_table = Table(sr_data, colWidths=[50, 400])
            sr_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            story.append(sr_table)
            story.append(Spacer(1, 8))

    # Subject
    story.append(Paragraph(f"<b>Subject:</b> {html.escape(correspondence.subject)}", body_style))
    story.append(Spacer(1, 8))

    # Horizontal rule
    story.append(Table([['']], colWidths=[doc.width], rowHeights=[1]))
    story.append(Spacer(1, 8))

    # Body
    if correspondence.body:
        parser = _HTMLToReportLabParser(body_style, heading_style, code_style)
        body_flowables = parser.parse(correspondence.body)
        story.extend(body_flowables)
    else:
        story.append(Paragraph("<i>No body content</i>", body_style))

    story.append(Spacer(1, 12))

    # Approvals / Signatures
    if correspondence.workflow_instance_id:
        instance = session.get(WorkflowInstance, correspondence.workflow_instance_id)
        if instance:
            story.append(Paragraph("<b>Approvals</b>", heading_style))

            # Author signature
            if correspondence.author_signature_id:
                from workflow.models import Signature
                sig = session.get(Signature, correspondence.author_signature_id)
                if sig:
                    sig_img = _load_signature_image(sig.file_path, company)
                    if sig_img:
                        story.append(Paragraph("Author Signature:", small_style))
                        story.append(sig_img)
                        story.append(Spacer(1, 6))

            # Workflow actions
            actions = session.exec(
                select(WorkflowAction)
                .where(WorkflowAction.workflow_instance_id == instance.id)
                .order_by(WorkflowAction.acted_at)
            ).all()

            for action in actions:
                step = session.get(WorkflowStep, action.workflow_step_id)
                step_name = step.step_name if step else f"Step {action.workflow_step_order}"
                acted_by_user = session.get(User, action.acted_by)
                acted_by_name = acted_by_user.full_name if acted_by_user else f"User {action.acted_by}"

                action_text = f"{step_name} — {action.action.value.title()} by {acted_by_name}"
                if action.acted_at:
                    action_text += f" ({action.acted_at.strftime('%d %b %Y %H:%M')})"
                story.append(Paragraph(action_text, small_style))

                # Action signature
                if action.signature_id:
                    from workflow.models import Signature
                    sig = session.get(Signature, action.signature_id)
                    if sig:
                        sig_img = _load_signature_image(sig.file_path, company)
                        if sig_img:
                            story.append(sig_img)
                            story.append(Spacer(1, 4))

                if action.remarks:
                    story.append(Paragraph(f"  Note: {html.escape(action.remarks)}", small_style))
                story.append(Spacer(1, 4))

            # Status
            story.append(Paragraph(
                f"<b>Final Status:</b> {instance.status.value.replace('_', ' ').title()}",
                small_style,
            ))

    # Dispatch info
    if correspondence.dispatch_method:
        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Dispatch Information</b>", heading_style))
        dispatch_data = [
            ["Method:", correspondence.dispatch_method.value.title()],
            ["Date:", correspondence.dispatched_at.strftime("%d %b %Y %H:%M") if correspondence.dispatched_at else "—"],
            ["Reference:", correspondence.dispatch_reference or "—"],
        ]
        dispatch_table = Table(dispatch_data, colWidths=[80, 370])
        dispatch_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(dispatch_table)

    # Footer callback
    def footer_callback(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(
            A4[0] / 2, 1.5 * cm,
            f"Document Management System — Correspondence — Generated {datetime.utcnow().strftime('%d %b %Y %H:%M')}"
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=footer_callback, onLaterPages=footer_callback)

    # Save PDF to correspondence storage
    pdf_bytes = buffer.getvalue()
    buffer.close()

    user_dir = storage_service.get_correspondence_root(company) / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = user_dir / f"{correspondence.reference_number}_final.pdf"
    pdf_path.write_bytes(pdf_bytes)

    return pdf_path
