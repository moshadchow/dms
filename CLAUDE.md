# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Document Management System (DMS) — a FastAPI + React/Vite full-stack app with JWT auth and role-based access control (RBAC). Four roles: Admin, Maker, Checker, Auditor. Permissions: view, download, create, update, delete.

## Commands

### Backend (repo root)
```bash
# Setup
python -m venv venv && .\venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env                              # then edit secrets
alembic upgrade head                              # apply migrations
python seed.py                                    # create default roles, permissions, admin user

# Run
uvicorn main:app --reload                         # API at http://localhost:8000

# Test
pytest                                            # all tests
pytest tests/test_document_variants.py            # single file
pytest -k "test_name"                             # single test by name
```

### Frontend (dms-app/)
```bash
cd dms-app
npm install
npm run dev                                       # Vite dev server at http://localhost:5173
npm run build                                     # type-check + production build
npm run lint                                      # ESLint for TS/TSX
```

### Database
```bash
alembic upgrade head                              # apply all migrations
alembic revision --autogenerate -m "description"  # generate new migration
```

## Architecture

### Backend — Feature-based modules
Each domain module (`auth/`, `users/`, `categories/`, `directories/`, `documents/`) follows the same pattern:
- **models.py** — SQLModel table definitions and Pydantic schemas
- **schemas.py** — Request/response Pydantic models (when separated from models)
- **service.py** — Business logic, database queries
- **router.py** — FastAPI endpoint definitions

Core infrastructure in `core/`:
- **config.py** — `Settings` via pydantic-settings, loaded from `.env`
- **database.py** — SQLAlchemy engine, `get_session` dependency
- **security.py** — JWT creation/verification, bcrypt password hashing
- **dependencies.py** — `CurrentUser`, `DBSession`, `require_permission()`, `require_admin()` dependency injectors

### Auth & Authorization
- JWT tokens: access (1h) + refresh (7d), HS256-signed
- Two-layer RBAC: middleware-level (`middleware/rbac.py`) checks route-prefix→action map; endpoint-level `require_permission()` dependency provides finer control
- Admin role bypasses all permission checks
- Users have assigned categories (`UserCategoryLink`) for category-scoped document access

### Frontend — React + Zustand + Tailwind
- **Routing**: `react-router-dom` v6 with lazy-loaded pages, `ProtectedRoute` wrapper
- **State**: Zustand stores in `store/` (authStore, directoryStore, themeStore)
- **API layer**: `api/client.ts` (axios instance with interceptors), domain-specific `*.api.ts` files
- **Pages**: LoginPage, DashboardPage, DocumentsPage, AdminPage
- **Styling**: Tailwind CSS

### Key Data Relationships
- Users ↔ Roles (many-to-many via `user_role_links`)
- Roles ↔ Permissions (many-to-many via `role_permission_links`)
- Users ↔ Categories (many-to-many via `user_category_links`)
- Categories → Directories → Documents (hierarchical ownership)
- Documents have variants (file versions) stored on disk in `storage/uploads/`

## Testing

Backend tests use pytest with an async test client (httpx). Test fixtures in `tests/conftest.py` set up an in-memory or test database, create users with specific roles, and provide authenticated API clients. Tests live in `tests/test_*.py`.

## Environment Variables

Copy `.env.example` to `.env`. Key variables: `DATABASE_URL`, `JWT_SECRET_KEY`, `STORAGE_ROOT`, `CORS_ORIGINS`, `DEBUG`.
