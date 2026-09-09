# Plan: ADMIN Self-Edit Company Profile — Read-Only Display

## Problem
When an ADMIN edits their own account, the Company Profile section shows:
> No active companies available. Create a Company Profile first.

This is incorrect — the ADMIN already has a company assigned via `users.company_id`. The frontend tries to fetch a list of companies to populate a dropdown, but when the list is empty or the fetch fails, it shows this error. The real fix: for ADMIN self-edit, display the assigned company name as read-only text instead of a dropdown.

## Current State (Verified)

### Backend
- `users/models.py:146`: `company_id: Optional[int]` FK on `User`
- `users/models.py:171-173`: `company: Optional["Company"] = Relationship(...)` with selectin lazy load
- `users/models.py:235-245`: `UserRead` returns `company: Optional[CompanyRead] = None`
- `users/models.py:217-224`: `UserUpdate` has `company_id: Optional[int] = None`
- `users/service.py:244-338`: `update_user()` — company assignment logic at lines 299-315, only allows company changes for ADMIN-role users, no self-edit guard
- `users/router.py:59-61`: `GET /me` returns `UserRead` with company included
- `users/router.py:73-80`: `PATCH /{user_id}` passes `current_user` to service

### Frontend
- `UserFormModal.tsx:33-34`: Gets `currentUser` from auth store
- `UserFormModal.tsx:37`: `isEditingAdmin = editing?.roles.some((r) => r.name === 'admin')`
- `UserFormModal.tsx:52-61`: Fetches company list when `isSuperAdmin || isEditingAdmin`
- `UserFormModal.tsx:218-236`: Company Profile section — shows dropdown when `(!editing && isSuperAdmin) || (editing && isEditingAdmin)`, shows "No active companies" error when list is empty
- `UserFormModal.tsx:111-114`: Submit sends `company_id` when `isEditingAdmin`
- `authStore.ts:33`: `user: User | null` — the current user has `company: CompanySummary | null`
- `user.types.ts:48-61`: `User` interface includes `company: CompanySummary | null`

### Key Insight
The `editing` prop (the user being edited) already contains `company: CompanySummary | null` from the API response. The current user (`currentUser`) also contains `company: CompanySummary | null`. No backend changes needed for data — just frontend UX logic.

## Changes

### 1. Frontend: `dms-app/src/components/admin/UserFormModal.tsx`

**Add self-edit detection** (after line 40):
```typescript
const isSelfEdit = !!editing && currentUser?.id === editing.id
```

**Replace Company Profile section** (lines 217-236):
- When `isSelfEdit && isEditingAdmin`: render read-only display showing `editing.company?.full_name` or appropriate fallback text ("No company assigned")
- When NOT self-edit but `isEditingAdmin`: keep existing dropdown behavior
- When `!editing && isSuperAdmin`: keep existing create-mode dropdown behavior

The read-only display should:
- Use existing form styling (`labelStyle`)
- Show the company full_name as non-editable text
- NOT fetch company list from API (skip the useEffect for self-edit)
- Show "No company assigned" if `editing.company` is null

**Skip company in submit for self-edit** (lines 111-114):
When `isSelfEdit`, do NOT include `company_id` in the update payload. The backend should preserve the existing company.

### 2. Backend: `users/service.py`

**Add self-edit company guard** in `update_user()` (after line 300):
When `current_user.id == user_id` (admin editing self), reject `company_id` changes. This is a defense-in-depth measure — the frontend won't send it, but the backend should still block it.

Specifically:
- Check if `current_user is not None and current_user.id == user_id`
- If so and `data.company_id is not None`, raise 403: "Admin cannot change their own company"
- If company_id is in model_fields_set but value is None (clearing), also block

### 3. Backend Tests: `tests/test_company_assignment.py`

Add 3 new tests:

1. **`test_admin_self_edit_company_unchanged`**: ADMIN self-edits via API (name/email change), verify `company_id` remains unchanged
2. **`test_admin_self_edit_cannot_change_company`**: ADMIN tries to change own `company_id` via direct API call, verify 403
3. **`test_admin_self_edit_preserves_company_for_new_users`**: ADMIN self-edits, then creates a new user, verify new user still inherits the admin's company

## Files to Modify

| File | Change |
|------|--------|
| `dms-app/src/components/admin/UserFormModal.tsx` | Add self-edit detection, read-only company display, skip company in submit for self-edit |
| `users/service.py` | Add self-edit company change guard in `update_user()` |
| `tests/test_company_assignment.py` | Add 3 backend tests for admin self-edit behavior |

## Verification

1. `pytest tests/test_company_assignment.py -v` — all tests pass including new ones
2. `pytest -v` — full regression passes
3. `cd dms-app && npx tsc --noEmit` — TypeScript compiles cleanly
4. `cd dms-app && npm run build` — frontend builds
