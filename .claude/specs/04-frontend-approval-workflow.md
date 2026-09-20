# Spec: Frontend for Approval Workflow — Foundation, Submission & Signature & History Phases

## Overview
This spec covers the complete frontend implementation for the Approval Workflow system across three phases: Foundation (admin workflow configuration), Submission (document submission for approval), and Signature & History (signature capture, approval actions, and history tracking). The backend is already complete — this spec focuses exclusively on React/Vite frontend work to make the workflow features accessible through the UI.

## Depends on
- Phase 1 backend: workflow/ module, WorkflowDefinitionService, admin config API endpoints — complete
- Phase 2 backend: submit-for-approval, pending queue, ApprovalActionService — complete
- Phase 3 backend: SignatureService, workflow_history, remarks — complete
- Frontend infrastructure: apiClient from ./client, Zustand auth store, ProtectedRoute, AppLayout — complete

## Routes
No new backend routes needed — all workflow API endpoints already exist.

Frontend routes to add or verify:
- GET /approvals/pending — pending approvals for current user — logged-in
- GET /approvals/history — my submitted instances — logged-in
- GET /admin/workflows — admin workflow definition config — admin

## Database changes
No database changes — all tables and migrations already exist.

## Templates
No Jinja2 templates — frontend is React/Vite SPA.

## Files to change

### Bug fixes (critical)
1. dms-app/src/api/workflow.api.ts — Add missing getInstanceHistory(id) method. The ApprovalHistoryPage calls it but it does not exist. The backend returns history embedded in WorkflowInstanceDetailRead via GET /workflow-instances/{id}, so this method should call getInstance(id) and return detail.history, OR the page should be refactored to use getInstance(id) directly (preferred — avoids redundant call).

2. dms-app/src/pages/ApprovalHistoryPage.tsx — Fix document_name references (lines ~172, ~349) to use document_title (matching the WorkflowInstance type definition).

### Navigation
3. dms-app/src/components/layout/Sidebar.tsx — Add Pending Approvals and My Submissions nav links in the bottom nav section (visible to all logged-in users, not just admin). Show a pending-count badge on Pending Approvals if a workflowStore provides the count.

### Admin workflow config (Foundation phase)
4. dms-app/src/pages/AdminPage.tsx — Add a new tab "workflows" to the Tab union type. Render a WorkflowConfigPanel component when active.

5. dms-app/src/components/admin/WorkflowConfigPanel.tsx — (new) Admin panel for managing workflow definitions. Features: list all definitions in a table (name, category, steps count, active status), Create Workflow button opens WorkflowFormModal, edit/deactivate/activate actions per row, filter by category and active status.

6. dms-app/src/components/admin/WorkflowFormModal.tsx — (new) Modal form for creating/editing workflow definitions. Features: fields for name, description, document category dropdown, dynamic step builder with add/remove steps each having step_order, step_name, approval_mode, per-step approver management with users or roles and priority, uses workflowApi.create() / workflowApi.update(), validation requiring at least 1 step and unique step_order.

### Store
7. dms-app/src/store/workflowStore.ts — (new) Zustand store for workflow UI state: pendingCount for badge display, refreshPendingCount() that fetches getPendingInstances({ limit: 1 }) and reads total, auto-refresh on login and after act_on_instance calls.

### Signature integration improvements
8. dms-app/src/pages/PendingApprovalPage.tsx — Verify signature upload works correctly with the action modal. Ensure the signature blob is uploaded before the action is submitted, and that signature_id is passed in the payload.

### Routes
9. dms-app/src/App.tsx — Verify /approvals/pending, /approvals/history routes exist. Add /admin/workflows route if using a dedicated page (or rely on AdminPage tab).

## Files to create

| File | Purpose |
|------|---------|
| dms-app/src/components/admin/WorkflowConfigPanel.tsx | Admin workflow definitions list + CRUD UI |
| dms-app/src/components/admin/WorkflowFormModal.tsx | Create/edit workflow definition modal |
| dms-app/src/store/workflowStore.ts | Zustand store for pending count badge + workflow UI state |

## New dependencies
No new dependencies — all required packages (react, zustand, react-hot-toast, clsx) are already installed.

## Rules for implementation
- Use existing project architecture — frontend API files import apiClient from ./client, not apiRoot from ./base
- TypeScript: 2-space indent, PascalCase for components, camelCase for hooks/stores/utils
- React components use inline styles with CSS variables (var(--surface), var(--border), var(--text), etc.)
- Follow existing Button, Badge, Modal, ConfirmDialog component patterns from components/ui/
- Follow AdminPage.tsx tab pattern for adding the workflows tab
- Follow Sidebar.tsx NavBtn pattern for adding navigation links
- Zustand store follows authStore.ts conventions (simple state + actions, no complex middleware)
- Never expose secrets or sensitive data in logs
- Use .env for configuration only (never commit .env)
- Maintain audit trail — backend already handles this via AuditService.log_event()
- Tests use SQLite in-memory; patch engine in core.database, middleware.rbac, middleware.audit
- No new backend dependencies

## Definition of done
- [ ] npm run build passes with zero TypeScript errors
- [ ] Sidebar shows Pending Approvals and My Submissions links for all logged-in users
- [ ] Sidebar shows a badge with pending approval count on Pending Approvals
- [ ] /approvals/pending page loads, displays pending instances, and approve/reject/return actions work with optional signature
- [ ] /approvals/history page loads, displays submitted instances, and detail modal shows approval timeline
- [ ] Admin page has a Workflows tab that lists workflow definitions
- [ ] Admin can create a new workflow definition via modal form (name, category, steps, approvers)
- [ ] Admin can edit, activate, and deactivate workflow definitions
- [ ] No console errors or runtime exceptions on any workflow page
- [ ] document_title displays correctly in ApprovalHistoryPage (not undefined)
