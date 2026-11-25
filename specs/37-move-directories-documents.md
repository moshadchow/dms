# Spec: Move Directories and Documents

## Overview

This feature enables users to move directories and uploaded documents to another location, either within the same category or to a different category in the same company.

Users with UPDATE permission can:

- Move a directory by changing its parent directory and, when necessary, its category.
- Move a document by changing its containing directory.

The operation validates source and destination access, prevents circular directory references, preserves tenant boundaries, and records immutable audit events.

## Depends on

- Step 28: Subdirectory-level access (directory grants and navigation)
- Step 29: Parent directory navigation (tree traversal)
- Step 33: Document sorting and filtering (directory context)

## Routes

- `PATCH /api/v1/directories/{directory_id}/move` — Move a directory to a new parent or category — requires UPDATE permission.
- `PATCH /api/v1/documents/{document_id}/move` — Move a document to another directory — requires UPDATE permission.

## Database changes

No database changes. Existing `Directory.parent_id`, `Directory.category_id`, and `Document.directory_id` columns are used.

## Files to change

- `backend/directories/models.py` — Add `DirectoryMove` schema.
- `backend/directories/service.py` — Add `move_directory` method.
- `backend/directories/router.py` — Add move endpoint.
- `backend/documents/models.py` — Add `DocumentMove` schema.
- `backend/documents/service.py` — Add `move_document` method.
- `backend/documents/router.py` — Add move endpoint.
- `backend/middleware/rbac.py` — Add routes to `ROUTE_PERMISSION_MAP`.
- `backend/tests/` — Add directory and document move coverage.

## Files to create

None.

## New dependencies

No new dependencies.

## Rules for implementation

- Use FastAPI and SQLModel only.
- Keep routers thin; put validation and mutation logic in service classes.
- Both endpoints require `require_permission(PermissionAction.UPDATE)`.
- Use `CurrentUser` for user injection.
- Enforce company scoping: source and destination must belong to the current user's company.
- SuperAdmin users must be denied mutations at the service layer with `403`.
- Non-admin users must have direct directory access to both the source and destination. Navigation-only access is insufficient.
- Update `updated_at` on every moved entity.
- Record successful moves with `AuditService.log_event()` using `MOVE_DIRECTORY` or `MOVE_DOCUMENT`.
- Audit logs remain immutable.
- Do not expose storage paths in API responses.
- Use SQLModel/parameterized queries only.
- Add or update tests for every implemented behavior.

### Implementation constraints

#### Directory move

The request body supports moving under a new parent, optionally in another category:

```json
{
  "new_parent_id": 123
}
```

Use `"new_parent_id": null` to move the directory to the root of its current category.

Rules:

- The destination parent must exist and be accessible to the user.
- A directory cannot be moved under itself or any of its descendants.
- Moving beneath a parent in another category moves the directory and its entire descendant subtree into that parent’s category.
- When a subtree changes category, update `category_id` for every moved descendant directory.
- Update `directory_id`-linked documents only where necessary through their directory relationship; documents remain in their existing directory rows.
- Preserve directory-grant semantics. Existing grants remain attached to their directory IDs, so access follows the moved directory/subtree.
- Reject a move if the destination already has a sibling directory with the same name.
- Moving to root level does not change the category unless the API explicitly supports a target category ID.

#### Document move

The request body is:

```json
{
  "new_directory_id": 456
}
```

Rules:

- The destination directory must exist and be accessible to the user.
- Same-category moves are allowed.
- Cross-category moves are allowed only when both source and destination categories belong to the current user’s company.
- Update `Document.directory_id`; the document’s effective category is derived from its destination directory.
- Private document variants must remain valid. If variant metadata stores `category_id` and `directory_id`, update it to match the moved document’s destination.
- The initial implementation may retain the existing `storage_path`, since storage is company-relative and document authorization is based on `directory_id`. Do not expose this internal path.

## Definition of done

- [ ] Directory move endpoint accepts `new_parent_id`, including `null` for root.
- [ ] Document move endpoint accepts `new_directory_id`.
- [ ] Same-category directory and document moves work.
- [ ] Cross-category directory moves update the moved subtree’s `category_id`.
- [ ] Cross-category document moves work within the same company.
- [ ] Circular directory moves are rejected.
- [ ] Destination sibling-name conflicts are rejected.
- [ ] Source and destination access is required for non-admin users.
- [ ] Cross-company moves are rejected.
- [ ] SuperAdmin mutations return `403`.
- [ ] `updated_at` is updated.
- [ ] `MOVE_DIRECTORY` and `MOVE_DOCUMENT` audit events are recorded.
- [ ] RBAC middleware maps both PATCH routes to UPDATE permission.
- [ ] Tests cover valid same-category moves, valid cross-category moves, cycle prevention, access denial, tenant isolation, duplicate names, variant metadata updates, and SuperAdmin restrictions.
- [ ] `pytest -q` passes apart from the two known baseline failures.
- [ ] `ruff check .`, `black .`, and `mypy backend/` pass.