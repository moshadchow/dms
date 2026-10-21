# Spec: Automated Company-Wise Folder Backup Service

## Overview
This feature adds an automated, company-wise folder backup service that archives each company's storage namespace (`STORAGE_ROOT/<short_name>/{uploads,memos,signatures,correspondence}`) into a timestamped zip file under a separate `BACKUP_ROOT/<short_name>/`, on a configurable schedule and on demand. Runs are recorded in a `backup_runs` table (status, file count, size, error), listed through an admin UI page, downloadable for restore, pruned by a retention policy, and written to the audit trail. At this stage of the roadmap the DMS already holds multi-tenant regulated documents behind production TLS/rate-limiting (specs 30/31) with company-scoped storage (spec 21), so a self-contained disaster-recovery story — no external backup products, no new dependencies, single-uvicorn-worker deployment — is the natural next hardening step.

## Depends on
- Spec 15: Company Profile Management (`Company`, `short_name` storage namespace)
- Spec 17: Company-Wise SuperAdmin Permission (SUPERADMIN read-only cross-company visibility rules)
- Spec 19: Company-Wise Audit Trail (`AuditService.log_event`)
- Spec 21: Company-Based Document Storage Structure (`core/storage.py::storage_service` path resolution + validation)
- Spec 31: Rate Limiting (precedent for in-process background work on the single uvicorn worker)
- `storage_usage` SystemSetting key/value store (admin-configurable settings pattern, cf. `storage_capacity_gb`)
- Alembic migration chain — current head `20261018_153000`

## Routes
All new routes are registered at `/api/v1/backups` (tag "Backups"):

- `GET /api/v1/backups` — paginated backup run history; ADMIN sees own company only, SUPERADMIN sees all companies with optional `company_id` filter — access level: admin (AdminUser + VIEW)
- `GET /api/v1/backups/{id}` — single run detail; cross-company access returns 404 — access level: admin (AdminUser + VIEW)
- `POST /api/v1/backups/run` — trigger an immediate backup of the caller's company; returns the completed run (HTTP 200, `status` may be `failed` — failure is data, not an error response); 409 if a run for that company is already `running` — access level: admin (AdminUser + CREATE; SUPERADMIN rejected 403 at the service layer per the repo's mutation invariant since it has no company)
- `GET /api/v1/backups/{id}/download` — stream the zip archive; pruned archives (retention) return 404 with a clear message — access level: admin (AdminUser + DOWNLOAD)
- `GET /api/v1/backups/settings` — read schedule settings (`enabled`, `interval_hours`, `retention_count`) — access level: admin (AdminUser + VIEW)
- `PUT /api/v1/backups/settings` — update schedule settings; SUPERADMIN allowed, mirroring the `PUT /storage/capacity` precedent — access level: admin (AdminUser + UPDATE)

## Database changes
New table `backup_runs`:

| column | type | notes |
|---|---|---|
| `id` | int PK | |
| `company_id` | int FK `companies.id`, NOT NULL, indexed | tenancy boundary |
| `status` | str(20), indexed | `pending` \| `running` \| `success` \| `failed` (plain string, no DB enum) |
| `trigger` | str(10) | `manual` \| `scheduled` |
| `triggered_by` | int FK `users.id`, nullable | NULL for scheduled runs |
| `started_at` | datetime, nullable | |
| `finished_at` | datetime, nullable | |
| `file_count` | int, default 0 | files archived |
| `total_bytes` | int, default 0 | uncompressed bytes |
| `archive_path` | str(500), nullable | POSIX, relative to `BACKUP_ROOT` (e.g. `acme/backup_20261021T093000Z.zip`); NULL = pruned by retention |
| `archive_size_bytes` | int, nullable | zip size on disk |
| `error_message` | str(500), nullable | set when `status=failed` |
| `created_at` | datetime, indexed | |

Composite index `(company_id, created_at)`.

Schedule settings **reuse the existing `system_settings` table** (`storage_usage/models.py::SystemSetting`) with three new keys seeded idempotently: `backup_enabled` = `"true"`, `backup_interval_hours` = `"24"`, `backup_retention_count` = `"7"`.

One new Alembic revision, date-prefixed per `alembic.ini` `file_template` (e.g. `migrations/versions/20261021_0900_add_backup_runs.py`), `revision = '20261021_0900'`, `down_revision = '20261018_153000'`. No DB enum change: `audit_logs.action`/`module` are plain strings (`max_length=50`), so the new `AuditAction`/`AuditModule` members need no migration.

## Templates
No Jinja2 templates — frontend is React/Vite SPA. Frontend changes are listed under "Files to change" / "Files to create".

## Files to change
Backend (paths relative to `backend/`):
- `main.py` — import and include `backups.router` at `f"{API}/backups"` (tag "Backups"); start the scheduler task in `lifespan` when `settings.BACKUP_SCHEDULER_ENABLED`, cancel it on shutdown
- `core/config.py` — add `BACKUP_ROOT: str = "backups_data"` (resolved against `APP_ROOT` like `STORAGE_ROOT`, absolute values used as-is, never inside `STORAGE_ROOT`; the default deliberately avoids the name `backups` so runtime data can never collide with the `backups/` Python module), `BACKUP_SCHEDULER_ENABLED: bool = True`, `BACKUP_SCHEDULER_TICK_SECONDS: int = 300`
- `core/database.py` — `import backups.models` in `create_db_and_tables()` **after** `company_profile.models` (FK to `companies`)
- `middleware/rbac.py` — add to `ROUTE_PERMISSION_MAP`:
  - `("GET", "/api/v1/backups") → PermissionAction.VIEW`
  - `("POST", "/api/v1/backups") → PermissionAction.CREATE`
  - `("PUT", "/api/v1/backups") → PermissionAction.UPDATE`
- `audit/models.py` — add `AuditAction.CREATE_BACKUP = "create_backup"`, `BACKUP_FAILED = "backup_failed"`, `DOWNLOAD_BACKUP = "download_backup"`, `UPDATE_BACKUP_SETTINGS = "update_backup_settings"`; add `AuditModule.BACKUPS = "backups"`
- `seed.py` — idempotently seed the three `backup_*` SystemSetting keys (same style as `storage_capacity_gb`)
- `tests/conftest.py` — in the `client` fixture: `monkeypatch.setattr(core.database.settings, "BACKUP_SCHEDULER_ENABLED", False)` (a `TestClient` runs lifespan, so the scheduler must never start in tests), point `BACKUP_ROOT` at `tmp_path / "backups"`, and patch `engine` in any new module that does `from core.database import engine` at import time (e.g. `backups.scheduler`)
- `.env.example` (repo root) — document `BACKUP_ROOT`, `BACKUP_SCHEDULER_ENABLED`, `BACKUP_SCHEDULER_TICK_SECONDS`
- `.gitignore` (repo root) and `backend/.gitignore` — ignore the runtime `backups/` directory (alongside `storage/uploads/`)
- `AGENTS.md` — one line under "Module Notes" for `backups/` and the new settings keys

Frontend (paths relative to repo root):
- `dms-app/src/App.tsx` — route `/admin/backups` → `BackupsPage` (inside the protected block, next to `/admin/audit-trail`)
- `dms-app/src/components/layout/Sidebar.tsx` — "Backups" nav item in the admin section (same gating as Audit Trail / Company Profile)

## Files to create
- `backups/__init__.py`
- `backups/models.py` — `BackupRun` table model + read schemas `BackupRunRead`, `BackupRunListResponse`, `BackupSettingsRead`
- `backups/schemas.py` — write schemas `BackupSettingsUpdate` (`enabled: bool`, `interval_hours: int` 1–168, `retention_count: int` 1–100)
- `backups/service.py` — class-based `BackupService(session)`: `run_backup(company, user, trigger)`, `list_runs`, `get_run`, `download_path`, `get_settings`, `update_settings`, `_prune_retention(company)`; plus the scheduler-facing function `run_due_backups(engine)` that opens its own `Session(engine)`
- `backups/router.py` — thin FastAPI router; all endpoints take `AdminUser` and delegate to the service
- `backups/scheduler.py` — async tick loop (`asyncio` task, `BACKUP_SCHEDULER_TICK_SECONDS` cadence): never raises, logs via `logging.getLogger("dms.backups")`, builds zips via `asyncio.to_thread` so the event loop is never blocked, cancels cleanly on shutdown
- `migrations/versions/20261021_0900_add_backup_runs.py` — creates `backup_runs` (down_revision `20261018_153000`; replace the time part with the actual creation time)
- `tests/test_backup.py` — endpoint tests + company-isolation tests (backup is company-scoped, so isolation lives here rather than growing an existing file)
- `dms-app/src/api/backups.api.ts` — `apiClient` from `./client`
- `dms-app/src/types/backup.types.ts`
- `dms-app/src/pages/BackupsPage.tsx` — run history table (status, trigger, started/finished, file count, size, error), "Run backup now" button, download link, settings form

## New dependencies
No new dependencies. Backend uses stdlib only (`zipfile` with `ZIP_DEFLATED`, `shutil`, `asyncio`, `logging`); frontend uses existing libraries.

## Rules for implementation
- Use FastAPI + SQLModel only
- Use existing project architecture (backend modules: `auth/`, `users/`, `categories/`, `directories/`, `documents/`, `user_levels/`, `audit/`)
- Each backend module follows: `models.py` (SQLModel + Pydantic read schemas), `schemas.py` (request/response schemas), `service.py` (business logic, class-based, takes Session), `router.py` (FastAPI router)
- Keep routers thin; business logic belongs in services
- Use `CurrentUser` from `core/dependencies.py` for user injection
- Use `AdminUser` for admin-only endpoints (all six backup routes are admin-level; `AdminUser` admits ADMIN + SUPERADMIN, the service layer applies company scoping)
- Add new endpoints to `ROUTE_PERMISSION_MAP` in `middleware/rbac.py` (entries listed under "Files to change")
- Use SQLModel / parameterized queries only
- Use JWT access + refresh token auth (core/security.py)
- Hash passwords with bcrypt 4.0.1 (do not upgrade)
- Python: 4-space indent, `snake_case`
- TypeScript: 2-space indent, `PascalCase` components, `camelCase` hooks/stores
- Frontend API files import `apiClient` from `./client`, not `apiRoot` from `./base`
- Never expose secrets or sensitive data in logs (backup error details go to the DB row + `dms.backups` logger; no credential or full environment logging)
- Use `.env` for configuration only (never commit `.env`)
- Maintain audit trail via `AuditService.log_event()` (audit/service.py) — log `CREATE_BACKUP` (manual + scheduled), `BACKUP_FAILED`, `DOWNLOAD_BACKUP`, `UPDATE_BACKUP_SETTINGS`, with `company_id` set (scheduled runs have `user=None`)
- Audit logs are immutable (no PUT/PATCH/DELETE endpoints)
- Tests use SQLite in-memory; patch `engine` in `core.database`, `middleware.rbac`, `middleware.audit` — plus any new module binding `engine` at import time (`backups.scheduler`)
- Azure AD: use `cryptography` library for JWK parsing (not `jwk.construct()`)
- No new dependencies unless explicitly approved
- Add/update tests for every implemented feature

### Feature-specific constraints
- **Archive location:** `BACKUP_ROOT/<short_name>/backup_<YYYYmmddTHHMMSSZ>.zip` (UTC). `BACKUP_ROOT` must resolve **outside** `STORAGE_ROOT` (same `APP_ROOT`-relative resolution as `core/storage.py::StorageService.storage_root`) so a backup can never contain itself and storage-usage/quota accounting (spec 08) is not double-counted. The default value must also never collide with the `backups/` module directory — runtime data stays out of the source tree (default: `backups_data`).
- **Path safety:** build the company directory from `storage_service._validate_short_name(company.short_name)` (or an equivalent reuse) — never raw string concatenation; store `archive_path` POSIX-relative to `BACKUP_ROOT`; resolve downloads through the same validation (path-traversal guard). Zip arcnames are relative to the company root (`uploads/...`, `memos/...`, ...) so unzipping restores the exact folder tree.
- **Missing source:** a missing/empty company root records `status=failed` with a clear `error_message` and logs a WARNING like `resolve_path` does — never crash the loop or the request.
- **Memory:** stream members into the zip (chunked copy of open file handles), never read whole files into memory.
- **Company isolation:** ADMIN is auto-scoped to `current_user.company_id`; another company's run id → 404 (non-admin denials are 404 by design); SUPERADMIN reads all companies (optional `company_id` filter) with no param — SUPERADMIN fails read at service layer per repo invariant.

## Definition of done
- [ ] `alembic upgrade head` applies cleanly and creates `backup_runs` (head chain still rooted at `20261018_153000`)
- [ ] `python seed.py` is idempotent and seeds `backup_enabled` / `backup_interval_hours` / `backup_retention_count`
- [ ] Admin clicks "Run backup now" (or `POST /api/v1/backups/run`) → a zip appears under `<BACKUP_ROOT>/<short_name>/`, and the run row shows `success` with correct `file_count` / `total_bytes` / `archive_size_bytes`
- [ ] `GET /api/v1/backups` returns only the caller's company runs for ADMIN; SUPERADMIN sees all companies and can filter with `?company_id=`
- [ ] `GET /api/v1/backups/{id}` and `/download` for another company's run return 404 (not 403)
- [ ] `POST /run` as SUPERADMIN returns 403; as a non-admin (maker/auditor) returns 403; without a token returns 401 (RBAC middleware map active)
- [ ] `GET /backups/{id}/download` streams the zip; after retention pruning it returns the explicit "retention policy" 404
- [ ] `GET`/`PUT /backups/settings` round-trip values; out-of-range `interval_hours`/`retention_count` return 422; the PUT is audited
- [ ] With `backup_enabled=true` and a due company, a direct call to `run_due_backups` creates a `scheduled` run; with `backup_enabled=false` it creates none; with `BACKUP_SCHEDULER_ENABLED=false` no loop ever starts (verified: tests never trigger scheduled runs)
- [ ] After three successful runs with `retention_count=2`, exactly two archives exist on disk and the oldest row has `archive_path = NULL`
- [ ] A forced failure (e.g., monkeypatched zip writer raising) yields `status=failed` + `error_message`, HTTP 200 on manual trigger, an audit `BACKUP_FAILED` row, and the app keeps serving requests
- [ ] Audit rows exist for manual trigger, scheduled run, download, failure, and settings update, each with the right `company_id`
- [ ] Unzipping an archive reproduces the company folder tree (`uploads/`, `memos/`, `signatures/`, `correspondence/`)
- [ ] `pytest tests/test_backup.py -q` passes, including cross-company isolation cases
- [ ] No regression in the wider suite beyond the known baseline (2 failures: `test_workflow.py::TestApprovalActionService::test_parallel_step_any_approve_completes`, `test_workflow_company.py::TestSuperAdminCategoryRestrictions::test_superadmin_cannot_modify_category_ids`)
- [ ] Frontend: `/admin/backups` reachable from the sidebar (admin-only), shows history with status badges, Run Now, download, and settings form
- [ ] `cd dms-app && npm run build` passes (typecheck)
- [ ] `cd dms-app && npm run lint` passes (0 errors)
