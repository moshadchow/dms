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
    STORAGE_ROOT:      str = "storage"
    MAX_FILE_SIZE_MB:  int = 50
    ALLOWED_MIME_TYPES: List[str] = [
        "application/pdf",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "image/jpeg",
        "image/png",
    ]

    # ── Azure AD (Microsoft Entra ID) ─────────
    # Tenant/client credentials are NOT configured here: Azure AD is
    # company-scoped and stored on the `companies` table (see
    # company_profile/, configured via /api/v1/companies/{id}/azure-config).
    # Only this deployment's own callback URL and frontend origin remain env-configurable.
    AZURE_REDIRECT_URI:  str = "http://localhost:8000/api/v1/auth/azure/callback"
    FRONTEND_URL: str = "http://localhost:5173"

    # ── SMTP / Email ──────────────────────────
    SMTP_HOST:       str  = ""
    SMTP_PORT:       int  = 587
    SMTP_USERNAME:   str  = ""
    SMTP_PASSWORD:   str  = ""
    SMTP_FROM_EMAIL: str  = ""
    SMTP_USE_TLS:    bool = True
    SMTP_FROM_NAME:  str  = "DMS"

    # ── CORS ──────────────────────────────────
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file        = ".env"
        env_file_encoding = "utf-8"
        case_sensitive  = False
        # Unknown env vars (e.g. stale Azure AD credential vars left in an
        # existing .env after the move to company-scoped config) must be
        # ignored, not fatal — otherwise old deployments would not boot.
        extra           = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()


# Module-level shortcut used across the codebase
settings = get_settings()
