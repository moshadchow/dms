from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Application ───────────────────────────
    APP_NAME:    str  = "Document Management System"
    APP_VERSION: str  = "1.0.0"
    DEBUG:       bool = False

    # ── Database ──────────────────────────────
    DATABASE_URL: str = "postgresql+psycopg2://postgres:root@localhost:5432/dms_db"
    DB_ECHO:      bool = False   # set True in dev to log SQL

    # ── JWT ───────────────────────────────────
    JWT_SECRET_KEY:        str = "change-me-in-production"
    JWT_ALGORITHM:         str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES:  int = 60       #  1 hour
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080    #  7 days

    # ── File Storage ──────────────────────────
    STORAGE_ROOT:      str = "storage/uploads"
    MAX_FILE_SIZE_MB:  int = 50
    ALLOWED_MIME_TYPES: List[str] = [
        "application/pdf",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "image/jpeg",
        "image/png",
    ]

    # ── Azure AD (Microsoft Entra ID) ─────────
    AZURE_CLIENT_ID:     str = ""
    AZURE_CLIENT_SECRET: str = ""
    AZURE_TENANT_ID:     str = ""
    AZURE_REDIRECT_URI:  str = "http://localhost:8000/api/v1/auth/azure/callback"
    AZURE_SCOPES:        List[str] = ["openid", "profile", "email"]
    AZURE_DEFAULT_ROLE_NAME: str = "auditor"  # role assigned to JIT-provisioned users

    @property
    def AZURE_AUTHORITY(self) -> str:
        return f"https://login.microsoftonline.com/{self.AZURE_TENANT_ID}"

    @property
    def AZURE_ENABLED(self) -> bool:
        return bool(self.AZURE_CLIENT_ID and self.AZURE_CLIENT_SECRET and self.AZURE_TENANT_ID)

    # ── CORS ──────────────────────────────────
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file        = ".env"
        env_file_encoding = "utf-8"
        case_sensitive  = False


@lru_cache()
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()


# Module-level shortcut used across the codebase
settings = get_settings()
