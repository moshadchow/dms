# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this repository.

## Project Structure

Dual-app repo: **FastAPI backend** at repo root + **React + Vite frontend** in `dms-app/`.

Backend features follow a consistent module convention:
- `models.py` — SQLModel ORM models + Pydantic read schemas
- `service.py` — Business logic (class-based, takes `Session`)
- `router.py` — FastAPI router
- `schemas.py` — Additional request/response schemas (where separate from models)

Shared infra in `core/`, middleware in `middleware/`, migrations in `migrations/`.

## Commands

Backend (Python / FastAPI)
```bash
alembic upgrade head          # Apply DB migrations (required before first run)
python seed.py                # Seed roles, permissions, admin user (run after migrate)
uvicorn main:app --reload     # Dev server on :8000
pytest                        # Run all tests (SQLite in-memory)
pytest tests/path/to/test.py  # Single test file
pytest tests/foo/test_bar.py::test_baz  # Single test function
ruff check . && black .       # Lint / format
```

Frontend (dms-app)
```bash
cd dms-app && npm install
npm run dev       # Vite dev server on :5173 (proxies /api to backend)
npm run build     # tsc + vite build (includes typecheck)
npm run lint      # ESLint
```

## High-Level Architecture

- **API surface**: All endpoints under `/api/v1`. Public paths (`/api/v1/auth`, `/docs`, `/redoc`, `/openapi.json`, `/health`) bypass RBAC.
- **Auth**: JWT access + refresh tokens. Azure AD (Microsoft Entra ID) integration via PKCE. `python-jose` for JWT; `cryptography` for Azure JWK/X.509 parsing (do NOT revert to `jwk.construct()`).
- **RBAC**: Two-layer defense: (1) `middleware/rbac.py` `ROUTE_PERMISSION_MAP` maps `(HTTP_METHOD, path_prefix)` → `PermissionAction`; (2) per-endpoint `require_permission()` guards in `core/dependencies.py`.
- **Audit**: `AuditService.log_event()` is the authoritative audit sink. Uses an independent `Session(engine)` so logs persist even if caller rolls back. Immutable records — no PUT/PATCH/DELETE endpoints.
- **DB**: SQLModel ORM. SQLite for tests (`StaticPool`). PostgreSQL in production. `create_db_and_tables()` only runs when `DEBUG=True` — production must use `alembic upgrade head`.
- **Frontend**: Zustand stores for auth/workflow/theme, Axios `apiClient` with automatic 401 refresh interceptor, React Router with protected routes.

## Critical Cross-File Rules

### Tests
Tests use SQLite in-memory with `StaticPool`. `conftest.py` monkeypatches `engine` in three places:
- `core.database.engine`
- `middleware.rbac.engine`
- `middleware.audit.engine`
If you add a new module that imports `engine` at import time, update `conftest.py` or use lazy access.

### RBAC
New routes **must** be added to `ROUTE_PERMISSION_MAP` in `middleware/rbac.py`, or the middleware silently skips protection for unknown prefixes.

### Dependency Pins
- `bcrypt==4.0.1` — passlib 1.7.4 breaks with bcrypt 4.1+
- `python-jose[cryptography]==3.3.0`
- `httpx==0.27.0`

### Frontend
- Import `apiClient` from `./client`, not `apiRoot` from `./base`
- Use `getErrorMessage()` for error display
- `npm run build` includes `tsc` typecheck — no separate typecheck script

### Dependency Injection
Use `CurrentUser` from `core/dependencies.py` for authenticated user injection. `AdminUser` allows both ADMIN and SUPERADMIN. `SuperAdminUser` restricts to SUPERADMIN only.

### Azure AD JWKs
`auth/azure_service.py` constructs RSA public keys from `x5c` certificate chains using the `cryptography` library. Do not revert to `python-jose.jwk.construct()`.

### Audit Trail
Always use `AuditService.log_event()` for significant operations. Never create alternate audit sinks.
