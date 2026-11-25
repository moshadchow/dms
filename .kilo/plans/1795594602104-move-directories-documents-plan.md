# Implementation Plan: Move Directories and Documents (Spec 37)

## Overview
Implement directory and document move operations with full access control, audit logging, and cross-category support within the same company.

---

## Phase 1: Schemas

### 1.1 `backend/documents/schemas.py`
- Add `DocumentMoveRequest` schema:
  ```python
  class DocumentMoveRequest(BaseModel):
      new_directory_id: int = Field(..., description="Target directory ID")
  ```

---

## Phase 2: Service Layer

### 2.1 `backend/directories/service.py` — `move_directory` method
**Signature:**
```python
def move_directory(
    self,
    directory_id: int,
    new_parent_id: Optional[int],
    current_user: User,
) -> Directory:
```

**Validation logic:**
1. **Source access**: `ensure_directory_access(session, current_user, directory_id)` — requires direct access (write), not navigation-only.
2. **Destination access**:
   - If `new_parent_id` is not None: `ensure_directory_access(session, current_user, new_parent_id)`
   - If `new_parent_id` is None: `ensure_category_access(session, current_user, directory.category_id)` (root move)
3. **Same company**: Verify `directory.category.company_id == current_user.company_id` and destination category matches.
4. **Cycle prevention**: Walk ancestors of `directory_id` up to root; if `new_parent_id` appears in chain → reject (400).
5. **Name conflict**: Check if a sibling directory with the same `name` exists under `new_parent_id` (or root of category).
6. **Category change**: If `new_parent_id` points to a directory in a different category:
   - Update `category_id` for the moved directory AND all descendants recursively.
   - Preserve `UserDirectoryLink` grants (they reference directory IDs, which don't change).
7. **Mutation**:
   - `directory.parent_id = new_parent_id`
   - `directory.updated_at = datetime.utcnow()`
   - `session.commit()`, `session.refresh(directory)`
8. **Audit**: `AuditService.log_event(action=MOVE_DIRECTORY, module=DIRECTORIES, entity_name="directory", entity_id=str(directory_id), old_value={"parent_id": old_parent_id, "category_id": old_category_id}, new_value={"parent_id": new_parent_id, "category_id": new_category_id}, description=f"Moved directory '{directory.name}'", user=current_user)`
9. **Return**: `DirectoryRead(**directory.model_dump())`

### 2.2 `backend/documents/service.py` — `move_document` method
**Signature:**
```python
def move_document(
    self,
    document_id: int,
    new_directory_id: int,
    current_user: User,
) -> DocumentRead:
```

**Validation logic:**
1. **Source document access**: `_get_orm(document_id, current_user)` (uses `ensure_document_access` internally)
2. **Destination directory access**: `ensure_directory_access(session, current_user, new_directory_id)`
3. **Same company**: Verify source directory's category and destination directory's category both belong to `current_user.company_id`.
4. **Cross-category allowed** within same company.
5. **Mutation**:
   - `old_directory_id = doc.directory_id`
   - `doc.directory_id = new_directory_id`
   - `doc.updated_at = datetime.utcnow()`
   - `session.add(doc)`, `session.commit()`, `session.refresh(doc)`
6. **Update variants**: For each `DocumentVariant` linked to `doc.id`:
   - `variant.directory_id = new_directory_id`
   - `variant.category_id = new_directory.category_id`
   - `variant.updated_at = datetime.utcnow()`
7. **Audit**: `AuditService.log_event(action=MOVE_DOCUMENT, module=DOCUMENTS, entity_name="document", entity_id=str(document_id), old_value={"directory_id": old_directory_id, "category_id": old_category_id}, new_value={"directory_id": new_directory_id, "category_id": new_category_id}, description=f"Moved document '{doc.title}'", user=current_user)`
8. **Return**: `self._to_read(doc)`

---

## Phase 3: Routers

### 3.1 `backend/directories/router.py`
- Add endpoint:
  ```python
  @router.patch(
      "/{directory_id}/move",
      response_model=DirectoryRead,
      summary="Move directory to a new parent",
      dependencies=[Depends(require_permission(PermissionAction.UPDATE))],
  )
  def move_directory(
      directory_id: int,
      payload: DirectoryMoveRequest,
      current_user: CurrentUser,
      session: Session = Depends(get_session),
  ):
      return DirectoryService(session).move_directory(
          directory_id,
          payload.new_parent_id,
          current_user,
      )
  ```

### 3.2 `backend/documents/router.py`
- Add endpoint:
  ```python
  @router.patch(
      "/{document_id}/move",
      response_model=DocumentRead,
      summary="Move document to a different directory",
      dependencies=[Depends(require_permission(PermissionAction.UPDATE))],
  )
  def move_document(
      document_id: int,
      payload: DocumentMoveRequest,
      current_user: CurrentUser,
      session: Session = Depends(get_session),
  ):
      return DocumentService(session).move_document(
          document_id,
          payload.new_directory_id,
          current_user,
      )
  ```

---

## Phase 4: RBAC Middleware

### 4.1 `backend/middleware/rbac.py`
Add to `ROUTE_PERMISSION_MAP`:
```python
("PATCH", "/api/v1/directories"): PermissionAction.UPDATE,
("PATCH", "/api/v1/documents"): PermissionAction.UPDATE,
```
*Note: The longest-prefix match will handle `/directories/{id}/move` and `/documents/{id}/move` since they start with the base path.*

---

## Phase 5: Tests

### 5.1 `backend/tests/test_move_directories.py`
Test cases:
- Valid same-category move (subdirectory → root, root → subdirectory, subdirectory → sibling)
- Cross-category move within same company (updates subtree `category_id`)
- Cycle prevention (move parent into child)
- Name conflict rejection (duplicate sibling name)
- Access denied: no source access, no destination access
- Navigation-only access insufficient (write required)
- SuperAdmin mutation blocked (403)
- Cross-company rejection
- `updated_at` changes
- `MOVE_DIRECTORY` audit event recorded
- Directory grants preserved after move

### 5.2 `backend/tests/test_move_documents.py`
Test cases:
- Valid same-category move
- Cross-category move within same company
- Access denied: no source access, no destination access
- Navigation-only access insufficient
- SuperAdmin mutation blocked (403)
- Cross-company rejection
- `updated_at` changes
- `MOVE_DOCUMENT` audit event recorded
- Private variants updated (category_id, directory_id)

---

## Validation Checklist
- [ ] `pytest tests/test_move_directories.py -q` passes
- [ ] `pytest tests/test_move_documents.py -q` passes
- [ ] `pytest -q` passes (2 baseline failures, 686 passed)
- [ ] `ruff check .` passes
- [ ] `black .` passes
- [ ] `mypy backend/` passes

---

## Dependencies & Order
1. Schemas (no deps)
2. Services (depends on schemas, access control, audit)
3. Routers (depends on services)
4. RBAC (standalone)
5. Tests (depends on all above)

---

## Edge Cases Handled
| Scenario | Handling |
|----------|----------|
| `new_parent_id` = null | Promote to root of current category |
| Destination in different category | Update `category_id` for moved dir + all descendants |
| Document move cross-category | Update `Document.directory_id` + all variant metadata |
| SuperAdmin attempt | Return 403 in service layer |
| Cycle detection | Walk ancestor chain before mutation |
| Duplicate name | Query siblings before commit |
| Navigation-only grant | Reject with 404 (oracle avoidance) |

---

## Files Modified
1. `backend/documents/schemas.py` — add `DocumentMoveRequest`
2. `backend/directories/service.py` — add `move_directory`
3. `backend/documents/service.py` — add `move_document`
4. `backend/directories/router.py` — add move endpoint
5. `backend/documents/router.py` — add move endpoint
6. `backend/middleware/rbac.py` — add PATCH routes to map
7. `backend/tests/test_move_directories.py` — new test file
8. `backend/tests/test_move_documents.py` — new test file