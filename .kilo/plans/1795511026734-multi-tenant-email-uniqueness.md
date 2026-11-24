# Investigation and Fix Plan: Duplicate-Email Company Selection

## Root Cause Candidates
1. Backend candidate filtering: `AuthService.login` only includes users whose password verifies. If the duplicate accounts have different passwords, only one authenticates, so no selection list is returned.
2. Frontend stale session: cached JWT/localStorage may redirect to dashboard before login.
3. Company association validity: one or more duplicate accounts may be inactive or lack passwords.

## Evidence
- `snm-user1@dms.local` exists under company 1 and company 2, both active local users with passwords.
- Backend returns `requires_company_selection=true` only when more than one password-valid candidate exists.

## Required Changes
### Backend
- Decide authentication model:
  - If all duplicate accounts share one password, current backend logic is sufficient.
  - If passwords differ, switch to company-first login: collect email, show associated active companies, then authenticate against selected company.
- Add diagnostic logging of candidate count and valid count (without exposing hashes).
- Ensure `/auth/select-company` validates selection token and company membership.

### Frontend
- Clear auth store before login attempt.
- Handle `requires_company_selection` and render selector.
- Do not navigate to dashboard until tokens are issued.
- Use `/auth/select-company` for final token.

### Database
- Verify duplicate accounts are active and have passwords.
- Verify companies are active.

## Edge Cases
- Inactive company/user excluded from selection.
- Single valid company logs in directly.
- Invalid selection token rejected.
- Cross-company data access blocked by JWT user context.

## Tests
- Duplicate active local users with same password -> selection required.
- Duplicate users with different passwords -> either company-first flow or direct login depending on chosen model.
- Unique email -> direct login.
- Selection token tampering rejected.
- Selected company scopes `/auth/me` and dashboard data.

## Regression Checks
- Existing auth tests.
- Company scoping tests.
- Azure duplicate-email tests.