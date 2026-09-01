"""
signatures/service.py
─────────────────────
Signature file management: upload, list, get, soft-delete.
Separated from workflow/ since it has no workflow dependencies.
"""

from pathlib import Path
from typing import List
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlmodel import Session, select

from audit.models import AuditAction, AuditModule
from audit.service import AuditService
from core.config import settings
from users.models import User
from workflow.models import Signature, SignatureRead, SignatureType

ALLOWED_SIGNATURE_MIME_TYPES = {"image/jpeg", "image/png"}


class SignatureService:
    def __init__(self, session: Session):
        self.session = session

    def _to_read(self, sig: Signature) -> SignatureRead:
        return SignatureRead(
            id=sig.id,
            user_id=sig.user_id,
            file_name=sig.file_name,
            file_path=sig.file_path,
            mime_type=sig.mime_type,
            file_size=sig.file_size,
            sig_type=sig.sig_type,
            is_active=sig.is_active,
            created_at=sig.created_at,
            updated_at=sig.updated_at,
        )

    def _log_audit(
        self,
        action: AuditAction,
        signature: Signature,
        description: str,
    ) -> None:
        try:
            svc = AuditService(self.session)
            svc.log_event(
                action=action,
                module=AuditModule.WORKFLOW,
                entity_name="signature",
                entity_id=str(signature.id),
                new_value={
                    "sig_type": signature.sig_type.value,
                    "file_name": signature.file_name,
                },
                description=description,
                is_success=True,
            )
        except Exception:
            pass

    def upload_signature(
        self,
        file: UploadFile,
        current_user: User,
        sig_type: SignatureType,
    ) -> SignatureRead:
        """Upload a signature image (e-signature or wet-signature capture)."""
        mime = file.content_type or ""
        if mime not in ALLOWED_SIGNATURE_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"File type '{mime}' is not supported. Allowed types: JPEG, PNG",
            )

        content = file.file.read()
        file_size = len(content)

        max_bytes = 5 * 1024 * 1024
        if file_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Signature file size exceeds the 5 MB limit",
            )

        storage_root = Path(settings.STORAGE_ROOT)
        dest_dir = storage_root / "signatures" / str(current_user.id)
        dest_dir.mkdir(parents=True, exist_ok=True)

        safe_name = f"{uuid.uuid4().hex}_{Path(file.filename or 'signature').name}"
        dest_path = dest_dir / safe_name
        dest_path.write_bytes(content)

        relative_path = str(dest_path.relative_to(storage_root))

        sig = Signature(
            user_id=current_user.id,
            file_name=file.filename or safe_name,
            file_path=relative_path,
            mime_type=mime,
            file_size=file_size,
            sig_type=sig_type,
            is_active=True,
        )
        self.session.add(sig)
        self.session.commit()
        self.session.refresh(sig)

        self._log_audit(
            AuditAction.CREATE_WORKFLOW,
            sig,
            f"User {current_user.id} uploaded {sig_type.value}",
        )

        return self._to_read(sig)

    def list_signatures(self, current_user: User) -> List[SignatureRead]:
        """List the current user's active signatures (newest first)."""
        query = (
            select(Signature)
            .where(
                Signature.user_id == current_user.id,
                Signature.is_active == True,
            )
            .order_by(Signature.created_at.desc())
        )
        signatures = self.session.exec(query).all()
        return [self._to_read(s) for s in signatures]

    def get_signature(self, signature_id: int, current_user: User) -> SignatureRead:
        """Get signature metadata. Users can view their own; admins can view all."""
        sig = self.session.get(Signature, signature_id)
        if not sig:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Signature {signature_id} not found",
            )
        if not sig.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Signature {signature_id} not found",
            )
        if sig.user_id != current_user.id and not current_user.is_admin():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own signatures",
            )
        return self._to_read(sig)

    def get_signature_file(self, signature_id: int, current_user: User) -> Path:
        """Get the file path for serving a signature image."""
        sig = self.session.get(Signature, signature_id)
        if not sig or not sig.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Signature {signature_id} not found",
            )
        if sig.user_id != current_user.id and not current_user.is_admin():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own signatures",
            )

        storage_root = Path(settings.STORAGE_ROOT).resolve()
        abs_path = (storage_root / sig.file_path).resolve()

        if not str(abs_path).startswith(str(storage_root)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file path",
            )

        if not abs_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Signature file not found on disk",
            )

        return abs_path

    def soft_delete_signature(self, signature_id: int, current_user: User) -> SignatureRead:
        """Soft-delete a signature (set is_active=False)."""
        sig = self.session.get(Signature, signature_id)
        if not sig:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Signature {signature_id} not found",
            )
        if not sig.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Signature {signature_id} not found",
            )
        if sig.user_id != current_user.id and not current_user.is_admin():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own signatures",
            )

        sig.is_active = False
        from datetime import datetime
        sig.updated_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(sig)

        self._log_audit(
            AuditAction.DELETE_WORKFLOW,
            sig,
            f"User {current_user.id} deleted signature {signature_id}",
        )

        return self._to_read(sig)

    # ── Admin operations ──────────────────────────

    def _validate_target_user(self, target_user_id: int) -> User:
        """Validate that the target user exists and is active."""
        target = self.session.get(User, target_user_id)
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {target_user_id} not found",
            )
        if not target.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User {target_user_id} is inactive",
            )
        return target

    def admin_upload_for_user(
        self,
        target_user_id: int,
        file: UploadFile,
        current_user: User,
        sig_type: SignatureType,
    ) -> SignatureRead:
        """Admin uploads a signature on behalf of another user.

        If the target user already has an active signature, it is soft-deleted
        (replaced) before the new one is created.
        """
        if not current_user.is_admin():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can manage other users' signatures",
            )
        self._validate_target_user(target_user_id)

        mime = file.content_type or ""
        if mime not in ALLOWED_SIGNATURE_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"File type '{mime}' is not supported. Allowed types: JPEG, PNG",
            )

        content = file.file.read()
        file_size = len(content)

        max_bytes = 5 * 1024 * 1024
        if file_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Signature file size exceeds the 5 MB limit",
            )

        # Soft-delete existing active signature (replace behavior)
        existing_query = (
            select(Signature)
            .where(
                Signature.user_id == target_user_id,
                Signature.is_active == True,
            )
        )
        existing = self.session.exec(existing_query).all()
        from datetime import datetime
        for old_sig in existing:
            old_sig.is_active = False
            old_sig.updated_at = datetime.utcnow()

        storage_root = Path(settings.STORAGE_ROOT)
        dest_dir = storage_root / "signatures" / str(target_user_id)
        dest_dir.mkdir(parents=True, exist_ok=True)

        safe_name = f"{uuid.uuid4().hex}_{Path(file.filename or 'signature').name}"
        dest_path = dest_dir / safe_name
        dest_path.write_bytes(content)

        relative_path = str(dest_path.relative_to(storage_root))

        sig = Signature(
            user_id=target_user_id,
            file_name=file.filename or safe_name,
            file_path=relative_path,
            mime_type=mime,
            file_size=file_size,
            sig_type=sig_type,
            is_active=True,
        )
        self.session.add(sig)
        self.session.commit()
        self.session.refresh(sig)

        self._log_audit(
            AuditAction.CREATE_WORKFLOW,
            sig,
            f"Admin {current_user.id} uploaded {sig_type.value} for user {target_user_id}",
        )

        return self._to_read(sig)

    def list_user_signatures(
        self,
        target_user_id: int,
        current_user: User,
    ) -> List[SignatureRead]:
        """Admin lists active signatures for a specific user."""
        if not current_user.is_admin():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can view other users' signatures",
            )
        self._validate_target_user(target_user_id)

        query = (
            select(Signature)
            .where(
                Signature.user_id == target_user_id,
                Signature.is_active == True,
            )
            .order_by(Signature.created_at.desc())
        )
        signatures = self.session.exec(query).all()
        return [self._to_read(s) for s in signatures]

    def admin_delete_signature(
        self,
        target_user_id: int,
        signature_id: int,
        current_user: User,
    ) -> SignatureRead:
        """Admin deletes a specific signature for a user."""
        if not current_user.is_admin():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can delete other users' signatures",
            )
        self._validate_target_user(target_user_id)

        sig = self.session.get(Signature, signature_id)
        if not sig:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Signature {signature_id} not found",
            )
        if not sig.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Signature {signature_id} not found",
            )
        if sig.user_id != target_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Signature {signature_id} does not belong to user {target_user_id}",
            )

        sig.is_active = False
        from datetime import datetime
        sig.updated_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(sig)

        self._log_audit(
            AuditAction.DELETE_WORKFLOW,
            sig,
            f"Admin {current_user.id} deleted signature {signature_id} for user {target_user_id}",
        )

        return self._to_read(sig)

    def validate_signature_exists(self, signature_id: int) -> Signature:
        """Validate that a signature exists and is active."""
        sig = self.session.get(Signature, signature_id)
        if not sig or not sig.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Signature {signature_id} not found or is inactive",
            )
        return sig
