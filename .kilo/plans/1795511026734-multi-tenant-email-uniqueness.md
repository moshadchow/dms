# Login Page Blank Content Investigation Plan

## Symptom
`/login` renders an empty/blank page; email and password fields are not visible.

## Likely Root Causes
1. Runtime render failure inside `LoginPage` caught by `ErrorBoundary`, leaving only blank shell.
2. CSS theme variables (`--bg`, `--text`, `--surface`) may be undefined if `index.css` is not applied or `data-theme` is unset.
3. `showCompanySelector` may be true on initial render, hiding the form behind an unstyled/empty selector.
4. A stale persisted auth state may redirect before render completes.

## Investigation Steps
1. Open browser DevTools on `/login`:
   - Console: capture runtime errors.
   - Elements: inspect `#root` and `.LoginPage` container.
   - Computed styles: verify `--bg`, `--surface`, `--text`, width, height, display.
2. Confirm `index.css` is loaded and `:root` variables are defined.
3. Check whether `showCompanySelector` is unexpectedly true.
4. Verify `useAuthStore` does not redirect authenticated state.
5. Test with a minimal inline-styled login form to isolate CSS vs component logic.

## Recommended Fix
- Add explicit, theme-independent inline styles for container, card, labels, and inputs as a fallback.
- Guard `showCompanySelector` so it only displays when company options exist.
- Ensure `useEffect` does not clear state in a way that triggers remount loops.
- Add a visible fallback/error boundary message for login render failures.

## Validation
- Light and dark themes.
- Desktop, tablet, and mobile widths.
- No console errors.
- Email/password inputs visible and focusable.