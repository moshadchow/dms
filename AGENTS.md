# Repository Guidelines

## Project Structure
FastAPI backend (repo root) + React/Vite frontend (`dms-app/`). Backend feature modules: `auth/`, `users/`, `categories/`, `directories/`, `documents/`, `user_levels/`. Shared infra in `core/`. Middleware in `middleware/`. Migrations in `migrations/`. Bootstrap data in `seed.py`. Frontend source in `dms-app/src/` organized by concern (`api/`, `components/`, `hooks/`, `pages/`, `store/`, `types/`, `utils/`).

## Backend: Key Commands
```
alembic upgrade head          # apply DB migrations (required before first run)
python seed.py                # seed roles, permissions, and admin user (run once after migrate)
uvicorn main:app --reload     # dev server on :8000
pytest                        # run all tests (57 tests, SQLite in-memory)
```

**`DEBUG=True` bypasses Alembic** — `main.py` lifespan calls `create_db_and_tables()` when DEBUG is true, auto-creating tables from SQLModel metadata. In production, rely solely on `alembic upgrade head`.

## Frontend: Key Commands
```
cd dms-app && npm install
npm run dev      # Vite dev server on :5173 (proxies /api to backend :8000)
npm run build    # tsc + vite build
npm run lint     # ESLint
```

Frontend env: `dms-app/env` sets `VITE_API_BASE_URL=/api`. The `@` alias resolves to `dms-app/src/`.

## Testing: SQLite In-Memory
Tests use `SQLite` + `StaticPool` (in-memory), **not** PostgreSQL. The `conftest.py` fixture monkeypatches the engine in two places:
- `core.database.engine`
- `middleware.rbac.engine`

Any new module that imports `engine` directly (e.g., for a new middleware) must be patched in the test fixture or tests will hit the wrong database.

## RBAC Middleware: Hardcoded Route Map
`middleware/rbac.py` has a `ROUTE_PERMISSION_MAP` dict mapping `(HTTP_METHOD, path_prefix)` to a `PermissionAction`. **New endpoints that require permission checks must be added here**, otherwise they are silently unprotected by the middleware (individual endpoint guards via `require_permission()` still apply, but the middleware safety net is bypassed).

Paths under `/api/v1/auth`, `/docs`, `/redoc`, `/openapi.json`, and `/health` bypass RBAC entirely (`PUBLIC_PATH_PREFIXES`).

## Backend Module Convention
Each feature module follows this pattern:
- `models.py` — SQLModel ORM models + Pydantic read schemas
- `schemas.py` — additional request/response schemas
- `service.py` — business logic (class-based, takes `Session`)
- `router.py` — FastAPI router

The `documents/` module has two service classes: `DocumentService` and `DocumentVariantService`.

## Auth & User Injection
Use the `CurrentUser` annotated type from `core/dependencies.py` to inject the authenticated user into endpoints:
```python
from core.dependencies import CurrentUser
def my_endpoint(current_user: CurrentUser = None): ...
```

`AdminUser` (also from `core/dependencies.py`) raises 403 for non-admins.

## Azure AD Authentication
Backend module: `auth/azure_service.py` handles PKCE, token exchange, ID token validation, and JIT user provisioning.

**Key files:**
- `auth/router.py` — `/azure/login`, `/azure/callback`, `/azure/config` endpoints
- `auth/azure_service.py` — Azure token exchange, ID token validation, user resolution
- `core/config.py` — `AZURE_*` and `FRONTEND_URL` settings
- `dms-app/src/pages/AzureCallbackPage.tsx` — frontend callback handler

**Azure callback flow:** Login → Azure → callback exchanges code for tokens → validates ID token → resolves/creates user → redirects to `{FRONTEND_URL}/auth/callback?access_token=...&refresh_token=...`

**Error surfacing:** `azure_callback` in `auth/router.py` has separate `except HTTPException` and `except Exception` handlers. In DEBUG mode, the actual error message is URL-encoded in the `?error=` query param. Audit events go to `dms.auth` logger.

**JWK parsing:** `python-jose`'s `jwk.construct()` fails with Azure AD signing keys that include `x5c` fields. `azure_service.py:188-203` uses the `cryptography` library to build RSA public keys from the X.509 certificate chain instead. Do not revert to `jwk.construct()`.

**Azure env vars** (in `.env`):
```
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=
AZURE_TENANT_ID=
AZURE_REDIRECT_URI=http://localhost:8000/api/v1/auth/azure/callback
AZURE_DEFAULT_ROLE_NAME=auditor
FRONTEND_URL=http://localhost:5173
```

Azure is enabled when all three of `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, and `AZURE_TENANT_ID` are set.

## Frontend Auth Flow
- Zustand store (`store/authStore.ts`) persists only tokens to localStorage; the `user` object is re-fetched on every page load via `ProtectedRoute` calling `authApi.me()`.
- Axios client (`api/client.ts`) automatically intercepts 401 responses, attempts a single token refresh, and redirects to `/login` on failure.
- Azure AD: `LoginPage.tsx` link → backend `/azure/login` → Azure → callback → `AzureCallbackPage.tsx` stores tokens → fetches user → navigates to dashboard.

## User Levels
`user_levels/` module manages document visibility tiers. Documents are linked to user levels via `DocumentUserLevelLink`. Users can only see documents linked to their level (enforced in `documents/service.py`). Admin bypasses all level restrictions.

## Dependency Pins
- `bcrypt==4.0.1` — passlib 1.7.4 is incompatible with bcrypt 4.1+. Do not upgrade.
- `python-jose[cryptography]==3.3.0` — used for JWT and OIDC (JWK parsing replaced with `cryptography` for Azure AD keys).
- `httpx==0.27.0` — used for Azure AD token exchange (async HTTP client).
- Frontend: React 18, Vite 5, Zustand 4, React Router 6.

## Seed Data
`seed.py` creates four roles with fixed permission matrices:
| Role    | Permissions |
|---------|------------|
| Admin   | view, download, create, update, delete |
| Maker   | view, download, create, update |
| Checker | view, download, update |
| Auditor | view, download |

Default admin: `admin@dms.local` / `Admin@1234`.

## Docker Compose (Stale)
`docker-compose.yml` references `./backend` and `./frontend` directories that don't match the current repo layout. It may need updating before use.

## Coding Style
4-space indent in Python, 2-space in TypeScript/TSX. `snake_case` for Python, `PascalCase` for React components, `camelCase` for hooks/stores/utils.

## Commits & PRs
Short imperative subjects (`Fix archieve & Restore feature`). PRs: clear summary, migration notes for schema changes, screenshots for UI.

## Security
Copy `.env.example` to `.env` for local setup. Never commit `.env` (it contains Azure AD client secrets). GitHub secret scanning will reject pushes containing Azure secrets. Treat `storage/uploads/` as runtime data. Ensure `__pycache__/` and `*.pyc` are in `.gitignore` before committing.
