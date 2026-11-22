# Plan: Lazy-loaded Global Search for documents in DMS

## Problem

`DocumentsPage.tsx` calls `loadDocuments()` on mount when in global search mode (`isGlobalSearch` true, line 247-255). `loadDocuments` invokes `documentsApi.list()` with `search: search.trim() || undefined`, where `search` starts as `''` → `undefined` → backend returns ALL accessible documents. No debounce, no min-length, no empty-state guidance.

## Root Cause

- Frontend: `useEffect` (lines 247-255) fires `loadDocuments()` immediately on mount in global search mode with an empty search term.
- Backend: `GET /api/v1/documents` accepts optional `search`; when `None`, the service skips the `ilike` filter and returns every document the user can access (service.py:215-219).
- No debounce on search input; no minimum length; results not cleared when input cleared.

## Required Changes

### Frontend — `dms-app/src/pages/DocumentsPage.tsx`

1. **No initial load in global search mode.** In the `useEffect` at lines 247-255, only call `loadDocuments()` when `search.trim()` meets the minimum length. Otherwise set `docData` to `null`/empty and show the empty-state message.
2. **Debounce search input.** Add a debounce (e.g., 300ms) so `loadDocuments` is not called on every keystroke. Use a `useEffect` + `setTimeout`/`clearTimeout` pattern or a `useDebounce` callback. Cancel pending timer on unmount.
3. **Minimum search length.** Require 3 characters (configurable constant `MIN_SEARCH_LEN = 3`). Below that, show guidance text under the input such as "Type at least 3 characters to search" and do NOT call the API.
4. **Empty-state message.** Before any search: "Enter a document name or keyword to search". After a search with no matches: keep existing "No documents match your filters" / "No documents found across accessible directories".
5. **Clear results on clear input.** When `search` is cleared (empty string), set `docData` to `null`/empty so results disappear immediately (don't wait for debounce).
6. **Preserve RBAC, company scoping, pagination, sorting, metadata.** No changes to `documentsApi.list` params or result rendering — `DocumentCard`, `DocumentListResponse`, pagination, sort, file_type filter all unchanged.

### Backend — `backend/documents/router.py` and/or `service.py`

7. **No all-documents return on empty query.** In `list_documents` (service.py:114), when `search` is empty/None AND `directory_id` is None AND `category_id` is None (global search mode), return an empty `DocumentListResponse(total=0, page=1, limit=limit, items=[])` immediately without querying the DB. Directory/category browsing (with `search` omitted) is unaffected.
8. **RBAC/company scoping preserved.** The access-filter logic (service.py:145-194, 196-206) is untouched.

### Tests — Backend

9. Add tests to `backend/tests/test_documents.py`:
   - Global search (no directory_id/category_id) with empty/None `search` → returns empty paginated response (`total=0, items=[]`), not all docs.
   - Global search with valid `search` term → returns matching documents only.
   - Directory listing without `search` still returns documents in that directory (regression).
   - Access control unchanged: non-admin global search respects category/directory grants (no escalation).

### Tests — Frontend

10. No frontend test files exist (`*.test.tsx` glob returned none). If a frontend test harness is available, add tests for: no initial API call on mount, API call only after ≥3 chars, clearing input clears results, debounce reduces call count. Otherwise note as out of scope and rely on backend tests + manual verification via `npm run build`/`lint`.

## Files to Change

- `dms-app/src/pages/DocumentsPage.tsx` — lazy load + debounce + min length + empty state + clear-on-clear
- `backend/documents/service.py` — empty response when no search in global mode
- `backend/tests/test_documents.py` — new backend tests

## Rollback / Risk

- Backend change is additive (early-return empty) — safe to revert.
- Frontend change only affects global search mode; directory browsing (`resolvedDirId` set) unchanged.
- Debounce may slightly delay search results (acceptable UX tradeoff).

## Validation

- `alembic upgrade head` (no DB changes needed — none required)
- `pytest tests/test_documents.py -q` passes
- `npm run build` and `npm run lint` pass from `dms-app/`
- Manual: open `/search`, confirm no documents load until ≥3 chars typed; confirm results clear when input cleared; confirm directory browse still works.

## Decisions (confirmed)

- Minimum search length: **3 characters** (guidance shown below input when shorter)
- Debounce delay: **300ms**
- Backend empty-query behavior: **return empty 200 `DocumentListResponse`** (total=0, items=[]) — safety net; frontend already guards against calling API with empty input
