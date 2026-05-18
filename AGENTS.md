# Repository Guidelines

## Project Structure & Module Organization
This repository has a FastAPI backend at the repo root and a React/Vite frontend in [`dms-app/`](./dms-app). Backend modules are split by feature: `auth/`, `users/`, `categories/`, `directories/`, and `documents/`, with shared infrastructure in `core/` and cross-cutting logic in `middleware/`. Database migrations live in `migrations/`, uploads in `storage/uploads/`, and bootstrap data in `seed.py`.

Frontend code lives under `dms-app/src/` and is organized by concern: `api/`, `components/`, `hooks/`, `pages/`, `store/`, `types/`, and `utils/`.

## Build, Test, and Development Commands
Backend:

- `python -m venv venv && .\\venv\\Scripts\\activate` - create and activate a local virtualenv on Windows.
- `pip install -r requirements.txt` - install FastAPI, SQLModel, Alembic, and test dependencies.
- `alembic upgrade head` - apply database migrations.
- `python seed.py` - create default roles, permissions, and the admin user.
- `uvicorn main:app --reload` - run the API locally at `http://localhost:8000`.
- `pytest` - run backend tests.

Frontend:

- `cd dms-app && npm install` - install frontend dependencies.
- `npm run dev` - start the Vite dev server.
- `npm run build` - type-check and build production assets.
- `npm run lint` - run ESLint for TypeScript and React files.

## Coding Style & Naming Conventions
Use 4-space indentation in Python and 2-space indentation in TypeScript/TSX. Keep backend modules split into `models.py`, `schemas.py`, `service.py`, and `router.py` where that pattern already exists. Use `snake_case` for Python functions and files, `PascalCase` for React components, and `camelCase` for hooks, stores, and utilities.

## Testing Guidelines
`pytest` and `pytest-asyncio` are available for backend testing. Add tests under a top-level `tests/` package, with names like `test_auth.py` or `test_documents_api.py`. Prefer focused API and service-layer tests for permission changes, migrations, and document workflows. Run `pytest` before opening a PR and `npm run lint` for frontend changes.

## Commit & Pull Request Guidelines
Recent history uses short imperative commit subjects such as `Change password layout`. Keep commit messages concise, present tense, and scoped to one change; for example, `categories: add user-specific permission filter`. PRs should include a clear summary, linked issue or task, migration notes when schema changes are involved, and screenshots for UI updates. Call out any `.env`, storage, or seed-data changes explicitly.

## Security & Configuration Tips
Copy `.env.example` to `.env` for local setup. Do not commit real secrets, production JWT keys, or uploaded documents containing sensitive data. Treat `storage/uploads/` as runtime data, not source code.
