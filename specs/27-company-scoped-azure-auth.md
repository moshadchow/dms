# Spec: Company Scoped Azure Auth (No Global Env Fallback)

## Overview
Azure AD / Microsoft Entra ID authentication previously resolved configuration from two sources: a per-company configuration on the `Company` model and a global `AZURE_*` `.env` fallback. This spec makes the company-scoped, database-stored configuration the **single source of truth**. Global `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID` and `AZURE_SCOPES` are removed from `core/config.py` and `.env.example`; no runtime authentication path may read them. The login flow must establish and validate the company context *before* redirecting to Entra, preserve it securely through the OAuth state / server-side pending store, and reuse the **same** company configuration for token exchange, ID-token validation (issuer/audience/JWKS per tenant) and JIT user provisioning. Cross-company authentication (Company A config authenticating a Company B user, or OAuth state tampering) is rejected.

## Depends on
- Step 15: Company Profile (company CRUD, `/{id}/azure-config` endpoints)
- Azure AD authentication module (`auth/azure_service.py`, `auth/router.py`)
- Prior spec `.claude/plans/8-company-scoped-azure-auth.md` (company-scoped config, which this spec reduces to the only path)

## Routes

### Modified routes
- `GET /api/v1/auth/azure/login?company_id=<id>` — `company_id` is now **required**; validates the company (exists, active, `azure_enabled`, client_id + tenant_id present) against the DB, builds the Entra authorize URL from *that* company's config, and stores `company_id` in the server-side pending store keyed by `state`. On any validation failure: `302` to `{FRONTEND_URL}/login?error=<user-safe message>` (never a raw JSON error page, never secrets). — public
- `GET /api/v1/auth/azure/callback` — recovers `company_id` from the server-side pending store (never from client-decoded state), reloads the **same** company config for token exchange and ID-token validation, resolves the user, records `company_id` on audit events where known. — public
- `GET /api/v1/auth/azure/config` — response changes from `{global_enabled, companies}` to `{enabled, companies}`; `companies` lists only companies that are `is_active AND azure_enabled AND azure_client_id IS NOT NULL AND azure_tenant_id IS NOT NULL`. No reference to global settings. — public

### Unchanged routes
- `GET/PUT/DELETE /api/v1/companies/{id}/azure-config` — GET: ADMIN own company / SUPERADMIN any; PUT/DELETE: SUPERADMIN only. Secrets remain write-only in responses.

No new routes. No `ROUTE_PERMISSION_MAP` changes (all paths already mapped or public).

## Database changes
No schema change. The `companies` table already has `azure_client_id`, `azure_client_secret`, `azure_tenant_id`, `azure_enabled`, `azure_default_role_name` (migration `20260915_f1a2b3c4d5e6`). Per-company scopes are **not** a column: default scopes are a module constant in `auth/azure_service.py`.

## Templates
No Jinja2 templates — frontend is React/Vite SPA. Frontend changes are listed under "Files to change".

## Files to change
- `core/config.py` — delete `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`, `AZURE_SCOPES`, `AZURE_DEFAULT_ROLE_NAME`, properties `AZURE_AUTHORITY` and `AZURE_ENABLED`. Keep `AZURE_REDIRECT_URI` (app's own callback URL, not a tenant credential) and `FRONTEND_URL`.
- `auth/azure_service.py` — `get_azure_config_for_company()` becomes DB-only (no global fallback; raises 400/404/403/503 with user-safe messages); add module constants `DEFAULT_SCOPES`, `DEFAULT_JIT_ROLE_NAME`; `resolve_azure_user()` takes required `company_id` and **rejects** an existing user whose `company_id` differs from the authenticating company (403, no relink, no reassign); delete dead `decode_state()`; update docstrings. JWK/x5c `cryptography` handling untouched.
- `auth/router.py` — `azure_login` requires `company_id` and converts config-resolution `HTTPException`s into `302 /login?error=…` redirects; `_pending_auth` entries get a timestamp and TTL pruning; `azure_callback` passes `company_id` to audit events after state validation; `azure_config` returns the new shape; move the bottom-of-file `select` import to the top.
- `company_profile/models.py` — move `azure_client_secret` from `CompanyBase` to the `Company` table model so `CompanyCreate`/`CompanyRead` never serialize the secret.
- `company_profile/service.py` — `update_azure_config` redacts `azure_client_secret` from audit `old_value`/`new_value`; enabling requires client_id + client_secret + tenant_id (422 otherwise).
- `dms-app/src/pages/LoginPage.tsx` — read `error` from the query string into the error banner; use `data.enabled` instead of `global_enabled`; remove the "global Azure, no company selector" branch.
- `.env.example` — delete `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`, `AZURE_DEFAULT_ROLE_NAME`; note that Azure AD is configured per company in the app.
- `AGENTS.md` — rewrite the "Azure AD" section (company-scoped only, no env fallback); adjust the `.env` note.
- `tests/test_azure_auth.py` — rewrite config/login/redirect/JIT tests around company scoping; add token-exchange, ID-token and config-removal guard tests.
- `tests/test_company_azure_config.py` — new `/azure/config` shape, secret never in company list/audit payloads.

## Files to create
- `specs/27-company-scoped-azure-auth.md` (this file). No new modules, no migration.

## New dependencies
No new dependencies.

## Rules for implementation
- Use FastAPI + SQLModel only; existing module layout (`models.py` / `schemas.py` / `service.py` / `router.py`); routers stay thin.
- **No runtime read of `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`, `AZURE_SCOPES`, `AZURE_ENABLED` anywhere** — not in config, services, routers, startup, tests or docs-as-code.
- Client may *identify* the company (`company_id` query param); only the backend validates it: load from DB → verify active → verify Azure enabled → verify client_id/tenant_id present → build authorize URL → store `company_id` server-side keyed by the random `state`.
- Callback trusts **only** the server-side pending store for `company_id`; the client-decoded state must never select a company (`decode_state` is removed).
- Same company config object drives authorize URL, token exchange and ID-token validation (issuer `https://login.microsoftonline.com/{tenant}/v2.0`, audience = company client id, JWKS per tenant).
- Preserve python-jose `x5c` → `cryptography` certificate handling for Azure signing keys.
- Existing user resolved by `oid` or `email` must belong to the authenticating company, else 403 with a generic message; never silently move/relink a user across companies. JIT-provisioned users get `company_id` of the authenticating company.
- Never return `azure_client_secret` in any API response or audit payload.
- Error messages shown to users are user-safe: no secrets, no tenant/client IDs, no stack traces.
- Company context recorded on audit events via existing `AuditService.log_event()` whenever known.
- Keep `AZURE_REDIRECT_URI`/`FRONTEND_URL` as the only auth-related env settings.
- Tests: SQLite in-memory, patch engine in `core.database`, `middleware.rbac`, `middleware.audit`; look up seeded roles, never create duplicates.
- No new dependencies; Python 4-space `snake_case`; TypeScript 2-space `PascalCase`.

## Definition of done
1. `core/config.py` has no `AZURE_CLIENT_ID/SECRET/TENANT_ID/SCOPES`, no `AZURE_ENABLED`/`AZURE_AUTHORITY`; `.env.example` matches.
2. `GET /azure/login` without `company_id` → `302` to `/login?error=…`, no Entra redirect.
3. `GET /azure/login?company_id=X` for an active, configured company → `302` to `login.microsoftonline.com/{X.tenant}` containing X's client id; for an unknown/inactive/disabled/unconfigured company → `302` to `/login?error=…`.
4. Two configured companies produce authorize URLs with their own tenant + client id (isolation test green).
5. Callback uses the pending-store company for token exchange (captured request shows that company's client id/secret/tenant) and for ID-token validation (wrong-tenant issuer and wrong audience rejected; correct one accepted).
6. Existing user of company B attempting login through company A's config → 403, `company_id` unchanged; JIT user lands in the authenticating company.
7. `GET /api/v1/companies` and `/{id}` responses contain no `azure_client_secret`; audit rows for azure-config changes contain no raw secret.
8. `GET /auth/azure/config` returns `{enabled, companies}` with only active + fully configured companies; no `global_enabled`.
9. LoginPage displays `?error=` messages and shows the Microsoft button only when at least one company is configured.
10. Guard tests prove no auth source file references the removed settings.
11. `pytest` passes (no new failures beyond the documented baseline), `npm run build` and `npm run lint` pass.
12. Repository-wide search for `AZURE_CLIENT_ID|AZURE_CLIENT_SECRET|AZURE_TENANT_ID|AZURE_SCOPES` yields only historical docs/migrations/dead enum names — zero runtime hits.
