# Spec: Company Scoped Azure Authentication

## Overview
Currently, Azure AD authentication uses a single global configuration (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID in \.env\). In a multi-tenant DMS where companies have their own Azure AD tenants, each company needs its own Azure AD configuration so users authenticate through their own tenant. JIT-provisioned users are auto-assigned to the company whose Azure config they authenticated through.

## Depends on
- Step 06: Company Profile (CRUD for company entities)
- Azure AD authentication module (\uth/azure_service.py\, \uth/router.py\)

## Routes

### Modified routes
- \GET /api/v1/auth/azure/login?company_id=<id>\ -- add optional \company_id\ query param; when provided, use that company Azure config instead of global env vars; fallback to global config if not provided -- public
- \GET /api/v1/auth/azure/callback\ -- extract \company_id\ from state param, use company-scoped Azure config for token exchange and ID token validation -- public
- \GET /api/v1/auth/azure/config\ -- return \enabled: true\ if global Azure OR any company has Azure enabled; return list of companies with \zure_enabled=true\ for login page -- public

### New routes
- \GET /api/v1/companies/{id}/azure-config\ -- return Azure config status for a company (no secrets) -- admin
- \PUT /api/v1/companies/{id}/azure-config\ -- set/update Azure AD config for a company -- superadmin
- \DELETE /api/v1/companies/{id}/azure-config\ -- remove Azure config from a company -- superadmin

## Database changes
Add columns to the \companies\ table:
`
azure_client_id:        Optional[str] = Field(default=None, max_length=255)
azure_client_secret:    Optional[str] = Field(default=None, max_length=500)
azure_tenant_id:        Optional[str] = Field(default=None, max_length=255)
azure_enabled:          bool = Field(default=False)
azure_default_role_name: Optional[str] = Field(default=None, max_length=50)
`
No new tables. Alembic migration required.

## Templates
No Jinja2 templates -- frontend is React/Vite SPA.

### Frontend changes
- \LoginPage.tsx\ -- fetch companies with Azure enabled; if multiple, show company selector before "Sign in with Microsoft"; if one, auto-select; pass \company_id\ to \/azure/login?company_id=...\
- \CompanyProfilePage.tsx\ -- add Azure AD configuration section (client ID, tenant ID, secret input, enable toggle)
- \dms-app/src/api/company.api.ts\ (or wherever company API lives) -- add \getAzureConfig\, \updateAzureConfig\, \deleteAzureConfig\ methods

## Files to change
- \company_profile/models.py\ -- add Azure fields to \Company\, \CompanyCreate\, \CompanyUpdate\, \CompanyRead\
- \company_profile/service.py\ -- add \get_azure_config\, \update_azure_config\, \delete_azure_config\ methods
- \company_profile/router.py\ -- add \GET /{id}/azure-config\, \PUT /{id}/azure-config\, \DELETE /{id}/azure-config\ endpoints
- \uth/router.py\ -- modify \zure_login\ to accept \company_id\ param; modify \zure_callback\ to extract \company_id\ from state and use company config; modify \zure_config\ to return company list
- \uth/azure_service.py\ -- refactor \uild_authorization_url\, \exchange_code_for_tokens\, \alidate_id_token\ to accept config params instead of reading \settings.*\ directly; embed \company_id\ in state parameter
- \core/config.py\ -- no changes needed (global config stays as fallback)
- \middleware/rbac.py\ -- add new company Azure config endpoints to \ROUTE_PERMISSION_MAP\
- \dms-app/src/pages/LoginPage.tsx\ -- company selector for Azure login
- \dms-app/src/pages/CompanyProfilePage.tsx\ -- Azure config section

## Files to create
- \migrations/versions/<hash>_add_azure_config_to_companies.py\ -- Alembic migration for new columns
- Tests for new endpoints and modified Azure flow

## New dependencies
No new dependencies.

## Rules for implementation
- Use FastAPI + SQLModel only
- Use existing project architecture (backend modules: \uth/\, \users/\, \categories/\, \directories/\, \documents/\, \user_levels/\, \udit/\, \company_profile/\)
- Each backend module follows: \models.py\ (SQLModel + Pydantic read schemas), \schemas.py\ (request/response schemas), \service.py\ (business logic, class-based, takes Session), \outer.py\ (FastAPI router)
- Keep routers thin; business logic belongs in services
- Use \CurrentUser\ from \core/dependencies.py\ for user injection
- Use \AdminUser\ for admin-only endpoints; use \equire_superadmin\ for superadmin-only endpoints
- Add new endpoints to \ROUTE_PERMISSION_MAP\ in \middleware/rbac.py\
- Use SQLModel / parameterized queries only
- Use JWT access + refresh token auth (core/security.py)
- Python: 4-space indent, \snake_case\
- TypeScript: 2-space indent, \PascalCase\ components, \camelCase\ hooks/stores
- Frontend API files import \piClient\ from \./client\, not \piRoot\ from \./base\
- Never expose Azure client secrets in API responses -- return \configured: true/false\ only
- Use \.env\ for configuration only (never commit \.env\)
- Maintain audit trail via \AuditService.log_event()\ (audit/service.py)
- Audit logs are immutable (no PUT/PATCH/DELETE endpoints)
- Tests use SQLite in-memory; patch \engine\ in \core.database\, \middleware.rbac\, \middleware.audit\
- Azure AD: use \cryptography\ library for JWK parsing (not \jwk.construct()\)
- Global Azure config in \.env\ remains as fallback; company-scoped config takes precedence when \company_id\ is provided
- Embed \company_id\ in the state parameter (base64-encoded JSON \{"cid": <id>, "nonce": <nonce>}\) so the callback knows which company config to use
- Company Azure config endpoints are scoped: ADMIN can view their own company config; SUPERADMIN can manage any company config
- No new dependencies unless explicitly approved
- Add/update tests for every implemented feature

## Definition of done
1. Migration applies cleanly (\lembic upgrade head\)
2. SUPERADMIN can set Azure config (client_id, client_secret, tenant_id) on a company via \PUT /api/v1/companies/{id}/azure-config\
3. SUPERADMIN can view company Azure config status via \GET /api/v1/companies/{id}/azure-config\ (no secrets returned)
4. SUPERADMIN can remove Azure config via \DELETE /api/v1/companies/{id}/azure-config\
5. Login page shows companies with Azure enabled; selecting one redirects to that company Azure AD tenant
6. Azure callback correctly uses company-scoped tenant ID for ID token validation
7. JIT-provisioned users are assigned to the company whose Azure config was used
8. Global Azure config still works as fallback when no \company_id\ is provided
9. Admin cannot manage Azure config for other companies; superadmin can
10. All existing tests pass; new tests cover the added endpoints and modified flow
11. \
pm run build\ passes (frontend typecheck)
