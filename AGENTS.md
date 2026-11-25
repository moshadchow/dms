# AGENTS.md

This file provides high-signal guidance for Kilo sessions working in this repository.

---

## Quick Commands

### Backend (run from `backend/` directory)
```bash
# Install deps
pip install -r requirements.txt

# Migrations (REQUIRED before first boot)
alembic upgrade head

# Seed data (roles, permissions, user levels, SuperAdmin)
python seed.py

# Dev server
uvicorn main:app --reload

# Tests
pytest -q
pytest tests/test_file_name.py
pytest tests/test_file_name.py::TestClassName::test_function_name

# Lint / format / typecheck
ruff check .
black .
mypy backend/
```

### Frontend (run from `dms-app/` directory)
```bash
npm install
npm run dev          # proxies /api → backend :8000
npm run build        # tsc + vite build (includes typecheck)
npm run lint         # ESLint
```

---

## Architecture Notes

**Backend**: FastAPI + SQLModel (PostgreSQL in prod), JWT auth (access + refresh), REST under `/api/v1`.

**Middleware stack** (outermost → innermost): CORS → HTTPS enforcement → Rate limiting → Audit logging → RBAC → Router.

**Frontend**: React + TypeScript + Vite, Tailwind CSS. API client baseURL `/api/v1`.

**Company scoping** (cross-cutting, easiest to break):
- `Company` is the tenancy boundary; `users`, `categories`, `correspondences` have `company_id` FK.
- **ADMIN** auto-scoped to `current_user.company_id`; client-supplied `company_id` ignored.
- **SUPERADMIN** passes authorization guards but denied at service layer for mutations (403); reads need explicit `company_id` query param.
- `Company.short_name` must match `[A-Za-z0-9_-]+`; used as storage namespace.

---

## Known Baseline Failures

2 tests always fail (do not chase as regressions):
- `test_workflow.py::TestApprovalActionService::test_parallel_step_any_approve_completes`
- `test_workflow_company.py::TestSuperAdminCategoryRestrictions::test_superadmin_cannot_modify_category_ids`

Healthy run: `2 failed, 686 passed`.

**New feature (Spec 37)**: Move Directories and Documents — 22 new tests in `tests/test_move_directories.py` and `tests/test_move_documents.py` (all passing).

---

## Critical Gotchas

### DB / Startup Invariant
- `main.py` lifespan calls `create_db_and_tables()` when `DEBUG=True`, silently bypassing Alembic. It only builds tables from SQLModel metadata — **will not apply column adds to existing tables**. Production runs `DEBUG=false` + `alembic upgrade head` only.

### Enum Columns Migration Trap
- Migration `server_default` must use the enum's `.name` (UPPERCASE), not `.value`. SQLModel maps `field: SomeStrEnum` to `sa.Enum`, which writes and expects the member's name. Lowercase defaults survive unnoticed until something inserts relying on the default.

### RBAC: Two Layers
1. `middleware/rbac.py` `ROUTE_PERMISSION_MAP` maps `(HTTP_METHOD, path_prefix)` → `PermissionAction`, matched by **longest prefix**.
2. Per-endpoint `dependencies=[Depends(require_permission(PermissionAction.X))]` in the router.

Do not invent permission verbs — matrix is fixed: `view`, `download`, `create`, `update`, `delete`.

### Auth & User Injection
- `core/dependencies.py` provides: `CurrentUser`, `AdminUser`, `AdminOnlyUser`, `SuperAdminUser`, `require_permission`.
- JWT access + refresh via `core/security.py`; `main.py` rewrites OpenAPI security to plain `HTTPBearer`.

### Audit Trail
- `AuditService.log_event()` in `audit/service.py` is the single audit sink. Opens its own `Session(engine)` so logs commit even when caller rolls back, and never raises. Call it after every significant mutation in a service. Audit records are immutable.

### Directory Navigation Access (three tiers — do not collapse)
- **Direct access** (`ensure_directory_access`, `ensure_category_access`): Required for ALL writes and document detail/view/download.
- **Navigation access** (`can_navigate_directory` / `ensure_directory_read_access`): Read-only traversal of a parent with ≥1 accessible descendant.
- **Category metadata** (`ensure_category_read_access`): Directory-grant users may read a category holding one of their grants.

Non-admin denials return **404, not 403** (oracle avoidance).

### Stored Path Values
- `storage_path` values are **company-relative and POSIX** (`uploads/<category_id>/<directory_id>/<file>`).
- Rows written on Windows hold backslashes, which are literal filename characters on Linux — resolver normalizes `\` → `/`.
- Always resolve through `documents/utils.py::resolve_storage_path(relative_path, company)` — never `STORAGE_ROOT / relative_path` by hand.

### Rate Limiting (spec 31)
- In-process token buckets per `(rule, client_ip)` (no Redis; single uvicorn worker).
- Rules: `auth` = 10 req/window on `/api/v1/auth/login`, `default` = 600 req/window on `/api/v1`.
- Skips `OPTIONS`, anything outside `/api/v1` (`/health`, `/docs`), and everything when `RATE_LIMIT_ENABLED=false`.
- Rejection = **429 + `Retry-After` + JSON `detail`**.

### Azure AD
- Company-scoped and database-driven — **no global `.env` fallback**.
- Config lives on `Company` (`azure_client_id`, `azure_client_secret`, `azure_tenant_id`, `azure_enabled`, `azure_default_role_name`).
- Managed via `/api/v1/companies/{id}/azure-config` (secret is write-only).
- `GET /azure/login?company_id=<id>` requires the company and validates it server-side.

### File Organization (per module)
| Module | Typical Contents |
|--------|-----------------|
| `models.py` | SQLModel + read schemas |
| `schemas.py` | Write schemas (optional) |
| `service.py` | Class-based, takes `Session` |
| `router.py` | Thin — business logic in service |

---

## Deployment

**Production is not Docker**: `dms-backend.service` (systemd unit, uvicorn on 127.0.0.1:8000) + `dms.conf` (nginx TLS terminating).

- `docker-compose.yml` is **stale** — builds `./backend` and `./frontend` which do not exist.
- **Production Docker Compose**: `compose.prod.yaml` — fixed production compose file. Uses `env_file: .env.prod`.
- **Docker Swarm**: `compose.prod.swarm.yaml` — Swarm-mode compose with secrets-based configuration and overlay network. Requires external secrets for `database_url`, `jwt_secret_key`, `gunicorn_workers`.
- TLS via Let's Encrypt/bootstrap with `scripts/tls/install_tls.sh`.
- Manual deploy script: `deploy.sh` (run on server, does git reset --hard, migrations, gunicorn restart).

---

## Spec-Driven Workflow

Features are numbered steps. Specs live in `specs/` directory (older `feature_*`/`instruction_*` files are legacy). Use `/create-spec` (`.opencode/commands/create-spec.md` or `.kilo/commands/create-spec.md`) to scaffold the next one with required structure:
- Overview, Depends on, Routes, Database changes, Files to change, Files to create, New dependencies, Rules for implementation, Definition of done.

Check `specs/` for the highest number before starting new work. Do not create a `plans/` directory.

---

## Test Notes

- Tests use SQLite in-memory (`sqlite://` + `StaticPool`).
- `conftest.py` patches multiple modules' `engine` at import time: `core.database`, `middleware.rbac`, `middleware.audit`, `notifications.tasks`, `backups.scheduler`, `db_backups.scheduler`.
- Schedulers and rate limiting are disabled in tests via monkeypatched settings.
- SMTP is disabled in tests (`SMTP_HOST=""`).
- `pg_dump` path pointed at non-existent binary; tests that need a dump monkeypatch `db_backups.service._run_pg_dump`.

---

## Commits

- Short imperative subjects in repo's existing style (e.g. `Implemented Reply correspondence lifecycle-v1`).
- End git commit messages with: `Co-Authored-By: Claude Code <noreply@anthropic.com>`
- End pull request descriptions with: `🤖 Generated with [Claude Code](https://claude.com/claude-code)`