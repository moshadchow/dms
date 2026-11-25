# Spec: Transport Layer Security (TLS/HTTPS)

## Overview
Production already reaches users through nginx (`dms.conf`), but TLS coverage is incomplete: the nginx config pins no cipher suites, performs no OCSP stapling, serves HSTS with a 1-year max-age and no `includeSubDomains`, and still points at manually placed certificates under `/etc/nginx/ssl/` instead of Let's Encrypt. Behind the proxy, uvicorn runs without `--proxy-headers`, so the application never sees the real `https` scheme, and `dms-backend.service` still advertises a plain-HTTP LAN origin (`http://192.168.101.34`) as the only CORS origin while `FRONTEND_URL` / `AZURE_REDIRECT_URI` default to `http://localhost` — all of which break or weaken HTTPS-mode cookie/redirect/CORS behavior. This step hardens the TLS edge (certbot-managed certificates, Mozilla-intermediate ciphers, OCSP stapling, 2-year includeSubDomains HSTS), teaches the application to trust the proxy's `X-Forwarded-Proto` and optionally enforce HTTPS (`FORCE_HTTPS` 308 redirect), and aligns the systemd unit and `.env.example` with the HTTPS deployment.

## Depends on
Spec 15 company profile (per-company config untouched), Azure AD company-scoped auth (spec 27 — `FRONTEND_URL` / `AZURE_REDIRECT_URI` must be exact for the OAuth flow), existing `dms.conf` / `dms-backend.service` production deployment, `core/config.py` Settings, `main.py` middleware registration order.

## Routes
No new API routes. Changed behavior on existing routes:
- `GET *` (any path) — when `FORCE_HTTPS=true` and the request arrives with `X-Forwarded-Proto: http`, respond `308 Location: https://{Host}{raw path + query}` — public (redirect happens before auth). `308` (not `301`) preserves the method and body, so API POSTs that ever arrive over plain HTTP are re-sent as POSTs rather than degraded to GET.
- Requests with `X-Forwarded-Proto: https` or **no** forwarded header are untouched (internal `/health`, localhost, direct uvicorn access keep working).
- `GET /docs`, `/redoc`, `/openapi.json`, `/health` remain public and proxied as today (explicitly out of scope for removal).

## Database changes
No database changes.

## Templates
No Jinja2 templates — frontend is React/Vite SPA. No frontend changes needed (the SPA already uses relative `/api/v1` paths and is served same-origin by nginx over HTTPS).

## Files to change
- `dms.conf` — Mozilla-intermediate `ssl_ciphers`, `ssl_prefer_server_ciphers off`, `ssl_ecdh_curve X25519:secp384r1`, OCSP stapling (`ssl_stapling on` / `ssl_stapling_verify on`), HSTS `max-age=63072000; includeSubDomains`, certificate paths switched to `/etc/letsencrypt/live/dms.xpertfintech.com/fullchain.pem` + `privkey.pem` + `chain.pem`, port-80 block upgraded to `308` with an ACME `/.well-known/acme-challenge/` exception (webroot = `dms-app/dist`) so certbot's http-01 challenge is not redirected.
- `core/config.py` — new `FORCE_HTTPS: bool = False` setting.
- `main.py` — HTTPS-enforcement middleware registered **last** (Starlette `add_middleware` prepends, so last-registered is outermost): the redirect runs before audit/RBAC/CORS, so plain-HTTP arrivals are upgraded before any other middleware touches them.
- `dms-backend.service` — add `--proxy-headers` to ExecStart; `FORCE_HTTPS=true`, `FRONTEND_URL=https://dms.xpertfintech.com`, `AZURE_REDIRECT_URI=https://dms.xpertfintech.com/api/v1/auth/azure/callback`, `CORS_ORIGINS=["https://dms.xpertfintech.com"]`, `DEBUG=false`.
- `.env.example` — commented production HTTPS block (`FORCE_HTTPS`, https `FRONTEND_URL` / `AZURE_REDIRECT_URI` / `CORS_ORIGINS`); dev defaults unchanged.
- `AGENTS.md` — Deploy section: proxy-header contract, `FORCE_HTTPS`, certbot renewal hook.

## Files to create
- `specs/30-transport-layer-security.md` (this file)
- `scripts/tls/install_tls.sh` — idempotent server-side bootstrap: install certbot if missing, obtain/renew the certificate for `dms.xpertfintech.com` via webroot (ACME challenge served from `dms-app/dist` by the port-80 exception in `dms.conf`), install the renewal deploy hook, `nginx -t` + reload.
- `scripts/tls/certbot_deploy_hook.sh` — `nginx -t && systemctl reload nginx` (installed to `/etc/letsencrypt/renewal-hooks/deploy/`).
- `tests/test_https_enforcement.py` — redirect matrix (http→308 with path+query preserved, https→200, no header→200, `FORCE_HTTPS=false`→200), applies to API paths and `/health`, plus Settings default assertion.

## New dependencies
No new dependencies (certbot is a system package installed by the shell script on the server, not a Python/npm dependency).

## Rules for implementation
- Use FastAPI + SQLModel only
- Use existing project architecture (backend modules: `auth/`, `users/`, `categories/`, `directories/`, `documents/`, `user_levels/`, `audit/`)
- Each backend module follows: `models.py` (SQLModel + Pydantic read schemas), `schemas.py` (request/response schemas), `service.py` (business logic, class-based, takes Session), `router.py` (FastAPI router)
- Keep routers thin; business logic belongs in services
- Use `CurrentUser` from `core/dependencies.py` for user injection
- Use `AdminUser` for admin-only endpoints
- Add new endpoints to `ROUTE_PERMISSION_MAP` in `middleware/rbac.py` (none needed — no new routes)
- Use SQLModel / parameterized queries only
- Use JWT access + refresh token auth (core/security.py)
- Hash passwords with bcrypt 4.0.1 (do not upgrade)
- Python: 4-space indent, `snake_case`
- TypeScript: 2-space indent, `PascalCase` components, `camelCase` hooks/stores
- Frontend API files import `apiClient` from `./client`, not `apiRoot` from `./base`
- Never expose secrets or sensitive data in logs
- Use `.env` for configuration only (never commit `.env`)
- Maintain audit trail via `AuditService.log_event()` (audit/service.py)
- Audit logs are immutable (no PUT/PATCH/DELETE endpoints)
- Tests use SQLite in-memory; patch `engine` in `core.database`, `middleware.rbac`, `middleware.audit`
- Azure AD: use `cryptography` library for JWK parsing (not `jwk.construct()`)
- No new dependencies unless explicitly approved
- Add/update tests for every implemented feature
- Middleware must never redirect when the forwarded header is absent (internal health checks and local development must keep working)
- The redirect target must be built from the request `Host` header and must preserve the raw path and query string; do not hardcode the hostname in code
- uvicorn trusts `X-Forwarded-*` from 127.0.0.1 by default — add only `--proxy-headers`; do not widen `--forwarded-allow-ips` beyond the default loopback
- Certificates are managed by certbot; never commit private keys or certificates

## Definition of done
- [ ] `pytest tests/test_https_enforcement.py` passes (redirect matrix + Settings default).
- [ ] With `FORCE_HTTPS=true`, a request carrying `X-Forwarded-Proto: http` to `/api/v1/auth/me` returns `308` with `Location: https://<host><path>` and query string preserved.
- [ ] The same request with `X-Forwarded-Proto: https`, or with no forwarded header, returns the normal non-redirect response.
- [ ] With `FORCE_HTTPS=false` (default), no request is redirected regardless of the header.
- [ ] `dms.conf` configures only TLSv1.2/TLSv1.3, pins the intermediate cipher suite, enables OCSP stapling, and sends `Strict-Transport-Security: max-age=63072000; includeSubDomains`.
- [ ] `dms.conf` references certbot paths under `/etc/letsencrypt/live/dms.xpertfintech.com/`.
- [ ] `nginx -t` passes with the new `dms.conf` (run server-side).
- [ ] `dms-backend.service` starts uvicorn with `--proxy-headers` and sets `FORCE_HTTPS=true`, https `FRONTEND_URL`, https `AZURE_REDIRECT_URI`, https `CORS_ORIGINS`, `DEBUG=false`.
- [ ] `scripts/tls/install_tls.sh` and `scripts/tls/certbot_deploy_hook.sh` exist and are executable; the hook reloads nginx only after `nginx -t` succeeds.
- [ ] `.env.example` documents the production HTTPS values while keeping dev defaults.
- [ ] AGENTS.md Deploy section documents the proxy-header contract and certbot renewal hook.
