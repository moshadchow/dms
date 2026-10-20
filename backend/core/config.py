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
    SMTP_HOST:       str  = "smtp.office365.com"
    SMTP_PORT:       int  = 587
    SMTP_USERNAME:   str  = "info@xpertfintech.com"
    SMTP_PASSWORD:   str  = "$December@2026$"
    SMTP_FROM_EMAIL: str  = "info@xpertfintech.com"
    SMTP_USE_TLS:    bool = True
    SMTP_FROM_NAME:  str  = "DMS"

    # ── CORS ──────────────────────────────────
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── Transport ─────────────────────────────
    # Production sits behind nginx TLS termination (see dms.conf). When true,
    # requests that arrive with X-Forwarded-Proto: http are 308-redirected to
    # https. Requests without the forwarded header (internal /health checks,
    # direct uvicorn access) are never redirected.
    FORCE_HTTPS: bool = False

    # ── Rate Limiting ─────────────────────────
    # Per-IP token buckets in middleware/ratelimit.py (spec 31). Limits are
    # requests per client IP per window; AUTH applies to /api/v1/auth/login,
    # REQUESTS to everything else under /api/v1. MAX_KEYS caps how many client
    # IPs are tracked (memory guard — expired buckets are pruned, and the
    # store fails open under pressure). nginx adds an edge limit_req on /api/
    # (see dms.conf) as the outer filter.
    RATE_LIMIT_ENABLED:       bool = True
    RATE_LIMIT_REQUESTS:      int  = 600       # default rule, per IP
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_AUTH_REQUESTS: int  = 10        # POST /api/v1/auth/login, per IP
    RATE_LIMIT_MAX_KEYS:      int  = 10000

    # ── Antivirus / Malware Scanning ───────────
    # Enable/disable AV scanning on uploads
    AV_ENABLED:           bool = True
    # Engine: "clamav" (requires clamd daemon + pip install clamd) or "dummy" (dev only)
    AV_ENGINE:            str  = "dummy"
    # ClamAV daemon connection (used when AV_ENGINE=clamav)
    CLAMD_HOST:           str  = "localhost"
    CLAMD_PORT:           int  = 3310
    # Scan timeout in seconds
    AV_SCAN_TIMEOUT:      int  = 30
    # Deduplication TTL in hours - reuse recent clean scan for same file hash
    AV_DEDUP_TTL_HOURS:   int  = 24

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
