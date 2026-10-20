# Spec: Inbound Correspondence is Never Submitted for Approval

## Overview
The "Submit for Approval" action was available on any correspondence in a submittable status, including **INBOUND received** records. That conflicts with the process-flow design: an inbound record is the original incoming document and must be treated as a received record — approval applies to the **OUTBOUND reply** that answers it. This spec removes the action for inbound records in the UI, enforces the same rule server-side (both correspondence submit endpoints plus the generic workflow-instance endpoint, so it cannot be bypassed over the API), and keeps the existing reply → submit → approval flow unchanged. OUTBOUND and INTERNAL drafts keep their current submit behavior.

## Depends on
- Step 23 — Correspondence Management (`correspondence/` module, status model, `POST /{id}/submit`).
- Step 24 — Reply lifecycle (`POST /{parent_id}/reply`, `POST /{id}/submit-reply`, parent response flagging).
- `workflow/instance_service.py` `submit_instance()` (generic `POST /api/v1/workflow-instances`).
- `middleware/rbac.py` `ROUTE_PERMISSION_MAP` (`POST /api/v1/correspondences/` → `UPDATE`, `POST /api/v1/workflow-instances` → `CREATE`) — unchanged.

## Routes
No new routes. Existing endpoints gain validation:
- `POST /api/v1/correspondences/{id}/submit` — **409** when `direction == inbound`.
- `POST /api/v1/correspondences/{id}/submit-reply` — inherits the same 409 through delegation for replies created with `direction == inbound`.
- `POST /api/v1/workflow-instances` — **409** when the target document belongs to an inbound correspondence (linked via `Correspondence.document_id` **or** `CorrespondenceAttachment.document_id`; any linked inbound record blocks the document, since outbound replies attach the parent's inbound document as `SUPPORTING`).

## Database changes
None. No columns, no migration; `CorrespondenceStatus` enum untouched (`RECEIVED` remains the status of inbound records).

## Files to change
- `correspondence/service.py` — `submit_correspondence()`: reject `CorrespondenceDirection.INBOUND` with 409 before any workflow work; document why `RECEIVED` stays in the allowed-status tuple (inbound-only by construction).
- `workflow/instance_service.py` — new private guard `_reject_inbound_correspondence_document()` called from `submit_instance()` right after the access checks; lazy import of correspondence models (module cycle safety, mirroring how correspondence defers its workflow imports).
- `dms-app/src/pages/CorrespondenceDetailPage.tsx` — `canSubmit` gains `corr.direction !== 'inbound'`, hiding the header button (single UI entry point; list/table/replies expose no submit action).
- `tests/test_correspondence.py` — repurpose `TestInboundSubmitWithAttachment` (inbound submission is no longer legal, so the attachment auto-fallback is exercised on an outbound draft with its backing-document link cleared) and add `TestInboundSubmitRestriction` (service 409, API 409, inbound-direction reply 409, generic workflow-instance 409 for `document_id` link and for attachment link, control: outbound document still 201).

## Files to create
- `specs/25-inbound-correspondence-no-submit-for-approval.md` — this spec.

## New dependencies
None.

## Rules for implementation
- Rule is `direction == inbound`, not status: `RECEIVED`/`ASSIGNED` inbound records are both blocked; outbound/internal drafts (including replies) are unaffected.
- Enforce in the service layer (single choke point shared by `/submit` and `/submit-reply`), never only in the router or the UI.
- Rejection is `409 Conflict` with a detail telling the user to create an outbound reply — consistent with the module's other state conflicts.
- No changes to Memos, workflow definitions/status sync (`_sync_workflow_status`), RBAC maps, audit actions, company scoping, or status enums. Audit continues to log successful `SUBMIT_CORRESPONDENCE` only; rejections are not audited (consistent with existing conflict rejections).
- INTERNAL direction remains submittable (explicit decision).

## Definition of done
- [ ] Inbound correspondence detail page shows no "Submit for Approval" button; `Edit`, `Reply`, `Mark Responded`, assign/forward are unchanged.
- [ ] `POST /api/v1/correspondences/{id}/submit` on an inbound record returns 409; record stays `received` with `workflow_instance_id = NULL`.
- [ ] `POST /api/v1/workflow-instances` with an inbound record's document (direct link or attachment) returns 409; outbound document control still returns 201.
- [ ] Full flow passes: inbound received → no submit → create OUTBOUND reply → `submit-reply` → workflow instance created → parent flagged `response_received` → approve/reject/return sync unchanged.
- [ ] `pytest tests/test_correspondence.py tests/test_correspondence_visibility.py tests/test_workflow.py` green; full `pytest` green.
- [ ] `cd dms-app && npm run build` (typecheck) and `npm run lint` pass.
