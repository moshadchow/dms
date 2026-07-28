# Repository Guidelines

## Project Structure
FastAPI backend (repo root) + React/Vite frontend (`dms-app/`). Backend feature modules: `auth/`, `users/`, `categories/`, `directories/`, `documents/`. Shared infra in `core/`. Middleware in `middleware/`. Migrations in `migrations/`. Bootstrap data in `seed.py`. Frontend source in `dms-app/src/` organized by concern (`api/`, `components/`, `hooks/`, `pages/`, `store/`, `types/`, `utils/`).

## Backend: Key Commands
```
alembic upgrade head          # apply DB migrations (required before first run)
python seed.py                # seed roles, permissions, and admin user (run once after migrate)
uvicorn main:app --reload     # dev server on :8000
pytest                        # run all tests
```

**`DEBUG=True` bypasses Alembic** — `main.py` lifespan calls `create_db_and_tables()` when DEBUG is true, auto-creating tables from SQLModel metadata. In production, rely solely on `alembic upgrade head`.

## Frontend: Key Commands
```
cd dms-app && npm install
npm run dev      # Vite dev server on :5173 (proxies /api to backend :8000)
npm run build    # tsc + vite build
npm run lint     # ESLint
```

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

## Frontend Auth Flow
- Zustand store (`store/authStore.ts`) persists only tokens to localStorage; the `user` object is re-fetched on every page load via `ProtectedRoute` calling `authApi.me()`.
- Axios client (`api/client.ts`) automatically intercepts 401 responses, attempts a single token refresh, and redirects to `/login` on failure.
- Frontend `@` path alias resolves to `dms-app/src/`.

## Dependency Pins
- `bcrypt==4.0.1` — passlib 1.7.4 is incompatible with bcrypt 4.1+. Do not upgrade.
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
Copy `.env.example` to `.env` for local setup. Never commit real secrets or production JWT keys. Treat `storage/uploads/` as runtime data.
