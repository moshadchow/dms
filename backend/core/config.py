from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings


# The application root — the directory that holds `core/` (and, in every
# supported deployment, `main.py`):
#
#   dev  : F:\Python-Project\dms\backend
#   prod : /var/www/dms
#
# Path-ish settings are resolved against this directory rather than the
# process working directory, so the app resolves the same tree no matter
# where uvicorn was launched from.
APP_ROOT: Path = Path(__file__).resolve().parents[1]

# The repository root — the parent of the application root. The shared `.env`
# lives here (see `.env.example`), while the backend package lives in
# `backend/`, so this is where the env file is found when the server is
# started from the application directory.
REPO_ROOT: Path = APP_ROOT.parent


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

    # ── Backups (spec 35) ─────────────────────
    # Company-wise folder backup archives. BACKUP_ROOT is resolved against
    # APP_ROOT exactly like STORAGE_ROOT (relative → APP_ROOT, absolute
    # as-is) and MUST stay outside STORAGE_ROOT: a backup must never contain
    # itself, and storage-usage/quota accounting must not double-count it.
    # The default is deliberately NOT "backups" — that name would collide
    # with the backups/ Python module sitting next to core/ (runtime data
    # must never be written into the source tree).
    BACKUP_ROOT: str = "backups_data"
    # In-process scheduler tick loop (backups/scheduler.py). Same single
    # uvicorn worker assumption as the rate limiter; disable in tests (a
    # TestClient runs lifespan and would start the loop) and in any future
    # multi-worker deployment.
    BACKUP_SCHEDULER_ENABLED:      bool = True
    BACKUP_SCHEDULER_TICK_SECONDS: int  = 300

    class Config:
        # Env files, ordered lowest → highest priority: pydantic-settings
        # gives the LAST file in the list precedence, and ignores files that
        # do not exist.
        #
        #   1. <repo root>/.env  — the documented location (`.env.example`)
        #   2. <app root>/.env   — a self-contained backend deployment
        #   3. ./.env            — relative to the process working directory
        #
        # Before this list the app only ever looked at `./.env`, which meant
        # that starting the server from `backend/` silently ignored the
        # repo-root `.env` and fell back to the code defaults.
        env_file = (
            str(REPO_ROOT / ".env"),
            str(APP_ROOT / ".env"),
            ".env",
        )
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
