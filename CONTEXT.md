# Domain Glossary

## Core Entities

- **Document** — The central entity. A file stored in the system with metadata (title, type, size, status). Documents live in directories and are linked to user levels for visibility control.
- **Directory** — A folder in the category tree. Documents are organized under directories. Directories belong to exactly one category.
- **Category** — A top-level organizational unit (e.g., Finance, HR). Each category has directories. Users are linked to categories for access.
- **User** — An authenticated person. Has a role (Admin, Maker, Checker, Auditor), a user level, and category links.
- **UserLevel** — A visibility tier (High, Medium, Low). Documents are linked to user levels; users can only see documents matching their level. Admin bypasses all level restrictions.

## Authorization

- **Role** — Named permission set (Admin, Maker, Checker, Auditor). Users have one or more roles.
- **Permission** — A specific action (view, download, create, update, delete) that can be granted to a role.
- **RBAC** — Role-Based Access Control. Enforced via `middleware/rbac.py` (route-level) and `core/dependencies.py` (per-endpoint).
- **ApprovalPolicy** — The logic that determines which users are eligible to act on a workflow step, based on step approvers and document user-level visibility. Lives in `workflow/approval_policy.py`.

## Workflow

- **WorkflowDefinition** — A template for an approval process. Has ordered steps, each with approvers (users or roles) and an approval mode (sequential or parallel).
- **WorkflowStep** — One stage in a workflow definition. Contains approvers and an approval mode.
- **WorkflowInstance** — A running workflow against a specific document. Tracks current step, status, and history.
- **WorkflowAction** — An approval action (approve, reject, return, clarify, forward) taken by an approver on an instance.
- **WorkflowHistory** — An event log entry for a workflow instance (submitted, step_advanced, approved, etc.).

## Memos

- **Memo** — A document draft backed by an HTML file. Created from a rich-text editor, linked to user levels for visibility, and can be submitted for workflow approval.
- **MemoAttachment** — A link between a memo and another document (attachment).

## Signatures

- **Signature** — An image file (e-signature upload or wet-signature canvas capture) stored per-user. Used in workflow approval actions and memo authorship.

## Audit

- **AuditLog** — An immutable record of significant system events. Written by `AuditService` to the `audit_logs` table.
- **AuditService** — The single adapter for audit logging. Used by all service modules.
