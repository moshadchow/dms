import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from audit.router        import router as audit_router
from auth.router         import router as auth_router
from backups.router      import router as backups_router
from backups.scheduler   import start_scheduler, stop_scheduler
from categories.router   import router as categories_router
from core.config         import settings
from core.database       import create_db_and_tables
from directories.router  import router as directories_router
from documents.router    import router as documents_router
from memos.router        import router as memos_router
from middleware.audit    import audit_middleware
from middleware.https    import https_enforcement_middleware
from middleware.ratelimit import rate_limit_middleware
from middleware.rbac     import rbac_middleware
from users.router        import router as users_router
from user_levels.router  import router as user_levels_router
from workflow.router import router as workflow_router, instance_router as workflow_instance_router, signature_router as workflow_signature_router
from storage_usage.router import router as storage_router
from company_profile.router import router as company_profile_router
from correspondence.router import router as correspondence_router
from antivirus.router    import router as antivirus_router
from db_backups.router   import router as db_backups_router
from db_backups.scheduler import (
    start_scheduler as start_db_backup_scheduler,
    stop_scheduler  as stop_db_backup_scheduler,
)
from db_backups.service  import get_db_backup_root


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.DEBUG:
        create_db_and_tables()
    if settings.BACKUP_SCHEDULER_ENABLED:
        # Company backup scheduler (spec 35) — in-process asyncio tick loop,
        # single uvicorn worker assumption (same as the rate limiter).
        # Tests disable it via conftest because a TestClient runs lifespan.
        start_scheduler()
    # Spec 36: fail loudly on a DB_BACKUP_ROOT that sits inside STORAGE_ROOT
    # or BACKUP_ROOT. The message is logged rather than raised on purpose —
    # a misconfigured *backup* path must never keep the DMS from serving
    # documents. The authoritative guard still runs inside
    # get_db_backup_root(), which every dump/download calls first, so a bad
    # root can never receive a write (it degrades to status=failed, the same
    # way spec 35 does).
    try:
        get_db_backup_root()
    except Exception:
        logging.getLogger("dms.db_backups").exception(
            "DB_BACKUP_ROOT is misconfigured — database backups will fail"
        )
    if settings.DB_BACKUP_SCHEDULER_ENABLED:
        # Database backup scheduler (spec 36) — a second in-process asyncio
        # tick loop, kept separate from the folder-backup one so the two can
        # be enabled/disabled independently. Disabled in tests for the same
        # reason: a TestClient runs lifespan.
        start_db_backup_scheduler()
    yield
    await stop_db_backup_scheduler()
    await stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## Document Management System API

JWT-authenticated, role-driven document management.

### How to authenticate in Swagger
1. Call `POST /api/v1/auth/login` with your email + password
2. Copy the `access_token` from the response
3. Click the **Authorize** button at the top of this page
4. Paste the token into the **HTTPBearer** value field
5. Click Authorize — all endpoints will now include your token

### Roles & Permissions
| Role    | View | Download | Create | Update | Delete |
|---------|------|----------|--------|--------|--------|
| Admin   |  ✓   |    ✓     |   ✓    |   ✓    |   ✓    |
| Maker   |  ✓   |    ✓     |   ✓    |   ✓    |        |
| Checker |  ✓   |    ✓     |        |   ✓    |        |
| Auditor |  ✓   |    ✓     |        |        |        |
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware stack ──────────────────────────
# Starlette add_middleware inserts each entry at the FRONT of its internal
# list, so the LAST registration below is the OUTERMOST layer. Request flow:
#   CORS → HTTPS → rate limit → audit → RBAC → router

# ── RBAC middleware ───────────────────────────
app.middleware("http")(rbac_middleware)

# ── Audit middleware ─────────────────────────
app.middleware("http")(audit_middleware)

# ── Rate limiting (spec 31) ──────────────────
# Outside audit/RBAC: floods are rejected (429 + Retry-After) before token
# parsing, DB sessions, or audit rows — a flood generates zero DB load, and
# the 429s are never audited.
app.middleware("http")(rate_limit_middleware)

# ── HTTPS enforcement ────────────────────────
# Outside the rate limiter: plain-HTTP arrivals (per nginx's
# X-Forwarded-Proto) get a 308 redirect without consuming rate-limit budget.
# No-op unless FORCE_HTTPS=true; requests without the forwarded header
# (internal health checks, direct uvicorn access) pass through.
app.middleware("http")(https_enforcement_middleware)

# ── CORS ─────────────────────────────────────
# Registered LAST so it is outermost: browser preflights short-circuit
# immediately, and every middleware-generated response below (308 redirects,
# rate-limit 429s, RBAC 401/403s) carries Access-Control-Allow-Origin —
# without this the browser cannot read those error bodies cross-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────
API = "/api/v1"
app.include_router(auth_router,        prefix=f"{API}/auth",        tags=["Auth"])
app.include_router(users_router,       prefix=f"{API}/users",       tags=["Users"])
app.include_router(categories_router,  prefix=f"{API}/categories",  tags=["Categories"])
app.include_router(directories_router, prefix=f"{API}/directories", tags=["Directories"])
app.include_router(documents_router,   prefix=f"{API}/documents",   tags=["Documents"])
app.include_router(user_levels_router, prefix=f"{API}/user-levels", tags=["User Levels"])
app.include_router(audit_router,       prefix=f"{API}/audit-logs",  tags=["Audit Trail"])
app.include_router(workflow_router,          prefix=f"{API}/workflows",           tags=["Workflows"])
app.include_router(workflow_instance_router, prefix=f"{API}/workflow-instances",  tags=["Workflow Instances"])
app.include_router(workflow_signature_router, prefix=f"{API}/signatures",         tags=["Signatures"])
app.include_router(memos_router,             prefix=f"{API}/memos",               tags=["Memos"])
app.include_router(storage_router,           prefix=f"{API}/storage",              tags=["Storage"])
app.include_router(company_profile_router,   prefix=f"{API}/companies",            tags=["Companies"])
app.include_router(correspondence_router,    prefix=f"{API}/correspondences",       tags=["Correspondence"])
app.include_router(antivirus_router,         prefix=f"{API}/antivirus",            tags=["Antivirus"])
app.include_router(backups_router,           prefix=f"{API}/backups",              tags=["Backups"])
app.include_router(db_backups_router,        prefix=f"{API}/db-backups",           tags=["Database Backups"])


# ── Custom OpenAPI — replace OAuth2 with clean HTTPBearer ────
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Replace any auto-generated OAuth2 scheme with a simple HTTPBearer
    schema["components"]["securitySchemes"] = {
        "HTTPBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Paste your access_token from POST /api/v1/auth/login",
        }
    }

    # Apply HTTPBearer globally to all operations
    for path in schema.get("paths", {}).values():
        for operation in path.values():
            operation["security"] = [{"HTTPBearer": []}]

    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi


# ── Health check ──────────────────────────────
@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}