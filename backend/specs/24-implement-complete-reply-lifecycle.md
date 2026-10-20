# Spec: Reply

## Overview
Step 23 (Correspondence Management) shipped the correspondence module including a backend reply API (`create_reply`, `submit_reply`, `mark_responded`, `get_replies`) and response-tracking fields on the `Correspondence` model, but the React SPA was never wired to use them. Step 24 completes the full Reply-Response lifecycle: a user can reply to a correspondence from its detail page, draft the reply as an outbound correspondence linked to the parent, submit it through the approval workflow (which marks the parent as responded), manually mark an inbound correspondence as responded, and browse the reply thread. It also fixes broken approve/reject/return handlers in `CorrespondenceDetailPage.tsx` that currently fail `tsc`, and adds backend tests for the reply endpoints (which had none).

## Depends on
- Step 23 — Correspondence Management: `correspondence/` module (`models.py`, `service.py`, `router.py`, `schemas.py`), the `Correspondence` response-tracking columns (`response_required`, `response_deadline`, `response_received`, `responded_at`, `parent_correspondence_id`), the reply endpoints, and the `/api/v1/correspondences` entries in `middleware/rbac.py` `ROUTE_PERMISSION_MAP`.

## Routes
No new routes. The following existing backend endpoints are wired into the frontend:
- `POST /api/v1/correspondences/{parent_id}/reply` — create a reply linked to a parent — logged-in, `CREATE`
- `POST /api/v1/correspondences/{id}/submit-reply` — submit a reply for workflow approval and mark the parent responded — logged-in, `UPDATE`
- `POST /api/v1/correspondences/{id}/mark-responded` — mark an inbound correspondence as responded — logged-in, `UPDATE`
- `GET /api/v1/correspondences/{parent_id}/replies` — list replies for a parent — logged-in, `VIEW`

## Database changes
No database changes. All required columns and indexes (`correspondences.response_required`, `response_deadline`, `response_received`, `responded_at`, `parent_correspondence_id`) already exist from step 23.

## Templates
No Jinja2 templates — frontend is a React/Vite SPA. Frontend changes are listed under "Files to change" and "Files to create".

## Files to change
Backend:
- `tests/test_correspondence.py` — add reply lifecycle tests (create reply, list replies, submit-reply marks parent responded, mark-responded, cross-company rejection, terminal-status rejection, permission guards).

Frontend:
- `dms-app/src/api/correspondence.api.ts` — add `getReplies`, `createReply`, `submitReply`, `markResponded`.
- `dms-app/src/pages/CorrespondenceDetailPage.tsx` — fix undefined `handleApprove` / `handleReject` / `handleReturn` (currently referenced but not defined, breaking `tsc`); add a Reply action (opens reply dialog) and a mark-responded action; render the replies thread.
- `dms-app/src/pages/CorrespondenceCreatePage.tsx` — support an optional `parent_id` query param; when present, call `createReply` instead of `create`.
- `dms-app/src/components/correspondence/CorrespondenceForm.tsx` — support an optional pre-set subject and a read-only reply context (lock direction to outbound, banner showing the parent reference).
- `dms-app/src/components/correspondence/CorrespondenceResponsePanel.tsx` — unchanged (kept read-only; response info + parent link already render here). Reply / Mark Responded actions live in the detail page header and the replies thread renders as a dedicated card below the panel, avoiding duplicated controls.

## Files to create
- `dms-app/src/components/correspondence/CorrespondenceReplyDialog.tsx` — modal to compose a reply (subject pre-filled `Re: <parent subject>`, body, optional attachment) and submit it via `createReply`.
- `dms-app/src/components/correspondence/CorrespondenceRepliesList.tsx` — reply thread list with navigation to each reply's detail page.
- `plans/24-reply.md` — this spec.

## New dependencies
No new dependencies.

## Rules for implementation
- Use FastAPI + SQLModel only.
- Use existing project architecture (backend modules: `auth/`, `users/`, `categories/`, `directories/`, `documents/`, `user_levels/`, `audit/`).
- Each backend module follows: `models.py` (SQLModel + Pydantic read schemas), `schemas.py` (request/response schemas), `service.py` (business logic, class-based, takes Session), `router.py` (FastAPI router).
- Keep routers thin; business logic belongs in services.
- Use `CurrentUser` from `core/dependencies.py` for user injection.
- Use `AdminUser` for admin-only endpoints.
- Add new endpoints to `ROUTE_PERMISSION_MAP` in `middleware/rbac.py` (not required here — no new endpoints).
- Use SQLModel / parameterized queries only.
- Use JWT access + refresh token auth (`core/security.py`).
- Hash passwords with bcrypt 4.0.1 (do not upgrade).
- Python: 4-space indent, `snake_case`.
- TypeScript: 2-space indent, `PascalCase` components, `camelCase` hooks/stores.
- Frontend API files import `apiClient` from `./client`, not `apiRoot` from `./base`.
- Never expose secrets or sensitive data in logs.
- Use `.env` for configuration only (never commit `.env`).
- Maintain audit trail via `AuditService.log_event()` (`audit/service.py`) — already done in the existing service methods; do not add a second audit mechanism.
- Audit logs are immutable (no PUT/PATCH/DELETE endpoints).
- Tests use SQLite in-memory; patch `engine` in `core.database`, `middleware.rbac`, `middleware.audit` (existing `conftest.py` already does this).
- Azure AD: use `cryptography` library for JWK parsing (not `jwk.construct()`).
- No new dependencies unless explicitly approved.
- Add/update tests for every implemented feature.

## Definition of done
1. `pytest tests/test_correspondence.py` passes, including new tests that verify: creating a reply links it via `parent_correspondence_id`; replies are listed under `GET /{parent_id}/replies`; `submit-reply` submits the reply and marks the parent `response_received`; `mark-responded` sets `response_received` + `responded_at` and records a movement; replies from another company are rejected; replies to terminal-status parents are rejected.
2. `cd dms-app && npm run build` succeeds (runs `tsc` + Vite) — proving `handleApprove` / `handleReject` / `handleReturn` are fixed.
3. `cd dms-app && npm run lint` passes.
4. In the running app: an inbound correspondence detail page shows a Reply action; composing a reply pre-fills subject `Re: <parent subject>` and creates an outbound correspondence whose detail page links back to the parent reference.
5. Submitting the reply runs the workflow and sets the parent's response to "received" with an updated `responded_at`.
6. Mark Responded updates the parent's response state and appears in the movement history timeline.
7. The replies thread is visible on the parent detail page, and each reply navigates to its own detail page.