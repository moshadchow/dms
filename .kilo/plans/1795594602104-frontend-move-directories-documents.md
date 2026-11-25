# Frontend Implementation Plan: Move Directories and Documents (Spec 37)

## Overview
Implement frontend UI for the backend "Move Directories and Documents" feature (Spec 37). Backend endpoints already exist:
- `PATCH /api/v1/directories/{directory_id}/move` → `{ new_parent_id: number | null }`
- `PATCH /api/v1/documents/{document_id}/move` → `{ new_directory_id: number }`
- `GET /api/v1/directories` → flat list of all accessible directories (for destination picker)

---

## 1. Files to Modify

| File | Purpose |
|------|---------|
| `dms-app/src/api/directories.api.ts` | Add `move` method |
| `dms-app/src/api/documents.api.ts` | Add `move` method |
| `dms-app/src/types/directory.types.ts` | Add `DirectoryMoveRequest` type |
| `dms-app/src/types/document.types.ts` | Add `DocumentMoveRequest` type |
| `dms-app/src/components/directories/DirectoryTree.tsx` | Add "Move" to context menu, integrate move modal |
| `dms-app/src/components/documents/DocumentCard.tsx` | Add "Move" to dropdown menu, integrate move modal |
| `dms-app/src/components/directories/MoveDirectoryModal.tsx` | **NEW** - Destination picker for directory moves |
| `dms-app/src/components/documents/MoveDocumentModal.tsx` | **NEW** - Destination picker for document moves |
| `dms-app/src/pages/DocumentsPage.tsx` | Wire up move modals, handle refresh |

---

## 2. Where Move Actions Appear

### Directory Move
- **Location**: DirectoryTree context menu (right-click on directory node)
- **Condition**: `canUpdate && !node.navigation_only`
- **Icon**: Folder with arrow (📁→)

### Document Move
- **Location**: DocumentCard dropdown menu (three-dot menu)
- **Condition**: `canUpdate`
- **Icon**: File with arrow (📄→)

---

## 3. Destination Picker UX

### Shared Component: `MoveDestinationPicker`
Reusable component used by both modals.

**Props:**
```typescript
interface MoveDestinationPickerProps {
  // For directory moves
  currentDirectoryId?: number
  // For document moves
  currentDocumentDirectoryId?: number
  // Exclude current directory and its descendants (cycle prevention)
  excludeDirectoryId?: number
  // Callback when destination selected
  onSelect: (directoryId: number | null, directoryName: string, categoryName: string) => void
  // Title for modal header
  title: string
  // Loading state
  loading: boolean
}
```

**Data Source:**
- Fetch all accessible directories via `GET /api/v1/directories` (flat list)
- Group by category for display
- Show category name as section headers

**Display Format:**
```
📁 Finance (Category)
  ├── 📂 Root level (null parent)
  ├── 📂 Contracts
  │   └── 📂 2024
  └── 📂 Invoices

📁 HR (Category)
  ├── 📂 Root level
  └── 📂 Policies
```

**Exclusion Rules (client-side, backend validates too):**
1. **Self**: Current directory being moved
2. **Descendants**: Any directory that is a descendant of the source directory (prevent cycles)
3. **Navigation-only**: Directories where `navigation_only === true` (no direct write access)
4. **No UPDATE permission**: Backend enforces, but we can pre-filter if we have permission metadata
5. **Cross-company**: Not applicable - API only returns same-company directories

**Root Option:**
- Show "Root level" (parent_id = null) as a selectable option per category
- For directory moves: allows promoting to root
- For document moves: root is valid destination

---

## 4. Invalid Target Exclusion Logic

### Directory Move (MoveDirectoryModal)
```typescript
// Get flat list of all directories from API
const allDirs = await directoriesApi.listAll()

// Build adjacency map for descendant checking
const childrenMap = buildChildrenMap(allDirs)
const excludedIds = new Set([sourceDirId, ...getDescendants(sourceDirId, childrenMap)])

// Filter
const validDirs = allDirs.filter(d => 
  !excludedIds.has(d.id) &&
  !d.navigation_only &&
  d.category_id === sourceDir.category_id || /* cross-category allowed */ true
)
```

### Document Move (MoveDocumentModal)
```typescript
// Similar but no cycle check needed (documents can't have children)
const validDirs = allDirs.filter(d => 
  d.id !== currentDocDirId &&  // optional: prevent no-op moves
  !d.navigation_only
)
```

---

## 5. Success Refresh Behavior

### Directory Move
1. Call `onRefresh()` (provided by DocumentsPage → `handleTreeRefresh`)
2. `handleTreeRefresh` calls `loadTree(resolvedCategoryId)` and `refreshDirectories()`
3. If moved directory was selected:
   - If moved to different parent: selection stays on same directory ID (still valid)
   - If moved to root: selection stays on same directory ID
4. Navigation path (breadcrumb) updates automatically via tree refresh

### Document Move
1. Call `onRefresh()` (provided by DocumentsPage → `loadDocuments`)
2. Document list refreshes, moved document disappears from current directory
3. If user navigates to new directory, document appears there

---

## 6. Error & Loading Behavior

| Scenario | Behavior |
|----------|----------|
| API error (403, 404, 409, 422) | Show toast with backend error message (via `getErrorMessage`) |
| Network error | Show generic "Move failed" toast |
| Loading | Disable confirm button, show spinner |
| Success | Toast "Directory moved" / "Document moved", close modal, call onRefresh |

---

## 7. Tests to Add/Update

### Unit/Component Tests (if test setup exists)
- `MoveDestinationPicker` renders categories and directories
- Exclusion logic filters self/descendants/navigation-only
- MoveDirectoryModal opens on context menu click
- MoveDocumentModal opens on dropdown click
- Successful move calls onRefresh and closes modal
- Error shows toast and keeps modal open

### Integration Tests
- Directory move updates tree and selection
- Document move updates document list
- Cross-category move works
- Permission gating hides move action when no UPDATE permission

---

## Implementation Order

1. **Types & API**: Add move request types and API methods
2. **Destination Picker**: Create reusable `MoveDestinationPicker` component
3. **Directory Move Modal**: Create `MoveDirectoryModal` using picker
4. **Document Move Modal**: Create `MoveDocumentModal` using picker
5. **DirectoryTree Integration**: Add move to context menu, wire modal
6. **DocumentCard Integration**: Add move to dropdown, wire modal
7. **DocumentsPage Integration**: Add modal state, pass refresh callbacks
8. **Tests**: Add focused tests for new components
9. **Lint/Typecheck/Build**: Run `npm run lint`, `npm run build`, fix issues

---

## Baseline Failures (Unrelated)
- Frontend: None known
- Backend: 2 pre-existing test failures (`test_audit.py`, `test_category_rbac.py`) — do not chase

---

## Backend Validation (Authoritative)
Frontend must **not** bypass backend validation:
- Cycle prevention (directory into own subtree) → backend returns 400
- Cross-company moves → backend returns 403/404
- No UPDATE permission → backend returns 403/404
- Navigation-only access → backend returns 404

Frontend exclusions are UX optimizations only; backend is source of truth.