# Repository Guidelines

FastAPI backend at repo root + React/Vite SPA in `dms-app/`. Python 4-space/`snake_case`; TypeScript 2-space, `PascalCase` components, `camelCase` hooks/stores.

`CLAUDE.md` is a legacy near-duplicate of this file and has drifted (it lists `ruff`/`black`, which are **not** installed). Treat this file as authoritative.

## Commands

Backend (run from repo root, `venv/` is the working interpreter):
```
alembic upgrade head          # apply migrations — REQUIRED; run before first boot
python seed.py                # roles, permissions, admin user — once, after migrate
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

Copy `.env.example` → `.env`. Never commit `.env` (Azure secrets).

## Spec-Driven Workflow
Features are numbered steps. Specs live in `specs/NN-kebab-slug.md`; `/create-spec` (`.opencode/commands/create-spec.md`, mirrored in `.claude/commands/`) scaffolds the next one with a required structure (Overview / Depends on / Routes / Database changes / Files to change / Files to create / New dependencies / Rules for implementation / Definition of done). Check `specs/` for the highest number before starting new work. `plans/` holds derived implementation plans and is currently empty.

## Migrations
`alembic.ini` `file_template` is `%%(year)d%%(month).2d%%(day).2d_%%(rev)s_%%(slug)s` — new revisions are **date-prefixed** (`20260921_1559_add_x.py`). `migrations/env.py` overwrites `sqlalchemy.url` from `.env`; the URL in `alembic.ini` is dead config.

Any model change needs a migration. **Never** rely on `DEBUG=True` in a shared/dev DB to build the schema (see below).

## DB / Startup Invariant
`main.py`'s lifespan calls `create_db_and_tables()` when `DEBUG=True`, silently bypassing Alembic. It builds tables from SQLModel metadata only, so it will not apply column adds to existing tables. Production runs `DEBUG=false` + `alembic upgrade head` only.

Postgres in production (`requirements.txt`: `psycopg2-binary`). Storage: `STORAGE_ROOT` from `.env`, default `storage/uploads`.

## Testing: SQLite In-Memory
`tests/conftest.py` builds a `StaticPool` in-memory engine — **not** Postgres — and monkeypatches `engine` in three modules: `core.database`, `middleware.rbac`, `middleware.audit`. A new module that does `from core.database import engine` at import time bypasses the patch and hits the real DB; add it to the fixture.

Fixture shapes (easy to guess wrong):
- `client` yields a **tuple** `(test_client, engine, storage_path)` — not just a client.
- `seeded_data` returns id dict; two companies are seeded (`company_id` = "Test Company", `other_company_id` = "Other Company") plus a cross-company `other_admin`.
- `auth_headers` returns keys `admin`, `maker`, `superadmin`, `other_admin`. **There is no checker/auditor user** — create one in-test if a test needs one.

Company-isolation regressions are the norm here; they get their own file (`test_audit_company.py`, `test_category_company.py`, `test_workflow_company.py`, `test_user_visibility.py`, `test_company_assignment.py`). Add new company-scoped features there rather than growing `test_<feature>.py`.

**The suite is slow.** The `client` fixture rebuilds the whole schema on a fresh in-memory DB per test (~2 s setup), and `test_correspondence.py` alone takes ~2.5 min (54 tests) with PDF generation on top. Target a file/class while iterating, but budget a long run before declaring done.

## Module Convention
`models.py` (SQLModel + read schemas) · `schemas.py` (write schemas, optional) · `service.py` (class-based, takes `Session`) · `router.py` (thin — business logic belongs in the service). Keep routers thin.

Exceptions live in `core/exceptions.py`; access guards in `core/access.py` (`ensure_category_access`, `ensure_directory_access`, `ensure_document_access`, `ensure_document_user_level_access`).

`documents/` has `DocumentService` + `DocumentVariantService`; `workflow/` has three routers in `router.py` — `router` (`/api/v1/workflows`), `instance_router` (`/api/v1/workflow-instances`), `signature_router` (`/api/v1/signatures`) — with services split into `definition_service.py` / `instance_service.py` / `approval_service.py` (`service.py` is a back-compat re-export shim) and shared approver logic in `approval_policy.py`.

## Company Scoping (cross-cutting, easiest thing to break)
`Company` is the tenancy boundary. `users`, `categories`, `correspondences` (and `workflow_definitions`, `audit_logs`, `memos`) carry a `company_id` FK. Enforced invariants, all covered by tests:
- **ADMIN** is auto-scoped to `current_user.company_id`. A client-supplied `company_id` in a payload is ignored, not rejected.
- An **ADMIN with no company** sees empty lists and is rejected on writes (e.g. `test_company_less_admin_rejected`).
- Rows with `company_id = NULL` are **invisible** to ADMIN and to regular users; they show only to SUPERADMIN.
- **SUPERADMIN** passes authorization guards but is denied at the *service* layer for mutations (403). It can only read, and needs an explicit `company_id` query param to scope — with no param it sees all companies (audit logs: empty until a company is chosen).
- `Company.short_name` is the storage namespace and must match `[A-Za-z0-9_-]+`; it is validated on every path build.

`AdminUser` is an **authorization** guard, not a visibility guard — it admits both ADMIN and SUPERADMIN. Visibility hiding is done in the service (`users/service.py` `list_users()`).

## Company-Scoped Storage
`core/storage.py` `StorageService` (module singleton `storage_service`) owns all path building. Layout: `STORAGE_ROOT/<short_name>/{uploads,memos,signatures,correspondence}/`.

**Always resolve through `documents/utils.py::resolve_storage_path(relative_path, company)`** — never `STORAGE_ROOT / relative_path` by hand. It validates the resolved path stays under the company root (path-traversal guard) and 404s if absent. `resolve_path_with_fallback` tries the company-prefixed path first, then the legacy non-prefixed path, for pre-migration files. `delete_from_disk` is idempotent. `scripts/migrate_storage.py` and `scripts/fix_storage_paths.py` backfill the layout.

## RBAC: two layers
1. `middleware/rbac.py` `ROUTE_PERMISSION_MAP` maps `(HTTP_METHOD, path_prefix)` → `PermissionAction`. **New endpoints must be added here** or the middleware silently skips them. Paths under `PUBLIC_PATH_PREFIXES` (`/api/v1/auth`, `/docs`, `/redoc`, `/openapi.json`, `/health`) bypass it entirely. Known quirks: `PATCH /api/v1/workflows/{id}/activate` has no entry, and in `correspondence/` both `POST .../{id}/...` and `DELETE .../{id}/...` map to `UPDATE`.
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

- `WorkflowInstanceService.submit_instance()` **snapshots** the definition's steps. Editing a definition never affects in-flight instances.
- Deactivating a definition blocks new submissions only.
- Definitions are category-agnostic (`document_category_id` was removed); category filtering happens at the document level. Multiple active definitions per category are allowed, so submission UIs need a picker.
- `workflow_history` is the approval ledger; `audit/` stays the system-wide log. Both are written, never a third mechanism.
- Approver eligibility (`workflow/approval_policy.py`) is admin-configured and does **not** filter by User Level (`resolve_eligible_user_ids`; `list_pending` shows instances regardless of level — note `approval_service.act` refuses MAKER-role users). In exchange, an eligible approver at the current step of an in-flight instance can **read** the document even when its User Level links exclude them: memos do this unconditionally in `_check_view_access`, correspondence via `approver_view=True` on read paths only (detail, by-document, movements, replies, downloads) — mutations keep the strict level guard (`is_eligible_current_approver`). The grant lapses once the instance leaves `submitted`/`pending_approval`.
- Activation does not validate that steps/approvers exist; step-order uniqueness is enforced only by a DB constraint.

## Module Notes
- **`user_levels/`** — `DocumentUserLevelLink` gates document visibility in `documents/service.py`; Admin bypasses. A document with no links is visible to all linked levels; if no links exist at all, it is unconstrained.
- **`memos/`** — markdown → HTML → reportlab PDF (`memos/pdf_generator.py`). Reportlab's `Paragraph` parser is strict about balanced tags, so `_apply_inline_formatting` strips italics to plain text and `_sanitize_for_reportlab()` removes malformed tags. `_check_edit_access`: terminal statuses are frozen; the author may edit any non-terminal status; eligible approvers only in `draft`/`returned`/`rejected`.
- **`correspondence/`** — inbound/outbound/internal register. Key facts: `document_id` is nullable; outbound/internal auto-generate an HTML backing document from `body`; **a category is required to attach files** (`_resolve_backing_directory`); `/{id}/download` falls back to the first attachment; `/{id}/download-final` renders a signed PDF (`correspondence/pdf_generator.py`). Status model is richer than workflow: `received/registered/assigned/processing → draft/submitted/pending_approval/… → ready_for_dispatch → dispatched → delivered → acknowledged → completed → archived` (`TERMINAL_STATUSES` in `service.py`; also frozen once `dispatch_method` is set). Replies: `POST /{parent_id}/reply`, `POST /{id}/submit-reply`, `POST /{id}/mark-responded`, `GET /{parent_id}/replies`, keyed on `parent_correspondence_id` + `response_received`/`responded_at`. All mutations append to `CorrespondenceMovement` (the timeline).
- **`notifications/`** — `EmailService` is fire-and-forget and never raises; `EmailNotification` rows give idempotency. SMTP via `core/config.py` `SMTP_*`.
- **`signatures/`** — JPEG/PNG, 5 MB, soft-delete, stored under the company `signatures/` root. Referenced by `signature_id` on workflow approvals.
- **`company_profile/`** — SUPERADMIN-only CRUD at `/api/v1/companies`; per-company Azure AD config at `/{id}/azure-config` (GET: own company or any for SUPERADMIN; PUT/DELETE: SUPERADMIN only; secret is never returned).
- **`storage_usage/`** — quota accounting, admin endpoints at `/api/v1/storage`.

## Azure AD
Per-company credentials on the `Company` model, falling back to global `AZURE_*` env. Login takes optional `company_id`; the callback recovers it from the state parameter. Flow: `/azure/login` → Azure → callback (code exchange + ID token validation + JIT user provisioning) → redirect to `{FRONTEND_URL}/auth/callback?access_token=...&refresh_token=...`, handled by `dms-app/src/pages/AzureCallbackPage.tsx`.

**JWK parsing:** `python-jose`'s `jwk.construct()` fails on Azure keys carrying `x5c`. `auth/azure_service.py` builds RSA keys from the X.509 chain with `cryptography`. Do not revert.

## Frontend Conventions
- API modules import `apiClient` from `./client` (baseURL `/api/v1`, 401-refresh interceptor) — **not** `apiRoot` from `./base`. Paths are relative: `apiClient.get('/users')`.
- Error display uses `getErrorMessage(err)` from `@/api/client`; toasts via `react-hot-toast`.
- `store/authStore.ts` persists **only** tokens; the user object is refetched on every load by `ProtectedRoute` → `authApi.me()`.
- `@` → `dms-app/src/`. Tailwind is used via `@tailwind` directives in `index.css` — **there is no `tailwind.config.js`**; use utilities directly.
- Rich text is TipTap (see `dms-app/src/components/memo/`); sanitized HTML goes through `utils/sanitizeHtml.ts`.
- Typecheck is part of `npm run build`; there is no standalone `typecheck` script.

## Dependency Pins (do not bump)
- `bcrypt==4.0.1` — passlib 1.7.4 is incompatible with bcrypt 4.1+.
- `python-jose[cryptography]==3.3.0`, `httpx==0.27.0`.
- No new dependencies without explicit approval.

## Seed Data
`seed.py` creates five roles: SuperAdmin and Admin get all five permissions; Maker gets view/download/create/update; Checker gets view/download/update; Auditor gets view/download. Default admin `admin@dms.local` / `Admin@1234`.

## Deploy
Production is **not** Docker: `dms-backend.service` (systemd unit, uvicorn on 127.0.0.1:8000) + `dms.conf` (nginx TLS terminating, serves `dms-app/dist`, proxies `/api` and `/health`, SPA fallback to `index.html`). `docker-compose.yml` is stale — it builds `./backend` and `./frontend`, which do not exist; the root `Dockerfile` is current.

Treat `storage/uploads/` as runtime data. `__pycache__`/`*.pyc`/`venv/`/`node_modules/` are already gitignored.

## Commits
Short imperative subjects in the repo's existing style (e.g. `Implemented Reply correspondence lifecycle-v1`).
