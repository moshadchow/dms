import html
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import bleach
from fastapi import HTTPException, status
from sqlmodel import Session, select

from audit.models import AuditAction, AuditModule
from audit.service import AuditService
from core.access import ensure_directory_access, ensure_document_access, ensure_document_user_level_access
from core.config import settings
from documents.models import Document, DocumentStatus, DocumentUserLevelLink, FileType
from memos.models import Memo, MemoAttachment, MemoDetailRead, MemoListResponse, MemoRead
from memos.schemas import MemoCreate, MemoSubmit, MemoUpdate
from user_levels.models import UserLevel
from users.models import User
from workflow.models import WorkflowInstance, WorkflowStatus, WorkflowStep


# ──────────────────────────────────────────────
# Markdown-style → HTML renderer (stdlib only)
# ──────────────────────────────────────────────

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_UNORDERED_RE = re.compile(r"^\s*[-*+]\s+(.*)$")
_ORDERED_RE = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_BLOCKQUOTE_RE = re.compile(r"^\s*>\s?(.*)$")


def render_markdown(body: str) -> str:
    """Convert a limited markdown-style body to an HTML fragment.

    Supports: headings, bold/italic, inline code, fenced code blocks,
    unordered/ordered lists, blockquotes, and links. All text is HTML-escaped.
    """
    if not body:
        return "<p></p>"

    lines = body.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0

    def inline(text: str) -> str:
        # Code spans first (do not process formatting inside)
        text = re.sub(
            r"`([^`]+)`",
            lambda m: f"<code>{html.escape(m.group(1))}</code>",
            text,
        )
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", text)
        text = re.sub(
            r"\[([^\]]+)\]\(([^)\s]+)\)",
            lambda m: f'<a href="{html.escape(m.group(2), quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(m.group(1))}</a>',
            text,
        )
        return text

    def para(text: str) -> str:
        return f"<p>{inline(html.escape(text))}</p>"

    while i < len(lines):
        line = lines[i]

        # Fenced code block
        if line.strip().startswith("```"):
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            out.append(
                "<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>"
            )
            continue

        # Heading
        m = _HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(html.escape(m.group(2).strip()))}</h{level}>")
            i += 1
            continue

        # Blockquote
        m = _BLOCKQUOTE_RE.match(line)
        if m:
            quote_lines: list[str] = []
            while i < len(lines):
                qm = _BLOCKQUOTE_RE.match(lines[i])
                if not qm:
                    break
                quote_lines.append(qm.group(1))
                i += 1
            inner = " ".join(html.escape(x.strip()) for x in quote_lines)
            out.append(f"<blockquote>{inline(inner)}</blockquote>")
            continue

        # Unordered list
        m = _UNORDERED_RE.match(line)
        if m:
            items: list[str] = []
            while i < len(lines):
                lm = _UNORDERED_RE.match(lines[i])
                if not lm:
                    break
                items.append(inline(html.escape(lm.group(1).strip())))
                i += 1
            out.append("<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>")
            continue

        # Ordered list
        m = _ORDERED_RE.match(line)
        if m:
            items: list[str] = []
            while i < len(lines):
                lm = _ORDERED_RE.match(lines[i])
                if not lm:
                    break
                items.append(inline(html.escape(lm.group(1).strip())))
                i += 1
            out.append("<ol>" + "".join(f"<li>{item}</li>" for item in items) + "</ol>")
            continue

        # Blank line → paragraph break
        if not line.strip():
            i += 1
            continue

        # Normal paragraph (accumulate consecutive non-blank lines)
        para_lines: list[str] = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not _HEADING_RE.match(lines[i]):
            para_lines.append(lines[i])
            i += 1
        out.append(para(" ".join(x.strip() for x in para_lines)))

    return "\n".join(out) or "<p></p>"


# ──────────────────────────────────────────────
# HTML sanitization for memo body content
# ──────────────────────────────────────────────

ALLOWED_TAGS = [
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr",
    "strong", "b", "em", "i", "u", "s", "strike", "del",
    "code", "pre", "blockquote",
    "ul", "ol", "li",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
    "div", "span", "font",
]

ALLOWED_ATTRS = {
    "*": ["class", "style", "title"],
    "a": ["href", "target", "rel"],
    "img": ["src", "alt", "width", "height"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
    "font": ["color", "size", "face"],
}


def sanitize_memo_html(body: str) -> str:
    """Sanitize HTML body content for safe storage and rendering.

    Strips dangerous tags (script, iframe, object, etc.) and unsafe attributes.
    Uses bleach for production-grade sanitization.
    """
    if not body:
        return ""
    return bleach.clean(
        body,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        strip=True,
    )


def build_memo_html(subject: str, body: str) -> str:
    """Build a standalone HTML document from a memo's subject + HTML body.

    The body parameter is expected to be pre-sanitized HTML content.
    """
    escaped_subject = html.escape(subject)
    return (
        "<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>{escaped_subject}</title>"
        "<style>body{font-family:Segoe UI,Arial,sans-serif;max-width:760px;"
        "margin:2rem auto;padding:0 1.5rem;line-height:1.6;color:#1e293b}"
        "h1,h2,h3{line-height:1.25}code{background:#f1f5f9;padding:1px 5px;"
        "border-radius:4px;font-size:0.9em}pre{background:#f8fafc;padding:1rem;"
        "border:1px solid #e2e8f0;border-radius:8px;overflow-x:auto}"
        "blockquote{border-left:4px solid #cbd5e1;margin:1rem 0;padding-left:1rem;"
        "color:#64748b}table{border-collapse:collapse}td,th{border:1px solid #e2e8f0;"
        "padding:6px 10px}</style></head><body>"
        f"<h1>{escaped_subject}</h1>"
        f"{body}"
        "</body></html>"
    )


# ──────────────────────────────────────────────
# Memo Service
# ──────────────────────────────────────────────

class MemoService:
    def __init__(self, session: Session):
        self.session = session

    # ──────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────

    def _get_memo_or_404(self, memo_id: int) -> Memo:
        memo = self.session.get(Memo, memo_id)
        if not memo:
            raise HTTPException(status_code=404, detail=f"Memo {memo_id} not found")
        return memo

    def _get_workflow_status(self, document_id: int) -> Optional[str]:
        instance = self.session.exec(
            select(WorkflowInstance)
            .where(WorkflowInstance.document_id == document_id)
            .order_by(WorkflowInstance.submitted_at.desc())
        ).first()
        return instance.status.value if instance else None

    def _get_current_step(self, memo: Memo) -> Optional[WorkflowStep]:
        instance = self.session.exec(
            select(WorkflowInstance)
            .where(
                WorkflowInstance.document_id == memo.document_id,
                WorkflowInstance.status.in_([
                    WorkflowStatus.SUBMITTED,
                    WorkflowStatus.PENDING_APPROVAL,
                    WorkflowStatus.RETURNED,
                ]),
            )
            .order_by(WorkflowInstance.submitted_at.desc())
        ).first()
        if not instance:
            return None
        return self.session.exec(
            select(WorkflowStep).where(
                WorkflowStep.workflow_definition_id == instance.workflow_definition_id,
                WorkflowStep.step_order == instance.current_step_order,
            )
        ).first()

    def _is_eligible_approver(self, memo: Memo, user: User) -> bool:
        step = self._get_current_step(memo)
        if not step or not memo.document:
            return False
        from workflow.service import WorkflowInstanceService
        svc = WorkflowInstanceService(self.session)
        return user.id in svc._resolve_eligible_user_ids(step, memo.document)

    def _check_view_access(self, memo: Memo, user: User) -> None:
        if user.is_admin() or memo.created_by == user.id:
            return
        ensure_document_access(self.session, user, memo.document_id)
        ensure_document_user_level_access(self.session, user, memo.document)
        if self._is_eligible_approver(memo, user):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this memo",
        )

    def _check_edit_access(self, memo: Memo, user: User) -> None:
        if user.is_admin() or memo.created_by == user.id:
            return
        if not self._is_eligible_approver(memo, user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the author or an eligible approver can edit this memo",
            )

    def _check_author(self, memo: Memo, user: User) -> None:
        if not user.is_admin() and memo.created_by != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the memo author can perform this action",
            )

    def _save_memo_html(self, memo: Memo, user: User) -> str:
        """Write the generated HTML backing file, return relative storage path."""
        storage_root = Path(settings.STORAGE_ROOT)
        dest_dir = storage_root / "memos" / str(user.id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / f"{uuid.uuid4().hex}.html"
        dest_path.write_text(build_memo_html(memo.subject, memo.body), encoding="utf-8")
        return str(dest_path.relative_to(storage_root))

    def _validate_user_levels(self, user_level_ids: list[int]) -> set[int]:
        if not user_level_ids:
            raise HTTPException(
                status_code=422,
                detail="At least one user level must be selected for memo visibility",
            )
        valid = self.session.exec(
            select(UserLevel).where(
                UserLevel.id.in_(user_level_ids),
                UserLevel.is_active == True,
            )
        ).all()
        valid_ids = {ul.id for ul in valid}
        invalid = set(user_level_ids) - valid_ids
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid or inactive user level IDs: {sorted(invalid)}",
            )
        return valid_ids

    def _sync_attachments(self, memo: Memo, document_ids: list[int], user: User) -> None:
        # Remove existing links
        for link in list(memo.attachments):
            self.session.delete(link)
        for doc_id in document_ids:
            doc = ensure_document_access(self.session, user, doc_id)
            ensure_document_user_level_access(self.session, user, doc)
            self.session.add(MemoAttachment(memo_id=memo.id, document_id=doc_id))
        self.session.flush()
        self.session.expire(memo, ["attachments"])

    def _to_read(self, memo: Memo) -> MemoRead:
        return MemoRead(
            id=memo.id,
            document_id=memo.document_id,
            memo_date=memo.memo_date,
            subject=memo.subject,
            body=memo.body,
            author_signature_id=memo.author_signature_id,
            created_by=memo.created_by,
            created_by_name=memo.author.full_name if memo.author else None,
            created_at=memo.created_at,
            updated_at=memo.updated_at,
            workflow_status=self._get_workflow_status(memo.document_id),
        )

    def _to_detail(self, memo: Memo) -> MemoDetailRead:
        read = self._to_read(memo)
        doc = memo.document
        attachments = []
        for link in memo.attachments:
            att_doc = link.document
            attachments.append(
                {
                    "id": link.id,
                    "memo_id": memo.id,
                    "document_id": link.document_id,
                    "document_title": att_doc.title if att_doc else None,
                    "file_name": att_doc.file_name if att_doc else None,
                    "file_type": att_doc.file_type.value if att_doc and att_doc.file_type else None,
                    "mime_type": att_doc.mime_type if att_doc else None,
                    "file_size": att_doc.file_size if att_doc else None,
                    "created_at": link.created_at,
                }
            )
        user_level_ids = [
            ulink.user_level_id
            for ulink in self.session.exec(
                select(DocumentUserLevelLink).where(
                    DocumentUserLevelLink.document_id == memo.document_id
                )
            ).all()
        ]
        return MemoDetailRead(
            **read.model_dump(),
            directory_id=memo.document.directory_id if doc else None,
            document_title=doc.title if doc else None,
            file_name=doc.file_name if doc else None,
            file_type=doc.file_type.value if doc and doc.file_type else None,
            mime_type=doc.mime_type if doc else None,
            file_size=doc.file_size if doc else None,
            attachments=attachments,
            user_level_ids=user_level_ids,
        )

    def _log_audit(
        self,
        action: AuditAction,
        memo: Memo,
        description: str,
        user: User,
        *,
        old_value: Optional[dict] = None,
        new_value: Optional[dict] = None,
    ) -> None:
        try:
            svc = AuditService(self.session)
            svc.log_event(
                action=action,
                module=AuditModule.DOCUMENTS,
                entity_name="memo",
                entity_id=str(memo.id),
                old_value=old_value,
                new_value=new_value,
                description=description,
                is_success=True,
                user=user,
            )
        except Exception:
            pass

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def create_draft(self, data: MemoCreate, current_user: User) -> MemoDetailRead:
        directory = ensure_directory_access(self.session, current_user, data.directory_id)
        valid_level_ids = self._validate_user_levels(data.user_level_ids)

        memo_date = data.memo_date or datetime.utcnow()

        # Placeholder memo for file-path building
        memo = Memo(
            document_id=0,
            memo_date=memo_date,
            subject=data.subject,
            body=sanitize_memo_html(data.body),
            created_by=current_user.id,
        )

        # Build backing document
        storage_path = self._save_memo_html(memo, current_user)
        doc = Document(
            title=data.subject,
            description=f"Memo: {data.subject}",
            directory_id=data.directory_id,
            uploaded_by=current_user.id,
            file_name=f"{data.subject}.html",
            file_type=FileType.HTML,
            mime_type="text/html",
            file_size=Path(settings.STORAGE_ROOT).joinpath(storage_path).stat().st_size,
            storage_path=storage_path,
            status=DocumentStatus.ACTIVE,
        )
        self.session.add(doc)
        self.session.flush()

        for level_id in valid_level_ids:
            self.session.add(DocumentUserLevelLink(document_id=doc.id, user_level_id=level_id))

        memo.document_id = doc.id
        self.session.add(memo)
        self.session.flush()

        self._sync_attachments(memo, data.attachment_document_ids, current_user)

        self.session.commit()
        self.session.refresh(memo)

        self._log_audit(
            AuditAction.CREATE_MEMO,
            memo,
            f"Created memo '{memo.subject}'",
            current_user,
            new_value={"subject": memo.subject, "document_id": memo.document_id},
        )

        # Reload for eager relationships
        memo = self._get_memo_or_404(memo.id)
        return self._to_detail(memo)

    def get_memo(self, memo_id: int, current_user: User) -> MemoDetailRead:
        memo = self._get_memo_or_404(memo_id)
        self._check_view_access(memo, current_user)
        return self._to_detail(memo)

    def get_by_document(self, document_id: int, current_user: User) -> MemoDetailRead:
        memo = self.session.exec(
            select(Memo).where(Memo.document_id == document_id)
        ).first()
        if not memo:
            raise HTTPException(status_code=404, detail=f"No memo found for document {document_id}")
        self._check_view_access(memo, current_user)
        return self._to_detail(memo)

    def list_memos(
        self,
        current_user: User,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> MemoListResponse:
        query = select(Memo)
        if not current_user.is_admin():
            query = query.where(Memo.created_by == current_user.id)

        all_memos = self.session.exec(query).all()
        total = len(all_memos)
        page_memos = self.session.exec(
            query.order_by(Memo.created_at.desc()).offset(skip).limit(limit)
        ).all()

        return MemoListResponse(
            total=total,
            page=skip // limit + 1,
            limit=limit,
            items=[self._to_read(m) for m in page_memos],
        )

    def update_memo(self, memo_id: int, data: MemoUpdate, current_user: User) -> MemoDetailRead:
        memo = self._get_memo_or_404(memo_id)
        self._check_edit_access(memo, current_user)

        old_values = {
            "subject": memo.subject,
            "body": memo.body,
        }

        if data.subject is not None:
            memo.subject = data.subject
        if data.memo_date is not None:
            memo.memo_date = data.memo_date
        if data.body is not None:
            memo.body = sanitize_memo_html(data.body)

        body_changed = data.subject is not None or data.body is not None
        if body_changed:
            storage_root = Path(settings.STORAGE_ROOT)
            old_path = storage_root / memo.document.storage_path
            try:
                old_path.unlink(missing_ok=True)
            except Exception:
                pass
            new_storage_path = self._save_memo_html(memo, current_user)
            memo.document.storage_path = new_storage_path
            memo.document.title = memo.subject
            memo.document.file_name = f"{memo.subject}.html"
            memo.document.file_size = (
                storage_root.joinpath(new_storage_path).stat().st_size
            )

        if data.attachment_document_ids is not None:
            self._sync_attachments(memo, data.attachment_document_ids, current_user)

        if data.user_level_ids is not None:
            valid_level_ids = self._validate_user_levels(data.user_level_ids)
            existing_links = self.session.exec(
                select(DocumentUserLevelLink).where(
                    DocumentUserLevelLink.document_id == memo.document_id
                )
            ).all()
            for link in existing_links:
                self.session.delete(link)
            self.session.flush()
            for level_id in valid_level_ids:
                self.session.add(
                    DocumentUserLevelLink(document_id=memo.document_id, user_level_id=level_id)
                )

        memo.updated_at = datetime.utcnow()
        memo.document.updated_at = datetime.utcnow()
        self.session.add(memo)
        self.session.commit()
        self.session.refresh(memo)

        self._log_audit(
            AuditAction.UPDATE_MEMO,
            memo,
            f"Updated memo '{memo.subject}'",
            current_user,
            old_value=old_values,
            new_value={
                "subject": memo.subject,
            },
        )

        memo = self._get_memo_or_404(memo.id)
        return self._to_detail(memo)

    def submit_memo(self, memo_id: int, data: MemoSubmit, current_user: User) -> MemoDetailRead:
        memo = self._get_memo_or_404(memo_id)
        self._check_author(memo, current_user)

        # Validate signature ownership (if provided)
        if data.signature_id is not None:
            from workflow.service import SignatureService
            sig = SignatureService(self.session).validate_signature_exists(data.signature_id)
            if sig.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only attach your own signatures",
                )
            memo.author_signature_id = data.signature_id

        # Delegate to the existing workflow submission logic
        from workflow.schemas import WorkflowInstanceCreate
        from workflow.service import WorkflowInstanceService
        WorkflowInstanceService(self.session).submit_instance(
            WorkflowInstanceCreate(
                document_id=memo.document_id,
                workflow_definition_id=data.workflow_definition_id,
            ),
            current_user,
        )

        memo.updated_at = datetime.utcnow()
        self.session.add(memo)
        self.session.commit()
        self.session.refresh(memo)

        self._log_audit(
            AuditAction.SUBMIT_MEMO,
            memo,
            f"Submitted memo '{memo.subject}' for approval",
            current_user,
            new_value={
                "workflow_definition_id": data.workflow_definition_id,
                "signature_id": data.signature_id,
            },
        )

        memo = self._get_memo_or_404(memo.id)
        return self._to_detail(memo)

    # ──────────────────────────────────────────
    # Final Draft Download
    # ──────────────────────────────────────────

    def generate_final_draft(self, memo_id: int, current_user: User) -> Path:
        """Generate a PDF with memo content and embedded signatures.

        Validates:
        - Memo exists and user has view access
        - Workflow status is APPROVED

        Returns:
            Path to the generated PDF file.
        """
        memo = self._get_memo_or_404(memo_id)
        self._check_view_access(memo, current_user)

        # Find the approved workflow instance for this memo's document
        approved_instance = self.session.exec(
            select(WorkflowInstance)
            .where(
                WorkflowInstance.document_id == memo.document_id,
                WorkflowInstance.status == WorkflowStatus.APPROVED,
            )
            .order_by(WorkflowInstance.submitted_at.desc())
        ).first()

        if not approved_instance:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Memo has not been approved yet. Final draft is only available after approval.",
            )

        # Get workflow steps in order
        steps = self.session.exec(
            select(WorkflowStep)
            .where(WorkflowStep.workflow_definition_id == approved_instance.workflow_definition_id)
            .order_by(WorkflowStep.step_order)
        ).all()

        # Get all actions for this instance
        from workflow.models import WorkflowAction
        actions = self.session.exec(
            select(WorkflowAction)
            .where(WorkflowAction.workflow_instance_id == approved_instance.id)
        ).all()

        # Build approval entries with signatures
        approval_entries = []
        for action in actions:
            step_name = None
            if action.workflow_step:
                step_name = action.workflow_step.step_name

            signature_path = None
            if action.signature_id:
                from workflow.models import Signature
                sig = self.session.get(Signature, action.signature_id)
                if sig and sig.is_active:
                    signature_path = Path(settings.STORAGE_ROOT) / sig.file_path

            acted_by_name = action.acted_by_user.full_name if action.acted_by_user else f"User #{action.acted_by}"
            acted_at = action.acted_at.strftime("%Y-%m-%d %H:%M") if action.acted_at else ""

            approval_entries.append({
                "step_name": step_name or f"Step {action.workflow_step_id}",
                "acted_by_name": acted_by_name,
                "action": action.action.value if hasattr(action.action, 'value') else str(action.action),
                "signature_path": signature_path,
                "acted_at": acted_at,
            })

        # Sort approval entries by step order
        step_order_map = {step.id: step.step_order for step in steps}
        approval_entries.sort(key=lambda e: step_order_map.get(
            next((a.workflow_step_id for a in actions if a.acted_by == e.get("acted_by")), 0),
            0,
        ))

        # Get maker's signature path
        author_signature_path = None
        if memo.author_signature_id:
            from workflow.models import Signature
            author_sig = self.session.get(Signature, memo.author_signature_id)
            if author_sig and author_sig.is_active:
                author_signature_path = Path(settings.STORAGE_ROOT) / author_sig.file_path

        # Format memo date
        memo_date = memo.memo_date.strftime("%Y-%m-%d") if memo.memo_date else ""

        # Get workflow name
        workflow_name = approved_instance.workflow_definition.name if approved_instance.workflow_definition else "Unknown"

        # Get author name
        author_name = memo.author.full_name if memo.author else f"User #{memo.created_by}"

        # Generate PDF
        from memos.pdf_generator import generate_memo_pdf

        output_dir = Path(settings.STORAGE_ROOT) / "memos" / "final_drafts"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"memo_{memo_id}_final_draft.pdf"

        generate_memo_pdf(
            memo_subject=memo.subject,
            memo_body=memo.body,
            memo_date=memo_date,
            author_name=author_name,
            author_signature_path=author_signature_path,
            workflow_name=workflow_name,
            approval_entries=approval_entries,
            output_path=output_path,
        )

        # Audit log
        self._log_audit(
            AuditAction.DOWNLOAD_FINAL_DRAFT,
            memo,
            f"Downloaded final draft of memo '{memo.subject}'",
            current_user,
        )

        return output_path
