# Plan: Add Company Column to Users Table

## Current State (Verified)

### Backend — No Changes Needed
- `users/models.py:244`: `UserRead` already returns `company: Optional[CompanyRead] = None`
- `company_profile/models.py:14`: `CompanyRead` includes `short_name`
- `users/service.py:100`: `list_users()` already uses `selectinload(User.company)` — no N+1 risk

### Frontend Types — No Changes Needed
- `user.types.ts:60`: `User` interface already has `company: CompanySummary | null`
- `user.types.ts:38`: `CompanySummary` already has `short_name`

### Frontend Table — Only File to Change
- `UserTable.tsx:98`: Current columns: `['User', 'Email', 'Roles', 'Provider', 'Level', 'Status', 'Joined', 'Actions']`
- The `User` objects passed to `UserTable` already contain `company.short_name` from the API

## Change: `dms-app/src/components/admin/UserTable.tsx`

### 1. Add "Company" to header array (line 98)
Insert `'Company'` after `'Roles'` (logical position per the task spec):
```
['User', 'Email', 'Roles', 'Company', 'Provider', 'Level', 'Status', 'Joined', 'Actions']
```

### 2. Add Company cell in the row (after the Roles `<td>`, before Provider)
```tsx
{/* Company */}
<td style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
  {user.roles.some((r) => r.name === 'superadmin') ? (
    <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>—</span>
  ) : user.company ? (
    <span style={{ fontSize: '0.78rem', fontWeight: 500 }}>{user.company.short_name}</span>
  ) : (
    <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>—</span>
  )}
</td>
```

Logic:
- SUPERADMIN → display `—`
- Non-SUPERADMIN with company → display `company.short_name`
- Non-SUPERADMIN without company → display `—`

## Files to Modify

| File | Change |
|------|--------|
| `dms-app/src/components/admin/UserTable.tsx` | Add "Company" column header + cell rendering |

## Verification

1. `cd dms-app && npx tsc --noEmit` — TypeScript compiles
2. `cd dms-app && npm run build` — Frontend builds
3. `pytest tests/test_company_assignment.py -v` — Existing tests pass
4. `pytest tests/test_superadmin.py -v` — Existing tests pass
