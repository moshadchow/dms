# Spec: Rate Limiting and DDoS Mitigation

## Overview
Step 31 adds per-IP request throttling to the DMS API so credential brute-force
(POST /auth/login) and cheap request floods are stopped before they consume
application or database work, plus an nginx edge `limit_req` filter so volumetric
floods are absorbed before they ever reach uvicorn. Until now nothing in the stack
limits request rate: an attacker can hammer login or any API endpoint
indefinitely, and each request runs RBAC JWT checks, DB sessions, and audit
writes. The feature is a pure middleware (no new routes, no new dependencies) —
an in-process token bucket keyed by (rule, client IP) answers `429` with a
`Retry-After` header, configurable through `.env`, enabled by default, and
deliberately keeps its state out of Postgres so throttling never adds load during
an attack.

## Depends on
- Step 30 (Transport Layer Security): production runs behind nginx TLS
  termination with `proxy_set_header X-Real-IP` / `X-Forwarded-For`
  (dms.conf), which is the trusted source of the real client IP; and the
  middleware-registration convention in `main.py` (last registered = outermost).

## Routes
No new routes.

Rate limiting is enforced entirely by middleware; no endpoint is added, so
`ROUTE_PERMISSION_MAP` in `middleware/rbac.py` needs no new entries.

## Database changes
No database changes.

Limiter state is in-process (token buckets in a dict inside
`middleware/ratelimit.py`). It is intentionally not persisted: rejections must
never touch the database.

## Templates
No Jinja2 templates — frontend is React/Vite SPA.

No frontend changes needed: the 429 body is `{"detail": "..."}` like every other
error, and `getErrorMessage(err)` in `dms-app/src/api/client.ts` already surfaces
it. CORS is reordered (see Files to change) so the browser can actually read the
429 response body cross-origin.

## Files to change
- `main.py` — register `rate_limit_middleware` between HTTPS enforcement and the
  audit middleware, and move the `CORSMiddleware` registration to **last**
  (outermost). Registration order becomes: rbac → audit → ratelimit → https →
  CORS, giving the request flow `CORS → https → ratelimit → audit → rbac →
  router`. CORS must be outermost so every middleware-generated response (308,
  429, and the pre-existing rbac 401/403) carries `Access-Control-Allow-Origin`;
  today CORS is innermost and those responses are unreadable cross-origin.
  Rate limiting sits outside audit/rbac so rejects happen before any DB work and
  a flood generates zero audit rows.
- `core/config.py` — new `# Rate Limiting` settings block:
  `RATE_LIMIT_ENABLED: bool = True`,
  `RATE_LIMIT_REQUESTS: int = 600` (default rule, per IP),
  `RATE_LIMIT_WINDOW_SECONDS: int = 60`,
  `RATE_LIMIT_AUTH_REQUESTS: int = 10` (login, per IP),
  `RATE_LIMIT_MAX_KEYS: int = 10000` (memory cap on tracked IPs).
- `.env.example` — new `# Rate Limiting` block documenting the five variables
  with comments (dev can set `RATE_LIMIT_ENABLED=false`).
- `tests/conftest.py` — monkeypatch `RATE_LIMIT_ENABLED` to `False` in the
  `client` fixture (same pattern as `SMTP_HOST=""`): the suite bursts thousands
  of requests from the single TestClient IP and must never self-throttle.
  `core.database.settings` and `core.config.settings` are the same cached
  singleton, so patching the attribute reaches the middleware too.
- `dms.conf` — edge limiting: `limit_req_zone $binary_remote_addr zone=dms_api:10m
  rate=10r/s;` at the top of the file (http context — the file is included from
  nginx's `http {}`), and in the 443 `location /api/` block:
  `limit_req zone=dms_api burst=60 nodelay; limit_req_status 429;
  limit_req_log_level warn;`. Edge rate (10 r/s) matches the app's sustained
  default (600/min); `burst=60 nodelay` absorbs normal page-load parallelism.
  The port-80 server only 308-redirects, so it needs no limit.
  Not locally verifiable (no nginx on the dev box) — validate on the server with
  `sudo nginx -t` after deploy, same as spec 30.
- `dms-backend.service` — comment-only note that the rate-limit env vars are
  tunable there (defaults already apply; no `Environment=` lines required).
- `AGENTS.md` — short "Rate Limiting (spec 31)" note: middleware position in the
  stack, the trusted-IP rule, exempt paths, and the conftest disable pattern.

## Files to create
- `middleware/ratelimit.py` — `Limiter` class + `rate_limit_middleware`:
  - Token bucket per `(rule, ip)` key: capacity = rule limit, refill =
    `limit / window` tokens/second, clocked by module-level `_now()` wrapper
    around `time.monotonic()` (tests monkeypatch `_now` for a fake clock).
  - Rules: `auth` for `/api/v1/auth/login` (limit `RATE_LIMIT_AUTH_REQUESTS`),
    `default` for everything else under `/api/v1` (limit `RATE_LIMIT_REQUESTS`).
  - Skips: `RATE_LIMIT_ENABLED=false`, `OPTIONS` requests, exempt prefixes
    (`/health`, `/docs`, `/redoc`, `/openapi.json`), and paths outside `/api/v1`.
  - Trusted client IP: `X-Real-IP` first (nginx `proxy_set_header X-Real-IP
    $remote_addr` overwrites any client-supplied value, so it cannot be
    spoofed through the proxy), else the **last** value of `X-Forwarded-For`
    (nginx appends the real IP to whatever the client sent — taking the first
    value, as the audit helper does, would let an attacker rotate a fake first
    entry to bypass throttling), else `request.client.host`.
  - Rejection: `429` JSON `{"detail": "Too many requests. Please retry after
    <n> seconds."}` + `Retry-After: <n>` header (integer seconds, min 1), logged
    via `logging` only. Never via `AuditService` — no DB writes during a flood
    (and the audit middleware runs inside the limiter anyway, so 429s are not
    audited).
  - Memory safety: buckets store `(tokens, updated, expires_at)`; when the key
    count reaches `RATE_LIMIT_MAX_KEYS`, fully-refilled (expired) entries are
    pruned; if still at cap, the store is cleared — fail-open, throttling under
    memory pressure must never block legitimate users.
  - `Limiter.reset()` for tests.
- `tests/test_rate_limiting.py` — targeted tests (see Definition of done).

## New dependencies
No new dependencies. The limiter is implemented with the standard library
(`time`, `threading`, `math`); Redis/slowapi would require approval and is
unneeded — production runs a single uvicorn worker, so in-process state is
correct for this deployment.

## Rules for implementation
- Use FastAPI + SQLModel only
- Use existing project architecture (backend modules: `auth/`, `users/`,
  `categories/`, `directories/`, `documents/`, `user_levels/`, `audit/`)
- Each backend module follows: `models.py` (SQLModel + Pydantic read schemas),
  `schemas.py` (request/response schemas), `service.py` (business logic,
  class-based, takes Session), `router.py` (FastAPI router) — this feature is
  middleware-only, so no new module is created; `middleware/ratelimit.py` follows
  the existing `middleware/` pattern (https.py, audit.py, rbac.py)
- Keep routers thin; business logic belongs in services
- Use `CurrentUser` from `core/dependencies.py` for user injection
- Use `AdminUser` for admin-only endpoints
- Add new endpoints to `ROUTE_PERMISSION_MAP` in `middleware/rbac.py` (no new
  endpoints in this spec — nothing to add)
- Use SQLModel / parameterized queries only
- Use JWT access + refresh token auth (core/security.py)
- Hash passwords with bcrypt 4.0.1 (do not upgrade)
- Python: 4-space indent, `snake_case`
- TypeScript: 2-space indent, `PascalCase` components, `camelCase` hooks/stores
- Frontend API files import `apiClient` from `./client`, not `apiRoot` from `./base`
- Never expose secrets or sensitive data in logs (log method, path, rule, IP,
  retry seconds — never tokens, passwords, or request bodies)
- Use `.env` for configuration only (never commit `.env`)
- Maintain audit trail via `AuditService.log_event()` (audit/service.py) —
  exception for this spec: rate-limit rejections are NOT audit events (DB
  writes during a flood are exactly what we are defending against); they are
  logged with the `dms.ratelimit` logger
- Audit logs are immutable (no PUT/PATCH/DELETE endpoints)
- Tests use SQLite in-memory; patch `engine` in `core.database`,
  `middleware.rbac`, `middleware.audit`
- Azure AD: use `cryptography` library for JWK parsing (not `jwk.construct()`)
- No new dependencies unless explicitly approved
- Add/update tests for every implemented feature
- Middleware registration order in `main.py` must stay: rbac, audit, rate limit,
  https, CORS (last registered = outermost); do not reorder other middlewares
- Rate-limit settings are read from `settings` at request time (not captured at
  import) so tests can monkeypatch them, mirroring `FORCE_HTTPS`
- Client IP for throttling must follow the trusted rule above
  (`X-Real-IP` → last `X-Forwarded-For` → `client.host`); do not copy the
  audit helper's first-value rule — it is spoofable through nginx
  `$proxy_add_x_forwarded_for`

## Definition of done
- [ ] `pytest tests/test_rate_limiting.py` — all tests pass, covering:
  - default settings are enabled (`RATE_LIMIT_ENABLED` default `True`)
  - login: after `RATE_LIMIT_AUTH_REQUESTS` POSTs within the window, the next
    one returns 429 with `Retry-After` (≥1) and JSON `detail`
  - recovery: after the window elapses (fake clock), requests succeed again
  - default rule: non-login `/api/v1` requests get 429 after
    `RATE_LIMIT_REQUESTS` hits from the same IP
  - `/health` (and `/docs`) never return 429 even when limits are tiny
  - with `RATE_LIMIT_ENABLED=false` (the conftest default) no request is ever
    throttled
  - buckets are isolated per client IP (`X-Real-IP` / `X-Forwarded-For`
    precedence), so one IP flooding does not lock out another
  - the 429 response carries `Access-Control-Allow-Origin` (CORS is outermost)
  - `Limiter` unit tests: token accounting, refill after window, retry-after
    computation, key-cap pruning, `reset()`
- [ ] Full suite at documented baseline: `2 failed, 598 passed, 14 errors`
  (the 2 + 14 are the known pre-existing failures; passed count grows by the
  new tests) — proves the conftest disable keeps the rest of the suite
  unaffected
- [ ] Manual check with `uvicorn main:app` + `curl -H "X-Real-IP: 1.2.3.4"`
  hammering `/api/v1/auth/login`: after 10 rapid attempts the 11th returns 429
  with `Retry-After`; a different `X-Real-IP` is unaffected
- [ ] `dms.conf` contains `limit_req_zone` + `limit_req ... limit_req_status 429`
  on `location /api/`; reviewed for nginx http-context placement
  (`sudo nginx -t` on the server after deploy — no local nginx)
- [ ] `.env.example` documents all five rate-limit variables; `requirements.txt`
  unchanged (no new dependencies)
- [ ] `git diff requirements.txt` empty; `grep -r "RATE_LIMIT" core/config.py
  .env.example` shows matching names
