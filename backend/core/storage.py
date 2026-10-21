from pathlib import Path
import logging
import re

from fastapi import HTTPException, status

from core.config import APP_ROOT, get_settings
from company_profile.models import Company


logger = logging.getLogger("dms.storage")


class StorageService:
    """Centralized storage path resolution with company isolation."""

    @property
    def storage_root(self) -> Path:
        """Absolute storage root.

        A relative STORAGE_ROOT is resolved against the application root
        (the directory holding `core/`), never against the process working
        directory: the same configuration must resolve to the same tree no
        matter where uvicorn was launched from. An absolute STORAGE_ROOT is
        used as-is.
        """
        raw = Path(get_settings().STORAGE_ROOT).expanduser()
        if not raw.is_absolute():
            raw = APP_ROOT / raw
        return raw.resolve()

    @staticmethod
    def _normalize(relative_path: str) -> str:
        """Normalize a stored relative path to POSIX separators.

        Rows written on Windows hold backslashes (`uploads\\1\\2\\file.pdf`).
        A backslash is a literal character in a POSIX filename, so the very
        same row would not resolve on Linux. Normalizing at the single
        resolution point keeps stored values and the resolver in agreement on
        every platform.
        """
        return relative_path.replace("\\", "/")

    def _validate_short_name(self, short_name: str) -> str:
        """Normalize and validate company short_name for filesystem safety."""
        if not short_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Company short name cannot be empty"
            )
        
        # Allow only alphanumeric, hyphen, underscore
        safe = re.sub(r'[^a-zA-Z0-9_-]', '', short_name)
        
        if not safe or safe != short_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid company short name for storage (only alphanumeric, hyphen, underscore allowed)"
            )
        
        # Prevent path traversal attempts
        if ".." in safe or safe.startswith("/") or safe.startswith("\\"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path traversal detected in company short name"
            )
        
        return safe

    def get_company_root(self, company: Company) -> Path:
        """Get the absolute company storage root: STORAGE_ROOT/<short_name>/"""
        safe_name = self._validate_short_name(company.short_name)
        company_root = (self.storage_root / safe_name).resolve()
        
        # Ensure it stays within storage root
        if not str(company_root).startswith(str(self.storage_root)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path traversal detected"
            )
        
        return company_root

    def get_uploads_root(self, company: Company) -> Path:
        """STORAGE_ROOT/<short_name>/uploads/"""
        root = self.get_company_root(company) / "uploads"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def get_memos_root(self, company: Company) -> Path:
        """STORAGE_ROOT/<short_name>/memos/"""
        root = self.get_company_root(company) / "memos"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def get_signatures_root(self, company: Company) -> Path:
        """STORAGE_ROOT/<short_name>/signatures/"""
        root = self.get_company_root(company) / "signatures"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def get_correspondence_root(self, company: Company) -> Path:
        """STORAGE_ROOT/<short_name>/correspondence/"""
        root = self.get_company_root(company) / "correspondence"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def resolve_path(self, company: Company, relative_path: str) -> Path:
        """Resolve a DB-relative path to absolute, validating it stays in company root."""
        company_root = self.get_company_root(company)
        abs_path = (company_root / self._normalize(relative_path)).resolve()

        if not str(abs_path).startswith(str(company_root)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path traversal detected"
            )

        if not abs_path.exists():
            # A missing company root means the storage *configuration* is
            # wrong, not that the file is absent — say so loudly, because
            # both surface to the caller as a bare 404.
            if not company_root.exists():
                logger.warning(
                    "Storage company root %s does not exist (company=%s, "
                    "STORAGE_ROOT=%s) — check the storage configuration",
                    company_root,
                    company.short_name,
                    get_settings().STORAGE_ROOT,
                )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found on disk"
            )

        return abs_path

    def resolve_path_with_fallback(self, relative_path: str, company: Company = None) -> Path:
        """
        Resolve path with backward compatibility fallback.
        Tries new company-prefixed path first, then old path without company prefix.
        """
        # Try new company-aware path first
        if company:
            try:
                return self.resolve_path(company, relative_path)
            except HTTPException:
                pass

        # Fallback: try old path (without company prefix)
        abs_path = (self.storage_root / self._normalize(relative_path)).resolve()
        if not str(abs_path).startswith(str(self.storage_root)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file path"
            )
        
        if not abs_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found on disk"
            )
        
        return abs_path


# Module-level singleton
storage_service = StorageService()