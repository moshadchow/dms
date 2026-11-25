# Spec: PostgreSQL Scheduled Backup Service

## Overview
This feature adds a dedicated, scheduled PostgreSQL backup service that dumps the whole `dms_db` database with `pg_dump` into a separate `DB_BACKUP_ROOT` on a configurable cadence and on demand, records every attempt in a `db_backup_runs` table, streams dumps for restore, prunes them by a retention policy, and writes each event to the audit trail. Spec 35 already protects the *file* half of the system (each company's `STORAGE_ROOT/<short_name>/` tree), but a restore from those archives alone would resurrect documents without their metadata — no categories, no users, no workflows, no correspondence register, no audit history — because all of that lives in PostgreSQL. At this stage of the roadmap the DMS is a multi-tenant regulated system behind production TLS/rate limiting (specs 30/31) with a working folder-backup story (spec 35), so closing the remaining half of disaster recovery with the same self-contained, in-process, single-uvicorn-worker pattern is the natural next hardening step.

## Depends on
- Spec 19: Company-Wise Audit Trail (`AuditService.log_event`, plain-string `audit_logs.action`/`module` so new enum members need no migration)
- Spec 21: Company-Based Document Storage Structure (path resolution/validation discipline reused for the dump root)
- Spec 31: Rate Limiting (precedent for in-process background work on the single uvicorn worker)
- Spec 35: Automated Company-Wise Folder Backup (`backups/` module, `system_settings` key/value schedule pattern, scheduler + retention + run-history shape that this module deliberately mirrors)
- `storage_usage/models.py::SystemSetting` — the existing admin-configurable settings store
- Alembic migration chain — current head `20261021_0900`
- The PostgreSQL server already required by the app (`psycopg2-binary` in `requirements.txt`) — `pg_dump` ships with it

## Routes
All new routes are registered at `/api/v1/db-backups` (tag "Database Backups").

**Every route is SUPERADMIN-only.** A `pg_dump` of `dms_db` contains every company's rows in one file — a *company* ADMIN downloading it would be a cross-tenant data leak, which is exactly what the company-scoping invariant exists to prevent. The guard is the `SuperAdminUser` parameter annotation (authoritative, per-endpoint); the `ROUTE_PERMISSION_MAP` entries are only the coarse pre-filter.

- `GET /api/v1/db-backups` — paginated dump run history (status, trigger, started/finished, duration, size, error), newest first; SUPERADMIN reads across the deployment, so no `company_id` filter exists — access level: admin (SUPERADMIN only — `SuperAdminUser` + VIEW)
- `GET /api/v1/db-backups/{id}` — single run detail; an unknown id returns 404 — access level: admin (SUPERADMIN only — `SuperAdminUser` + VIEW)
- `POST /api/v1/db-backups/run` — run a dump now and return the finished run (HTTP 200; `status` may be `failed` — failure is data, not an error response); returns 409 if a dump is already `running` — access level: admin (SUPERADMIN only — `SuperAdminUser` + CREATE)
- `GET /api/v1/db-backups/{id}/download` — stream the `.dump` file; a dump pruned by retention returns 404 with an explicit reason — access level: admin (SUPERADMIN only — `SuperAdminUser` + DOWNLOAD)
- `GET /api/v1/db-backups/settings` — read schedule settings (`enabled`, `interval_hours`, `retention_count`) — access level: admin (SUPERADMIN only — `SuperAdminUser` + VIEW)
- `PUT /api/v1/db-backups/settings` — update schedule settings — access level: admin (SUPERADMIN only — `SuperAdminUser` + UPDATE)

A non-superadmin token (including an ADMIN token) on any of these returns **403**; no token returns 401.

## Database changes
New table `db_backup_runs` (deployment-scoped — **no `company_id`**, because the dump spans every company):

| column | type | notes |
|---|---|---|
| `id` | int PK | |
| `status` | str(20), indexed | `pending` \| `running` \| `success` \| `failed` (plain string, no DB enum) |
| `trigger` | str(10) | `manual` \| `scheduled` |
| `triggered_by` | int FK `users.id`, nullable | NULL for scheduled runs |
| `started_at` | datetime, nullable | |
| `finished_at` | datetime, nullable | |
| `dump_path` | str(500), nullable | POSIX, relative to `DB_BACKUP_ROOT` (e.g. `dms_20261022T093000Z.dump`); NULL = pruned by retention |
| `dump_size_bytes` | int, nullable | file size on disk |
| `duration_ms` | int, nullable | wall-clock duration of the `pg_dump` subprocess |
| `pg_dump_version` | str(60), nullable | `pg_dump --version` output — records which client produced the archive (restore compatibility) |
| `error_message` | str(500), nullable | set when `status=failed`; never contains a password |
| `created_at` | datetime, indexed | |

Index on `created_at`; no composite index (single-tenant-per-file is not a dimension here).

Schedule settings **reuse the existing `system_settings` table** (`storage_usage/models.py::SystemSetting`) with three new keys seeded idempotently in `seed.py`: `db_backup_enabled` = `"true"`, `db_backup_interval_hours` = `"24"`, `db_backup_retention_count` = `"7"`.

One new Alembic revision, date-prefixed per `alembic.ini` `file_template` (e.g. `migrations/versions/20261022_1000_add_db_backup_runs.py`), `revision = '20261022_1000'`, `down_revision = '20261021_0900'` — **replace the time part with the actual creation time**. The new `AuditAction`/`AuditModule` members need no migration (`audit_logs.action`/`module` are plain strings, `max_length=50`).

## Templates
No Jinja2 templates — frontend is React/Vite SPA. Frontend changes are listed under "Files to change" / "Files to create".

## Files to change
Backend (paths relative to `backend/`):
- `main.py` — import and include `db_backups.router` at `f"{API}/db-backups"` (tag "Database Backups"); in `lifespan`, start the DB backup scheduler task when `settings.DB_BACKUP_SCHEDULER_ENABLED`, and cancel it on shutdown alongside the existing folder-backup scheduler
- `core/config.py` — add:
  - `DB_BACKUP_ROOT: str = "db_backups_data"` — resolved against `APP_ROOT` exactly like `STORAGE_ROOT`/`BACKUP_ROOT` (relative → `APP_ROOT`, absolute as-is), and **must sit outside both `STORAGE_ROOT` and `BACKUP_ROOT`**. The default deliberately avoids the bare name `db_backups` so runtime data can never collide with the `db_backups/` Python module directory.
  - `DB_BACKUP_SCHEDULER_ENABLED: bool = True`, `DB_BACKUP_SCHEDULER_TICK_SECONDS: int = 300`
  - `PG_DUMP_PATH: str = "pg_dump"` — absolute path or bare name on `PATH`; lets a server pin a specific major version's client
  - `PG_DUMP_TIMEOUT_SECONDS: int = 3600` — a hung dump is killed and recorded as `failed`, never left `running` forever
- `core/database.py` — `import db_backups.models` in `create_db_and_tables()` (no FK to `companies`, so ordering is not critical, but keep it after the other model imports)
- `middleware/rbac.py` — add to `ROUTE_PERMISSION_MAP` (GET also covers `/{id}` and `/{id}/download` via longest-prefix match, same as spec 35's entries):
  - `("GET", "/api/v1/db-backups") → PermissionAction.VIEW`
  - `("POST", "/api/v1/db-backups") → PermissionAction.CREATE`
  - `("PUT", "/api/v1/db-backups") → PermissionAction.UPDATE`
- `audit/models.py` — add `AuditAction.CREATE_DB_BACKUP = "create_db_backup"`, `DB_BACKUP_FAILED = "db_backup_failed"`, `DOWNLOAD_DB_BACKUP = "download_db_backup"`, `UPDATE_DB_BACKUP_SETTINGS = "update_db_backup_settings"`; add `AuditModule.DB_BACKUPS = "db_backups"`
- `seed.py` — idempotently seed the three `db_backup_*` SystemSetting keys (same style as the existing `backup_*` block)
- `tests/conftest.py` — in the `client` fixture: `monkeypatch.setattr(core.database.settings, "DB_BACKUP_SCHEDULER_ENABLED", False)` (a `TestClient` runs lifespan), point `DB_BACKUP_ROOT` at `tmp_path / "db_backups"`, set `PG_DUMP_PATH` to a path guaranteed not to exist (so no test ever shells out to a real `pg_dump`), and `monkeypatch.setattr(db_backups.scheduler, "engine", engine)` — that module binds `engine` at import time
- `.env.example` (repo root) — document `DB_BACKUP_ROOT`, `DB_BACKUP_SCHEDULER_ENABLED`, `DB_BACKUP_SCHEDULER_TICK_SECONDS`, `PG_DUMP_PATH`, `PG_DUMP_TIMEOUT_SECONDS`
- `.gitignore` (repo root) and `backend/.gitignore` — ignore the runtime `db_backups_data/` directory
- `AGENTS.md` — one line under "Module Notes" for `db_backups/`, the new settings keys, and the SUPERADMIN-only rule

Frontend (paths relative to repo root):
- `dms-app/src/App.tsx` — route `/admin/db-backups` → `DbBackupsPage` (inside the protected block, next to `/admin/backups`)
- `dms-app/src/components/layout/Sidebar.tsx` — "Database Backups" nav item gated on `isSuperAdmin()` (the store already exposes it), next to the existing Backups item

## Files to create
- `db_backups/__init__.py`
- `db_backups/models.py` — `DbBackupRun` table model + read schemas `DbBackupRunRead`, `DbBackupRunListResponse`, `DbBackupSettingsRead`
- `db_backups/schemas.py` — write schema `DbBackupSettingsUpdate` (`enabled: bool`, `interval_hours: int` 1–168, `retention_count: int` 1–100)
- `db_backups/service.py` — class-based `DbBackupService(session)`: `run_manual_dump(user)`, `run_dump(trigger, user)`, `list_runs`, `get_run`, `download_path`, `get_settings`, `update_settings`, `_execute(run)`, `_prune_retention()`; plus module-level helpers `get_db_backup_root()`, `_parse_database_url()`, `_run_pg_dump(target_path)` and the scheduler entry point `run_due_db_backups(engine)` that opens its own `Session(engine)`
- `db_backups/router.py` — thin FastAPI router; every endpoint takes `SuperAdminUser` and delegates to the service
- `db_backups/scheduler.py` — async tick loop (`asyncio` task, `DB_BACKUP_SCHEDULER_TICK_SECONDS` cadence, task name `db-backup-scheduler`): sleeps, then calls `run_due_db_backups(engine)` inside `asyncio.to_thread` (a dump must never block the event loop), logs via `logging.getLogger("dms.db_backups")`, swallows and logs every non-cancellation exception, cancels cleanly on shutdown; binds `core.database.engine` at import time so `tests/conftest.py` can patch it
- `migrations/versions/<YYYYMMDD_HHMM>_add_db_backup_runs.py` — creates `db_backup_runs` (`down_revision = '20261021_0900'`)
- `tests/test_db_backup.py` — endpoint, authorization, retention, scheduler and failure tests (this feature is deployment-scoped rather than company-scoped, so it does not belong in the company-isolation files)
- `dms-app/src/api/dbBackups.api.ts` — `apiClient` from `./client`
- `dms-app/src/types/dbBackup.types.ts`
- `dms-app/src/pages/DbBackupsPage.tsx` — run history table (status, trigger, started/finished, duration, size, error), "Run backup now" button, download link, settings form

## New dependencies
No new backend or frontend packages. The service shells out to `pg_dump` via the standard library `subprocess` — `pg_dump` is a binary that ships with the PostgreSQL server already required by `requirements.txt` (`psycopg2-binary`); it is not a pip dependency. If it is absent, the run is recorded as `failed` with a clear `error_message` and nothing crashes.

## Rules for implementation
- Use FastAPI + SQLModel only
- Use existing project architecture (backend modules: `auth/`, `users/`, `categories/`, `directories/`, `documents/`, `user_levels/`, `audit/`)
- Each backend module follows: `models.py` (SQLModel + Pydantic read schemas), `schemas.py` (request/response schemas), `service.py` (business logic, class-based, takes Session), `router.py` (FastAPI router)
- Keep routers thin; business logic belongs in services
- Use `CurrentUser` from `core/dependencies.py` for user injection
- Use `AdminUser` for admin-only endpoints — **for this feature use `SuperAdminUser` on every route** (a database dump spans all tenants; see Routes)
- Add new endpoints to `ROUTE_PERMISSION_MAP` in `middleware/rbac.py` (entries listed under "Files to change")
- Use SQLModel / parameterized queries only
- Use JWT access + refresh token auth (core/security.py)
- Hash passwords with bcrypt 4.0.1 (do not upgrade)
- Python: 4-space indent, `snake_case`
- TypeScript: 2-space indent, `PascalCase` components, `camelCase` hooks/stores
- Frontend API files import `apiClient` from `./client`, not `apiRoot` from `./base`
- Never expose secrets or sensitive data in logs (the DB password is passed only through the child process's `PGPASSWORD` environment variable — never in argv, never in `logger.*` output, never in `error_message`; if it ever appears in stderr, strip it before persisting)
- Use `.env` for configuration only (never commit `.env`)
- Maintain audit trail via `AuditService.log_event()` (audit/service.py) — log `CREATE_DB_BACKUP` (manual + scheduled), `DB_BACKUP_FAILED`, `DOWNLOAD_DB_BACKUP`, `UPDATE_DB_BACKUP_SETTINGS`, all with `company_id=None` (deployment-scoped) and `user=None` for scheduled runs
- Audit logs are immutable (no PUT/PATCH/DELETE endpoints)
- Tests use SQLite in-memory; patch `engine` in `core.database`, `middleware.rbac`, `middleware.audit` — plus `db_backups.scheduler`, which binds `engine` at import time
- Azure AD: use `cryptography` library for JWK parsing (not `jwk.construct()`)
- No new dependencies unless explicitly approved
- Add/update tests for every implemented feature

### Feature-specific constraints
- **Dump location:** `DB_BACKUP_ROOT/dms_<YYYYmmddTHHMMSSZ>.dump` (UTC). `DB_BACKUP_ROOT` resolves against `APP_ROOT` exactly like `core/storage.py::StorageService.storage_root` and must sit **outside** `STORAGE_ROOT` and outside `BACKUP_ROOT` — verified with a `relative_to` check that raises at startup time, mirroring `backups/service.py::_company_backup_dir`. There is no per-company subdirectory: one database, one flat directory.
- **Format:** `pg_dump --format=custom --no-owner --no-privileges` (compressed, restorable with `pg_restore`). Write to a temporary file in the same directory and `os.replace()` it into place, so an interrupted dump can never be mistaken for a complete one or downloaded as one.
- **Credentials:** parse `settings.DATABASE_URL` with `urllib.parse` and strip the SQLAlchemy driver suffix (`postgresql+psycopg2://` → `postgresql://`). Pass host/port/user/dbname as argv; pass the password **only** as `PGPASSWORD` in the subprocess environment. Never build a `.pgpass` file and never interpolate the password into a shell string — `subprocess.run` with an argv list, `shell=False`.
- **Failure is data:** a missing `pg_dump` binary, a wrong password, a timeout, or a non-zero exit all set `status=failed` + `error_message` and return HTTP 200 on manual trigger (same discipline as spec 35). The scheduler loop and the request both keep serving; nothing propagates out of the tick.
- **Guard ordering:** a run already `running` → 409. Non-superadmin → 403 at the endpoint annotation. There is no `company_id` and no company-scoping code path — do not add one.
- **Retention:** keep the newest `retention_count` dump **files**; older files are deleted and their rows survive with `dump_path = NULL`, so run history and audit remain intact (mirrors `backups/service.py::_prune_retention`).
- **Scheduler:** `run_due_db_backups(engine)` returns 0 immediately when `db_backup_enabled` is not `true`, and considers a run "due" when the newest `db_backup_runs` row (any status) is older than `db_backup_interval_hours` — a failed run counts as a recent attempt so a persistent failure cannot retry-storm the worker.
- **Test isolation:** no test may execute a real `pg_dump`. `conftest` points `PG_DUMP_PATH` at a non-existent file; tests exercise the executor by monkeypatching `db_backups.service._run_pg_dump` (success, non-zero exit, `FileNotFoundError`, timeout).
- **Company scoping does not apply:** `db_backup_runs` has no `company_id`, so `list_runs` takes no company filter. Do not force the spec 35 `list_for_user` shape onto it.

## Definition of done
- [ ] `alembic upgrade head` applies cleanly and creates `db_backup_runs` (chain rooted at `20261021_0900`)
- [ ] `python seed.py` is idempotent and seeds `db_backup_enabled` / `db_backup_interval_hours` / `db_backup_retention_count`
- [ ] `POST /api/v1/db-backups/run` as SUPERADMIN with `pg_dump` available → a `.dump` file appears under `DB_BACKUP_ROOT/`, the run row shows `success` with correct `dump_size_bytes` / `duration_ms` / `pg_dump_version`, and only that file exists (no `.part`/temp leftovers)
- [ ] The produced file is a valid custom-format archive: `pg_restore --list <file>` succeeds
- [ ] `GET /api/v1/db-backups` lists runs newest first with pagination (`total`/`page`/`limit`)
- [ ] `GET /api/v1/db-backups/{id}` and `/{id}/download` for an unknown id return 404; after retention pruning, `/download` returns the explicit "retention policy" 404
- [ ] `POST /run` while another dump is `running` returns 409
- [ ] Every route with an ADMIN or MAKER token returns **403**; without a token returns **401** (RBAC map active, `SuperAdminUser` authoritative)
- [ ] `GET`/`PUT /db-backups/settings` round-trip values; out-of-range `interval_hours`/`retention_count` return 422; the PUT is audited
- [ ] The DB password never appears in argv, in any log line, or in `error_message` — verified by a test that greps the recorded failure text and the captured `subprocess.run` argv for the password value
- [ ] With `db_backup_enabled=true` and no prior run, a direct call to `run_due_db_backups(engine)` creates a `scheduled` run; with `db_backup_enabled=false` it creates none; with `DB_BACKUP_SCHEDULER_ENABLED=false` no loop ever starts (tests never trigger scheduled runs)
- [ ] After three successful dumps with `retention_count=2`, exactly two files exist on disk and the oldest row has `dump_path = NULL`
- [ ] A forced failure (monkeypatched `_run_pg_dump` raising `FileNotFoundError`, or returning non-zero stderr) yields `status=failed` + `error_message`, HTTP 200 on manual trigger, an audit `DB_BACKUP_FAILED` row, and the app keeps serving requests
- [ ] `PG_DUMP_TIMEOUT_SECONDS` exceeded → the subprocess is killed, the run is `failed` with a timeout message, and no `running` row is left behind
- [ ] Audit rows exist for manual trigger, scheduled run, download, failure, and settings update, each with `company_id = None` and the correct `user`
- [ ] `pytest tests/test_db_backup.py -q` passes, including the 403/401 authorization matrix and the password-leak check
- [ ] No regression in the wider suite beyond the known baseline (2 failures: `test_workflow.py::TestApprovalActionService::test_parallel_step_any_approve_completes`, `test_workflow_company.py::TestSuperAdminCategoryRestrictions::test_superadmin_cannot_modify_category_ids`)
- [ ] Frontend: `/admin/db-backups` reachable from the sidebar for SUPERADMIN, hidden for ADMIN/MAKER/CHECKER/AUDITOR; shows history with status badges, Run Now, download, and the settings form
- [ ] `cd dms-app && npm run build` passes (typecheck)
- [ ] `cd dms-app && npm run lint` passes (0 errors)
