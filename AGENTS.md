# Repository Guidelines

FastAPI backend at repo root + React/Vite SPA in `dms-app/`. Python 4-space/`snake_case`; TypeScript 2-space, `PascalCase` components, `camelCase` hooks/stores.

## Commands

Backend (run from repo root, `venv/` is the working interpreter):
```
alembic upgrade head          # apply migrations — REQUIRED; run before first boot
python seed.py                # roles, permissions, user levels, SuperAdmin — once, after migrate
uvicorn main:app --reload     # dev server on :8000
pytest                        # full suite
pytest tests/test_correspondence.py             # one file
pytest tests/test_correspondence.py::TestCorrespondenceReply   # one class
pytest -q -k mark_responded                    # one test by name
```
There is **no** Python linter/formatter installed. Do not claim lint passed.

Frontend:
```
cd dms-app
npm install
npm run dev      # Vite on :5173, proxies /api to :8000
npm run build    # tsc && vite build — this IS the typecheck step
npm run lint     # ESLint
```

Copy `.env.example` → `.env`. Never commit `.env`. There are **no** Azure AD credentials in `.env` — Entra ID config is per company, in the database.

## Spec-Driven Workflow
Features are numbered steps. Specs live in `specs/NN-kebab-slug.md` (older `feature_*`/`instruction_*` files are legacy); `/create-spec` (`.opencode/commands/create-spec.md`, mirrored in `.claude/commands/`) scaffolds the next one with a required structure (Overview / Depends on / Routes / Database changes / Files to change / Files to create / New dependencies / Rules for implementation / Definition of done). Check `specs/` for the highest number before starting new work. There is no `plans/` directory — do not create one.

## Migrations
`alembic.ini` `file_template` is `%%(year)d%%(month).2d%%(day).2d_%%(rev)s_%%(slug)s` — new revisions are **date-prefixed** (`20260921_1559_add_x.py`). `migrations/env.py` overwrites `sqlalchemy.url` from `.env`; the URL in `alembic.ini` is dead config.

Any model change needs a migration. **Never** rely on `DEBUG=True` in a shared/dev DB to build the schema (see below).

**Enum columns: a migration's `server_default` must use the enum's `.name` (UPPERCASE), not `.value`.** SQLModel maps `field: SomeStrEnum` to `sa.Enum`, which writes *and* expects the member's name — so a row storing `'pending'` comes back as `LookupError: 'pending' is not among the defined enum values. Possible values: PENDING, RUNNING, ...` (verified against Postgres, not just SQLite). These columns are declared as plain `sa.String(n)` in the migrations while the model type is `sa.Enum` — a DDL/type mismatch that is benign in itself (no CHECK is emitted, and the Python model always sets the value, so the column default is normally bypassed) but is exactly why a lowercase default survives unnoticed until something inserts relying on the default (raw SQL, `op.execute`, or a nullable-omitted insert). **Latent and unfixed:** `20261021_0900_add_backup_runs.py` (spec 35) declares `status`/`trigger` with `'pending'`/`'manual'`; `20261022_1133_add_db_backup_runs.py` (spec 36) is the corrected `'PENDING'`/`'MANUAL'` form — copy that one.

## DB / Startup Invariant
`main.py`'s lifespan calls `create_db_and_tables()` when `DEBUG=True`, silently bypassing Alembic. It builds tables from SQLModel metadata only, so it will not apply column adds to existing tables. Production runs `DEBUG=false` + `alembic upgrade head` only.

Postgres in production (`requirements.txt`: `psycopg2-binary`).

## Config / Storage Root Invariant
`core/config.py` resolves its env file **without depending on the working directory**: the candidates are `<repo root>/.env` → `<app root>/.env` → `./.env` (last one wins, pydantic-settings). The app root is `core/config.py`'s parent's parent (`backend/` in the repo, `/var/www/dms` on the server) — it is where `main.py` lives. The repo-root `.env` is the documented location; the backend package sitting in `backend/` used to mean it was never found when the server was started from there, so **every setting silently fell back to its code default**.

`STORAGE_ROOT` is therefore the one to watch: a **relative** value resolves against the **app root**, never against the CWD (`core/storage.py::storage_service.storage_root`), so the same config yields the same tree regardless of where uvicorn was launched. An absolute value is used as-is (tests, containers). Code default is `storage`, `.env.example` sets `storage/uploads` — a mismatch moves the company root and makes every file read answer 404 "File not found on disk" (which reads like an access denial, but is not). Always read the root through `storage_service.storage_root`; never rebuild it from `settings.STORAGE_ROOT` by hand.

Stored `storage_path` values are **company-relative and POSIX** (`uploads/<category_id>/<directory_id>/<file>`). Rows written on Windows hold backslashes, which are literal filename characters on Linux — the resolver normalizes `\` → `/` at the single resolution point, and new rows are written with `as_posix()`.

## Testing: SQLite In-Memory
`tests/conftest.py` builds a `StaticPool` in-memory engine — **not** Postgres — and monkeypatches `engine` in four modules: `core.database`, `middleware.rbac`, `middleware.audit`, `notifications.tasks`, plus settings (`DEBUG=False`, `STORAGE_ROOT` → per-test temp dir, `SMTP_HOST=""` so no mail goes out). A new module that does `from core.database import engine` at import time bypasses the patch and hits the real DB; add it to the fixture.

Fixture shapes (easy to guess wrong):
- `client` yields a **tuple** `(test_client, engine, storage_path)` — not just a client.
- `seeded_data` returns id dict; two companies are seeded (`company_id` = "Test Company", `other_company_id` = "Other Company") plus a cross-company `other_admin`.
- `auth_headers` returns keys `admin`, `maker`, `superadmin`, `other_admin`. **There is no checker/auditor user** — create one in-test if a test needs one.

Company-isolation regressions are the norm here; they get their own file (`test_audit_company.py`, `test_category_company.py`, `test_workflow_company.py`, `test_user_visibility.py`, `test_company_assignment.py`). Add new company-scoped features there rather than growing `test_<feature>.py`.

**The suite is slow.** The `client` fixture rebuilds the whole schema on a fresh in-memory DB per test (~2 s setup), and `test_correspondence.py` alone takes ~5 min (100 tests) with PDF generation on top. A full run is ~20 min. Target a file/class while iterating, but budget a long run before declaring done.

**The full suite is not green — known baseline failures** (present on a clean checkout; do not chase them as your regressions): 2 failures (`test_workflow.py::TestApprovalActionService::test_parallel_step_any_approve_completes`, `test_workflow_company.py::TestSuperAdminCategoryRestrictions::test_superadmin_cannot_modify_category_ids`). Recent healthy runs: `2 failed, 686 passed` (the 2 are constant; passed grows with new tests).

The 14 errors that used to sit in `test_document_visibility.py` are **fixed** — its fixture created a `Role(...)` that seeded data already created (`roles.name` is UNIQUE) and gave its users no `company_id` (a user without a company can never pass `ensure_category_access`, so every category-scoped read 404'd). **Look up the seeded role, don't create one**, and give test users a company. A fixture that dies in setup hides the assertions behind it — that is how a document-read regression reached production unnoticed.

## Module Convention
`models.py` (SQLModel + read schemas) · `schemas.py` (write schemas, optional) · `service.py` (class-based, takes `Session`) · `router.py` (thin — business logic belongs in the service). Keep routers thin.

Exceptions live in `core/exceptions.py`; access guards in `core/access.py` (`ensure_category_access`, `ensure_directory_access`, `ensure_document_access`, `ensure_document_user_level_access`, plus read/navigation variants — see **Directory Navigation Access** below).

`documents/` has `DocumentService` + `DocumentVariantService`; `workflow/` has three routers in `router.py` — `router` (`/api/v1/workflows`), `instance_router` (`/api/v1/workflow-instances`), `signature_router` (`/api/v1/signatures`) — with services split into `definition_service.py` / `instance_service.py` / `approval_service.py` (`service.py` is a back-compat re-export shim) and shared approver logic in `approval_policy.py`.

## Company Scoping (cross-cutting, easiest thing to break)
`Company` is the tenancy boundary. `users`, `categories`, `correspondences` (and `workflow_definitions`, `audit_logs`, `memos`) carry a `company_id` FK. Enforced invariants, all covered by tests:
- **ADMIN** is auto-scoped to `current_user.company_id`. A client-supplied `company_id` in a payload is ignored, not rejected.
- An **ADMIN with no company** sees empty lists and is rejected on writes (e.g. `test_company_less_admin_rejected`).
- Rows with `company_id = NULL` are **invisible** to ADMIN and to regular users; they show only to SUPERADMIN.
- **SUPERADMIN** passes authorization guards but is denied at the *service* layer for mutations (403). It can only read, and needs an explicit `company_id` query param to scope — with no param it sees all companies (audit logs: empty until a company is chosen).
- `Company.short_name` is the storage namespace and must match `[A-Za-z0-9_-]+`; it is validated on every path build.

`AdminUser` is an **authorization** guard, not a visibility guard — it admits both ADMIN and SUPERADMIN. Visibility hiding is done in the service (`users/service.py` `list_users()`).

## Directory Navigation Access (direct vs navigation vs content)
`core/access.py` separates three tiers — do not collapse them:
- **Direct access** (`ensure_directory_access`, `ensure_category_access`): category grant or grant covering self/ancestors. Required for ALL writes (upload, directory rename/delete, memo attach) and for document detail/view/download.
- **Navigation access** (`can_navigate_directory` / `ensure_directory_read_access`): read-only traversal of a parent with ≥1 accessible descendant (recursive, recomputed per request — revoking the last covering grant removes it). The directory's category must be active and same-company. Served with `navigation_only: true` on `DirectoryRead`/`DirectoryNode`.
- **Category metadata** (`ensure_category_read_access`, used **only** by `CategoryService.get_category`): directory-grant users may read a category holding one of their grants (page headers). Never use it for content guards — correspondence/memos keep strict `ensure_category_access`.

Nav-aware read paths are exactly: `GET /directories/{id}`, `list_by_category` roots, pruned `get_tree`, and the `directory_id`/`category_id` filters in `DocumentService.list_documents` (its `access_filters` + user-level filter still scope rows, so a nav-only parent lists 0 items). Partial-category `directory_count`/`document_count` in `list_categories` are scoped to granted subtrees, never whole-category totals.

Non-admin denials return **404, not 403** (oracle avoidance) — a 404 on these endpoints is the guard working, not a bug. The frontend's `isAccessDeniedError` maps 403/404 → `/forbidden`, so never "fix" a denial by suppressing 404s client-side. Tests: `tests/test_directory_navigation.py` (cross-company case lives in `test_directory_access_company.py`). Verify end-to-end through real `POST /auth/login` + `GET /auth/me` — minted-token replays bypass the frontend gate and once missed a real `/forbidden` bug.

## Company-Scoped Storage
`core/storage.py` `StorageService` (module singleton `storage_service`) owns all path building. Layout: `STORAGE_ROOT/<short_name>/{uploads,memos,signatures,correspondence}/`.

**Always resolve through `documents/utils.py::resolve_storage_path(relative_path, company)`** — never `STORAGE_ROOT / relative_path` by hand. It validates the resolved path stays under the company root (path-traversal guard) and 404s if absent. `resolve_path_with_fallback` tries the company-prefixed path first, then the legacy non-prefixed path, for pre-migration files. `delete_from_disk` is idempotent. `scripts/migrate_storage.py` and `scripts/fix_storage_paths.py` backfill the layout.

A **missing file and a misconfigured root both surface as a bare 404**, which is indistinguishable from an access denial (non-admin denials are 404 by design — see *Company Scoping*). `resolve_path` logs `dms.storage` WARNING when the *company root itself* is missing — check the server log before assuming a permissions problem. Regression coverage: `tests/test_storage_root.py`.

## RBAC: two layers
1. `middleware/rbac.py` `ROUTE_PERMISSION_MAP` maps `(HTTP_METHOD, path_prefix)` → `PermissionAction`, matched by **longest prefix** — so a broad prefix covers its subpaths (e.g. in `correspondence/` both `POST .../{id}/...` and `DELETE .../{id}/...` resolve to `UPDATE`). A new **top-level prefix** with no entry is silently skipped by the middleware (only per-endpoint guards remain), so add one. Paths under `PUBLIC_PATH_PREFIXES` (`/api/v1/auth`, `/docs`, `/redoc`, `/openapi.json`, `/health`) bypass it entirely.
2. Per-endpoint `dependencies=[Depends(require_permission(PermissionAction.X))]` in the router.

Do not invent permission verbs — the matrix is fixed at `view`, `download`, `create`, `update`, `delete` (see Seed Data).

## Auth & User Injection
`core/dependencies.py` provides `CurrentUser` (inject the caller), `AdminUser` (ADMIN + SUPERADMIN), `AdminOnlyUser` (ADMIN, **rejects** SUPERADMIN — used by `categories/`), `SuperAdminUser` (SUPERADMIN only), `require_permission`. JWT access + refresh via `core/security.py`; `main.py` rewrites the OpenAPI security scheme to plain `HTTPBearer`.

## Audit Trail
`AuditService.log_event()` in `audit/service.py` is the **single** audit sink. It opens its own `Session(engine)` so logs commit even when the caller rolls back, and it never raises. Call it after every significant mutation in a service. Audit records are immutable — no PUT/PATCH/DELETE endpoints exist.

`middleware/audit.py` (registered after RBAC in `main.py`) auto-logs auth, 401/403, and document operations; those events have `company_id=None`.

`core/audit.py::log_audit_event` is dead code — do not add callers.

## Workflow / Approval
Status flow: `draft → submitted → pending_approval → (returned | rejected | approved | cancelled) → published? → archived`.

- Step edits never delete rows: `update_definition` **supersedes** them (`workflow_steps.is_active=False`) so completed instances keep their historical chain (`workflow_actions.workflow_step_id` keeps resolving), and only runs when no instance is `draft/submitted/pending_approval/returned` (409 otherwise). All step-resolution queries filter `is_active=True`. There is no physical per-instance step snapshot — the edit guard is what keeps in-flight instances untouched.
- Deactivating a definition blocks new submissions only.
- Definitions are category-agnostic (`document_category_id` was removed); category filtering happens at the document level. Multiple active definitions per category are allowed, so submission UIs need a picker.
- `workflow_history` is the approval ledger; `audit/` stays the system-wide log. Both are written, never a third mechanism.
- Approver eligibility (`workflow/approval_policy.py`) is admin-configured and does **not** filter by User Level (`resolve_eligible_user_ids`; `list_pending` shows instances regardless of level — note `approval_service.act` refuses MAKER-role users). In exchange, an eligible approver at the current step of an in-flight instance can **read** the document even when its User Level links exclude them: memos do this unconditionally in `_check_view_access`, correspondence via `approver_view=True` on read paths only (detail, by-document, movements, replies, downloads) — mutations keep the strict level guard (`is_eligible_current_approver`). The grant lapses once the instance leaves `submitted`/`pending_approval`.
- `documents/` read paths (detail, view, download — `DocumentService._ensure_read_level_access`) use `is_eligible_approver_reader`, which also traverses `memo_attachments`/`correspondence_attachments`: the instance lives on the *container's* backing document, not the attachment. `workspace`/variants keep the strict level guard. See `tests/test_document_approver_read.py`.
- Activation does not validate that steps/approvers exist; step-order uniqueness is enforced only by a DB constraint.
- **Duplicate-action guard** (`approval_service.py`): a repeated identical action by the same user at the same step → 409. Approve message is exactly `This record is already approved by the first approver.`; other actions get `You have already performed '<action>' on this step.` Enforced twice: pre-check `_ensure_no_duplicate_action` (friendly 409) and unique constraint `uq_workflow_actions_instance_step_user_action` on `workflow_actions (instance, step, acted_by, action)` (race backstop → `IntegrityError` → 409). **Guard ordering gotcha:** the instance-status guard (422, terminal status) and the eligibility guard (403) run *before* the duplicate check — so on a completed instance a repeat returns 422, not 409. To test duplicates you need an instance that stays actionable: a **sequential step with ≥2 approvers** (first approve leaves it `pending_approval`). Different action or different step never trips the guard.

## Module Notes
- **`user_levels/`** — `DocumentUserLevelLink` gates document visibility in `documents/service.py`; Admin bypasses. Non-admins only see documents linked to **their** level (list and detail both filter), and a document with **no** links is admin-only: excluded from lists, 403 `You do not have access to this document` on detail/download.
- **`memos/`** — markdown → HTML → reportlab PDF (`memos/pdf_generator.py`). Reportlab's `Paragraph` parser is strict about balanced tags, so `_apply_inline_formatting` strips italics to plain text and `_sanitize_for_reportlab()` removes malformed tags. `_check_edit_access`: terminal statuses are frozen; the author may edit any non-terminal status; eligible approvers only in `draft`/`returned`/`rejected`.
- **`correspondence/`** — inbound/outbound/internal register. Key facts: `document_id` is nullable; outbound/internal auto-generate an HTML backing document from `body`; **a category is required to attach files** (`_resolve_backing_directory`); `/{id}/download` falls back to the first attachment; `/{id}/download-final` renders a signed PDF (`correspondence/pdf_generator.py`). Status model is richer than workflow: `received/registered/assigned/processing → draft/submitted/pending_approval/… → ready_for_dispatch → dispatched → delivered → acknowledged → completed → archived` (`TERMINAL_STATUSES` in `service.py`; also frozen once `dispatch_method` is set). Replies: `POST /{parent_id}/reply`, `POST /{id}/submit-reply`, `POST /{id}/mark-responded`, `GET /{parent_id}/replies`, keyed on `parent_correspondence_id` + `response_received`/`responded_at`. All mutations append to `CorrespondenceMovement` (the timeline).
- **`notifications/`** — `EmailService` is fire-and-forget and never raises; `EmailNotification` rows give idempotency. SMTP via `core/config.py` `SMTP_*`.
- **`signatures/`** — JPEG/PNG, 5 MB, soft-delete, stored under the company `signatures/` root. Referenced by `signature_id` on workflow approvals.
- **`company_profile/`** — SUPERADMIN-only CRUD at `/api/v1/companies`; per-company Azure AD config at `/{id}/azure-config` (GET: own company or any for SUPERADMIN; PUT/DELETE: SUPERADMIN only; secret is write-only — absent from `CompanyRead`/`AzureConfigRead` and redacted in audit payloads; enabling requires client ID + secret + tenant ID). Company-scoped Azure login behavior lives under **Azure AD** below.
- **`storage_usage/`** — quota accounting, admin endpoints at `/api/v1/storage`.
- **`backups/`** — automated company-wise folder backups (spec 35). Each company's `STORAGE_ROOT/<short_name>/` tree is zipped to `BACKUP_ROOT/<short_name>/backup_<UTC>.zip`; `BACKUP_ROOT` resolves against the app root exactly like `STORAGE_ROOT` and **must stay outside `STORAGE_ROOT`** (no self-inclusion, no quota double-count) — the default is `backups_data`, deliberately **not** `backups`, because a relative `BACKUP_ROOT=backups` would write archives into the `backups/` module directory itself (this actually happened during development: the DEBUG-started scheduler zipped a company into the package dir). Runs live in `backup_runs`; the schedule policy lives in `system_settings` keys `backup_enabled` / `backup_interval_hours` / `backup_retention_count` (seeded by `seed.py`). The in-process asyncio tick loop starts in `main.py` lifespan only when `BACKUP_SCHEDULER_ENABLED` (single-uvicorn-worker assumption, spec 31 precedent) — conftest disables it because a TestClient runs lifespan, and also patches `backups.scheduler`'s `engine` (it binds at import). All six `/api/v1/backups` routes are admin-level (per-endpoint guard is the `AdminUser` **parameter annotation**, NOT `dependencies=[Depends(AdminUser)]` — that form mis-signatures and 422s); SUPERADMIN is read-only (`POST /run` → 403 at the service layer); another company's run id → 404; retention keeps the newest `retention_count` archives per company and prunes older files (rows survive with `archive_path = NULL`; downloading one → 404 "retention policy").
- **`db_backups/`** — PostgreSQL dumps of `dms_db` itself (spec 36), the database half of disaster recovery; spec 35 above archives the file tree, which cannot recover categories, users, workflows, correspondence or audit history. **Deployment-scoped: no `company_id` exists anywhere in the module** — one dump holds every company's rows, so a tenant ADMIN must never reach one. That inverts the spec 35 permission shape: all six `/api/v1/db-backups` routes are **SUPERADMIN-only** (`SuperAdminUser` parameter annotation — the same signature trap as spec 35's `AdminUser`; `dependencies=[Depends(...)]` 422s), the one deliberate exception to the "SUPERADMIN mutations are 403" invariant, and `ROUTE_PERMISSION_MAP` cannot enforce it because `User.is_admin()` lets ADMIN bypass the middleware entirely. **Registration order matters:** declare `GET/PUT /settings` *before* `/{run_id}` or FastAPI captures "settings" as an int path param → 422. Runs live in `db_backup_runs`; policy lives in `system_settings` keys `db_backup_enabled` / `db_backup_interval_hours` / `db_backup_retention_count` (seeded by `seed.py`; `get_settings()` defaults `enabled` to **true**, so a test wanting "off" must set it explicitly). `DB_BACKUP_ROOT` gets the same APP_ROOT-relative resolution and **must stay outside both `STORAGE_ROOT` and `BACKUP_ROOT`**; the default is `db_backups_data`, again **not** the bare module name. `main.py`'s lifespan *logs loudly* rather than raising on a bad root (a backup misconfig must not stop the DMS serving documents) — the authoritative guard runs inside `get_db_backup_root()`, which every dump/download calls before any write, so a bad root degrades to `status=failed` and is never written to. **The password travels only in the child's `PGPASSWORD` env var** — never argv, never a log line, never `error_message`; `_redact()` strips the plain and URL-encoded forms from every persisted string. `_execute` writes `<name>.dump.part` then `os.replace()`s it, so an interrupted dump is never mistaken for (or downloadable as) a complete one, and the `.part` is always unlinked. Failure is **data, not an error**: HTTP 200 with `status:"failed"`; the only HTTP error raised is 409 when a run is already in flight. Retention prunes the oldest *files*; their rows survive with `dump_path = NULL` and download → 404 "retention policy". A second, **independent** asyncio tick loop (`db_backups/scheduler.py`, task name `db-backup-scheduler`, gated by `DB_BACKUP_SCHEDULER_ENABLED`) — separate from spec 35's so the two can be enabled/disabled without affecting each other; it uses `asyncio.to_thread` because a dump can take minutes, and it **quietly skips** when a run is already `RUNNING` (no 409 storm). `tests/conftest.py` disables it and patches `db_backups.scheduler`'s `engine` (it binds at import), and points `PG_DUMP_PATH` at a file that cannot exist — **`db_backups.service._run_pg_dump` is the single seam tests monkeypatch; no test ever shells out.** See `tests/test_db_backup.py`. Frontend: `/admin/db-backups` (`DbBackupsPage`), nav-gated behind `isSuperAdmin()`.

## Azure AD
**Company-scoped and database-driven — there is no global `.env` fallback** (`AZURE_CLIENT_ID/SECRET/TENANT_ID/SCOPES` do not exist; `core/config.py` keeps only `AZURE_REDIRECT_URI` + `FRONTEND_URL`). Config lives on `Company` (`azure_client_id`, `azure_client_secret`, `azure_tenant_id`, `azure_enabled`, `azure_default_role_name`), managed via `/api/v1/companies/{id}/azure-config` (secret is write-only: never in `CompanyRead`, `AzureConfigRead`, or audit payloads).

`GET /azure/login?company_id=<id>` **requires** the company and validates it server-side (exists → active → `azure_enabled` → client ID + tenant ID present) before building the Entra authorize URL from *that* company's config; failures redirect to `{FRONTEND_URL}/login?error=…` with a user-safe message. The validated `company_id` is stored in the server-side `_pending_auth` map keyed by the random `state` — that map (not client-decoded state) is the authority the callback uses to reload the **same** config for token exchange and ID-token validation (issuer/audience/JWKS per company tenant; TTL-pruned, pop-once). Flow: `/azure/login` → Azure → callback (code exchange + ID token validation + JIT user provisioning) → redirect to `{FRONTEND_URL}/auth/callback?access_token=...&refresh_token=...`, handled by `dms-app/src/pages/AzureCallbackPage.tsx`. `GET /auth/azure/config` returns `{enabled, companies}` (active + fully configured only) for the login page's company selector.

**Company isolation:** `resolve_azure_user` requires `company_id`; an existing user matched by `oid` or `email` must belong to that exact company or gets 403 (`_ensure_company_membership`) — users are never relinked or moved across companies. JIT users get the authenticating company's `company_id`.

**Orphaned accounts:** users provisioned before company-scoped Azure auth have `company_id = NULL` — invisible to ADMIN and rejected (403) on Azure login. Repair them with `PATCH /api/v1/users/{id}` from SUPERADMIN: `update_user` normally only applies `company_id` to ADMIN-role targets (reassignment of MAKER/CHECKER/AUDITOR is ignored — `test_non_admin_user_update_ignores_company`), but it *does* assign a company to **any non-SUPERADMIN user whose `company_id` is currently NULL** (same exists/active validation as the ADMIN path). SUPERADMIN targets never receive a company.

**JWK parsing:** `python-jose`'s `jwk.construct()` fails on Azure keys carrying `x5c`. `auth/azure_service.py` builds RSA keys from the X.509 chain with `cryptography`. Do not revert.

## Rate Limiting (spec 31)
`middleware/ratelimit.py` — in-process token buckets per `(rule, client_ip)` (no Redis; single uvicorn worker). Rules: `auth` = `RATE_LIMIT_AUTH_REQUESTS` (10)/window on `/api/v1/auth/login`, `default` = `RATE_LIMIT_REQUESTS` (600)/window on `/api/v1`; skips `OPTIONS`, anything outside `/api/v1` (`/health`, `/docs` live there), and everything when `RATE_LIMIT_ENABLED=false`. Rejection = **429 + `Retry-After` + JSON `detail`**, logged with the `dms.ratelimit` logger **only** — never `AuditService` (no DB writes during a flood; audit runs *inside* the limiter, so 429s are not audited).

**Client IP for throttling:** `X-Real-IP` → **last** `X-Forwarded-For` value → `client.host`. Do NOT reuse the audit helper's first-value rule — nginx's `$proxy_add_x_forwarded_for` appends to a client-supplied header, so the *first* entry is attacker-controlled and would make throttling bypassable; `X-Real-IP` is overwritten by nginx and is authoritative. Memory: `RATE_LIMIT_MAX_KEYS` (10000) prunes fully-refilled buckets and **fails open** (clears the store) if still at cap.

**`main.py` registration order is rbac → audit → rate limit → https → CORS (last = outermost):** CORS outermost is what lets browsers read middleware-generated bodies (308/429/RBAC's 401/403) — do not move it; rate limiting sits outside audit/rbac so floods are rejected before any DB work. Settings are `RATE_LIMIT_*` in `core/config.py`, read at request time (tests monkeypatch them, like `FORCE_HTTPS`).

`tests/conftest.py` disables it (`RATE_LIMIT_ENABLED=False`, same pattern as `SMTP_HOST=""`) because the suite bursts from one TestClient IP; `tests/test_rate_limiting.py` re-enables per-test with tiny limits, a fake clock (monkeypatch `middleware.ratelimit._now`), and `limiter.reset()`. nginx edge: `limit_req_zone` (http context — top of `dms.conf`) + `limit_req ... limit_req_status 429` on `location /api/`; not locally testable, validate with `sudo nginx -t` on deploy.

## Frontend Conventions
- API modules import `apiClient` from `./client` (baseURL `/api/v1`; interceptors: 401-refresh + Blob error parsing) — **not** `apiRoot` from `./base`. Paths are relative: `apiClient.get('/users')`.
- Error display uses `getErrorMessage(err)` from `@/api/client`; toasts via `react-hot-toast`. Download endpoints use `responseType: 'blob'` — the response error interceptor converts Blob error bodies to JSON in place, so `getErrorMessage(err)` and `err.response.data.detail` surface the real `detail`. Don't re-solve this per caller.
- Backend non-admin denials are **404 by design**; `isAccessDeniedError` treats 403/404 as access-denied → `/forbidden`. Genuine denials must keep flowing there — gate UI affordances instead of catching errors.
- Nav-only folders (`navigation_only` on `Directory`/`DirectoryNode`, see Directory Navigation Access): `DocumentsPage` hides Upload CTAs and shows a "View only" badge; `DirectoryTree` mutes the node, shows an eye icon, and suppresses the write context menu. The flag is display-only — enforcement is backend.
- Toast placement: the global `<Toaster>` (`main.tsx`) is `top-right`. Workflow/approval error toasts pass a per-call `{ position: 'top-center' }` override (see `CorrespondenceDetailPage`, `MemoDetailPage`) — do not move the global Toaster to change one toast.
- `store/authStore.ts` persists **only** tokens; the user object is refetched on every load by `ProtectedRoute` → `authApi.me()`.
- `GET /auth/me` hand-builds the `UserRead` payload (`auth/router.py`) — it is what the app boots from. Any `UserRead` field the UI consumes (`directories` for `canAccessCategory`) must be added there, not just on the model; a missing field fails silently (empty default) and once sent all grant-only users to `/forbidden` with no failed request in Network.
- `@` → `dms-app/src/`. Tailwind is used via `@tailwind` directives in `index.css` — **there is no `tailwind.config.js`**; use utilities directly.
- Rich text is TipTap (see `dms-app/src/components/memo/`); sanitized HTML goes through `utils/sanitizeHtml.ts`.
- Typecheck is part of `npm run build`; there is no standalone `typecheck` script.
- `npm run lint` passes with 0 errors. `react-hooks/set-state-in-effect` (React-Compiler-era rule) is enforced at `error`; effects must not call setState synchronously — use `Promise.resolve().then(...)` chains for loading/fetch and promise-deferred resets for reset-on-open/param-change effects (see `WorkflowConfigPanel`, `CompanyFormModal`).

## Dependency Pins (do not bump)
- `bcrypt==4.0.1` — passlib 1.7.4 is incompatible with bcrypt 4.1+.
- `python-jose[cryptography]==3.3.0`, `httpx==0.27.0`.
- No new dependencies without explicit approval.

## Seed Data
`seed.py` (run once, after migrate) creates the five permissions and five roles (SuperAdmin + Admin: all five; Maker: view/download/create/update; Checker: view/download/update; Auditor: view/download), the High/Medium/Low user levels (backfilling `Low` onto users that have none), the default **SuperAdmin** `superadmin@dms.local` / `SuperAdmin@1234`, and 100 GB storage capacity. It does **not** create an admin user — bootstrap through the SuperAdmin (`DEFAULT_ADMIN` in `seed.py` is an unused constant).

## Deploy
Production is **not** Docker: `dms-backend.service` (systemd unit, uvicorn on 127.0.0.1:8000) + `dms.conf` (nginx TLS terminating, serves `dms-app/dist`, proxies `/api` and `/health`, SPA fallback to `index.html`). `docker-compose.yml` is stale — it builds `./backend` and `./frontend`, which do not exist; the root `Dockerfile` is current.

**TLS (spec 30):** certificates are Let's Encrypt via certbot — bootstrap with `sudo scripts/tls/install_tls.sh` (webroot = `dms-app/dist`, ACME challenge served by the port-80 exception in `dms.conf`); renewals reload nginx through `scripts/tls/certbot_deploy_hook.sh` (installed to `/etc/letsencrypt/renewal-hooks/deploy/`, runs `nginx -t` first). nginx terminates TLS and MUST send `X-Forwarded-Proto` (it does, per location). uvicorn runs with `--proxy-headers` (trusts 127.0.0.1 — the nginx hop only). `FORCE_HTTPS=true` in the systemd unit activates `middleware/https.py` (registered **outermost** in `main.py`, last `app.middleware` call): a request with `X-Forwarded-Proto: http` gets `308` to `https://{Host}{path?query}`; requests **without** the header (internal `/health`, localhost) never redirect. Production sets `FRONTEND_URL` / `AZURE_REDIRECT_URI` / `CORS_ORIGINS` to the https origin in the unit file — Azure login redirects are exact-match, so a scheme mismatch there breaks the OAuth flow silently. Tests: `tests/test_https_enforcement.py`.

Treat `storage/uploads/` as runtime data. `__pycache__`/`*.pyc`/`venv/`/`node_modules/` are already gitignored.

## Commits
Short imperative subjects in the repo's existing style (e.g. `Implemented Reply correspondence lifecycle-v1`).
