from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from auth.router        import router as auth_router
from categories.router  import router as categories_router
from core.config        import settings
from core.database      import create_db_and_tables
from directories.router import router as directories_router
from documents.router   import router as documents_router
from middleware.rbac    import rbac_middleware
from users.router       import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.DEBUG:
        create_db_and_tables()
    yield


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

# ── CORS ─────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── RBAC middleware ───────────────────────────
app.middleware("http")(rbac_middleware)

# ── Routers ───────────────────────────────────
API = "/api/v1"
app.include_router(auth_router,        prefix=f"{API}/auth",        tags=["Auth"])
app.include_router(users_router,       prefix=f"{API}/users",       tags=["Users"])
app.include_router(categories_router,  prefix=f"{API}/categories",  tags=["Categories"])
app.include_router(directories_router, prefix=f"{API}/directories", tags=["Directories"])
app.include_router(documents_router,   prefix=f"{API}/documents",   tags=["Documents"])


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