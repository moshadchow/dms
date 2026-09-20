# Correspondence Management — Implementation Plan

## Guiding Principles

1. **Reuse existing infrastructure.** Correspondence layers business metadata on top of Document, Workflow, Signature, Notification, Audit, and User Level — no second systems.
2. **Follow existing patterns exactly.** Service classes take `Session`, routers use `CurrentUser`/`AdminUser`, RBAC middleware uses `ROUTE_PERMISSION_MAP`, audit uses `AuditService.log_event()`.
3. **Memo is the template.** The correspondence module mirrors `memos/` structurally: create backing Document, store HTML/file, integrate with workflow, generate PDF.
4. **Direction-aware, not direction-bloated.** One `Correspondence` model with a `direction` enum; direction-specific validation in schemas/service, not separate models.

---

## Phase 1: Backend Models & Migration

### 1.1 `correspondence/models.py`

**Enums:**
```
CorrespondenceDirection: INBOUND, OUTBOUND, INTERNAL
CorrespondencePriority: low, normal, high, urgent
CorrespondenceStatus: received, registered, assigned, processing, draft, submitted,
                      pending_approval, returned, rejected, approved,
                      ready_for_dispatch, dispatched, delivered, acknowledged,
                      completed, cancelled, archived
DispatchMethod: email, courier, post, hand_delivery, portal, other
```

**Table `correspondences`:**
| Column | Type | Notes |
|--------|------|-------|
| id | int PK | auto |
| document_id | int FK NOT NULL UNIQUE | 1:1 with Document |
| company_id | int FK NOT NULL | company isolation |
| created_by | int FK NOT NULL | → users.id |
| reference_number | varchar(50) NOT NULL UNIQUE | `COR-{SHORT}-{YYYY}-{SEQ}` |
| direction | enum NOT NULL | INBOUND/OUTBOUND/INTERNAL |
| status | enum NOT NULL | direction-appropriate default |
| subject | varchar(255) NOT NULL | |
| body | text nullable | HTML body (OUT/INTERNAL) |
| priority | enum NOT NULL default normal | |
| category_id | int FK nullable | → categories.id, same company |
| sender_name | varchar(255) nullable | |
| sender_organization | varchar(255) nullable | |
| sender_email | varchar(255) nullable | |
| sender_phone | varchar(50) nullable | |
| recipient_name | varchar(255) nullable | |
| recipient_organization | varchar(255) nullable | |
| recipient_email | varchar(255) nullable | |
| recipient_phone | varchar(50) nullable | |
| date_sent | datetime nullable | set at dispatch |
| date_received | datetime nullable | set at IN creation |
| response_required | bool NOT NULL default false | |
| response_deadline | datetime nullable | required when response_required=true |
| response_received | bool NOT NULL default false | |
| responded_at | datetime nullable | |
| parent_correspondence_id | int FK nullable | self-ref for response linking |
| author_signature_id | int FK nullable | → signatures |
| workflow_instance_id | int FK nullable | → workflow_instances |
| dispatch_method | enum nullable | |
| dispatch_reference | varchar(255) nullable | |
| dispatched_at | datetime nullable | |
| delivered_at | datetime nullable | |
| acknowledged_at | datetime nullable | |
| created_at | datetime NOT NULL | |
| updated_at | datetime NOT NULL | |

**Table `correspondence_movements`:**
| Column | Type | Notes |
|--------|------|-------|
| id | int PK | auto |
| correspondence_id | int FK NOT NULL | |
| from_user_id | int FK nullable | |
| to_user_id | int FK nullable | |
| from_department | varchar(255) nullable | denormalized (no department table) |
| to_department | varchar(255) nullable | |
| action | varchar(50) NOT NULL | assign/forward/return |
| remarks | text nullable | |
| created_by | int FK NOT NULL | actor |
| created_at | datetime NOT NULL | |

**Pydantic schemas:** `CorrespondenceRead`, `CorrespondenceDetailRead`, `CorrespondenceListResponse`, `MovementRead`.

**Key relationships:**
- `Correspondence.document` → `Document` (selectinload)
- `Correspondence.company` → `Company` (selectinload)
- `Correspondence.created_by_user` → `User` (selectinload)
- `Correspondence.category` → `Category` (selectinload, nullable)
- `Correspondence.parent` → self (selectinload, nullable)
- `Correspondence.workflow_instance` → `WorkflowInstance` (selectinload, nullable)

### 1.2 Alembic Migration

Single migration creating both tables with:
- FKs to `users`, `companies`, `documents`, `categories`, `workflow_instances`, `signatures`
- `UNIQUE(reference_number)`
- `UNIQUE(document_id)`
- Indexes on: `company_id`, `direction`, `status`, `priority`, `created_by`, `date_received`, `response_deadline`, `parent_correspondence_id`, `workflow_instance_id`
- Composite indexes: `(company_id, status)`, `(company_id, direction)`, `(company_id, created_at)`

### 1.3 Audit Model Extensions

Add to `audit/models.py`:
- `AuditAction` enum: `CREATE_CORRESPONDENCE`, `UPDATE_CORRESPONDENCE`, `SUBMIT_CORRESPONDENCE`, `ASSIGN_CORRESPONDENCE`, `FORWARD_CORRESPONDENCE`, `DISPATCH_CORRESPONDENCE`, `DOWNLOAD_CORRESPONDENCE`, `DOWNLOAD_FINAL_CORRESPONDENCE`, `COMPLETE_CORRESPONDENCE`, `ARCHIVE_CORRESPONDENCE`
- `AuditModule` enum: add `CORRESPONDENCE`

---

## Phase 2: Backend Service Layer

### 2.1 Storage Extension (`core/storage.py`)

Add `get_correspondence_root(company: Company) -> Path` following the `get_memos_root` pattern:
```
STORAGE_ROOT/<short_name>/correspondence/<user_id>/<uuid>.html
```

### 2.2 Reference Number Generation (`correspondence/service.py`)

**Concurrency-safe strategy:** Use `SELECT ... FOR UPDATE` (row-level locking) on a new `correspondence_sequences` table, or use a DB-level sequence. Since the project uses PostgreSQL in production:

Option A (simplest, PostgreSQL-native):
```sql
CREATE SEQUENCE correspondence_seq_{company_id}_{year} START 1;
```
But sequences per company/year are hard to manage.

Option B (row-level locking, database-agnostic):
```python
# In a transaction:
# 1. Try to INSERT sequence row (company_id, year, last_value=1) with ON CONFLICT DO NOTHING
# 2. SELECT last_value FROM correspondence_sequences WHERE company_id=X AND year=Y FOR UPDATE
# 3. Increment and UPDATE
# 4. Format: COR-{short_name}-{year}-{value:06d}
```

Option C (simplest, recommended):
Use a unique constraint on `reference_number` and a retry loop. On `IntegrityError`, regenerate. Since reference numbers are generated at creation time under a transaction, the probability of collision is near-zero with a microseconds-based random suffix, but the sequential format is required by the spec.

**Chosen approach:** Row-level locking with a `correspondence_sequences` table:
```
correspondence_sequences:
  company_id FK
  year int
  last_value int
  UNIQUE(company_id, year)
```

Service method `_next_reference_number(session, company)`:
1. `SELECT ... FOR UPDATE` on the sequence row
2. If not exists, INSERT with `last_value=1`
3. Increment, UPDATE
4. Return formatted string

This is safe under concurrent requests because `FOR UPDATE` blocks concurrent transactions on the same row.

### 2.3 `CorrespondenceService` Class

**Constructor:** `__init__(self, session: Session)` — same pattern as `MemoService`.

**Internal helpers (reuse from memos where possible):**
- `_get_correspondence_or_404(id)` — fetch with selectinload relationships
- `_check_view_access(correspondence, user)` — admin bypass, then company check + document access + user level
- `_check_edit_access(correspondence, user)` — admin bypass, terminal status check, author check, dispatch immutability
- `_to_read(correspondence)` — ORM → Pydantic before session closes
- `_to_detail(correspondence)` — full detail with relationships
- `_log_audit(action, correspondence, ...)` — wraps `AuditService.log_event()`

**Direction-specific validation:**
- INBOUND: `date_received` required, sender info required, body optional
- OUTBOUND: recipient info required, body required (HTML)
- INTERNAL: recipient must be same-company user, body required

**Public methods:**

| Method | Description |
|--------|-------------|
| `create_draft(data, user)` | Create correspondence + backing Document. IN: accept uploaded file. OUT/INTERNAL: generate HTML body, write to storage. |
| `get_correspondence(id, user)` | Get with access check |
| `list_correspondences(filters, user, skip, limit)` | Paginated list with company scoping, direction/priority/status/search filters |
| `update_correspondence(id, data, user)` | Edit with access check + status + dispatch immutability |
| `submit_correspondence(id, data, user, bg_tasks)` | Delegate to `WorkflowInstanceService.submit_instance()` |
| `assign_correspondence(id, data, user)` | Create movement record, update current_assignee |
| `forward_correspondence(id, data, user)` | Create movement record |
| `dispatch_correspondence(id, data, user)` | Validate approved status, record dispatch metadata |
| `get_movements(id, user)` | List movement history |
| `download_document(id, user)` | Stream backing document file |
| `download_final(id, user)` | Generate/download final PDF |
| `get_next_reference(user)` | Preview next reference number (non-destructive) |
| `mark_delivered(id, user)` | Record delivery acknowledgement |
| `mark_responded(id, correspondence_id, response_id)` | Link response correspondence |

**Creation flow (detail):**
1. Validate direction-specific fields
2. Resolve company from `user.company_id` (reject if None)
3. Validate category belongs to same company (if provided)
4. For INBOUND: validate uploaded file exists
5. Generate reference number (transaction-safe)
6. Create backing Document:
   - OUT/INTERNAL: write HTML to `correspondence/<user_id>/<uuid>.html`, create Document with `file_type=html`
   - INBOUND: the uploaded file was already saved by Document upload; create Document referencing it
7. Create `Correspondence` record
8. Link user levels (reuse `DocumentUserLevelLink`)
9. Commit
10. Audit `CREATE_CORRESPONDENCE`

**Dispatch flow (detail):**
1. Validate status is `approved` or `ready_for_dispatch`
2. Validate dispatch_method, recipient info
3. Set `dispatch_method`, `dispatch_reference`, `dispatched_at`, `date_sent`, `status=dispatched`
4. Create movement record
5. Commit
6. Audit `DISPATCH_CORRESPONDENCE`
7. Send notification (background)

### 2.4 Reused Components

| Component | Source | How Used |
|-----------|--------|----------|
| HTML sanitization | `memos/service.py` `sanitize_memo_html()` | Import directly — same bleach config |
| HTML rendering | `memos/service.py` `render_markdown()` + `build_memo_html()` | Import or duplicate (memo-specific template) |
| PDF generation | `memos/pdf_generator.py` `generate_memo_pdf()` | Extend or create `correspondence/pdf_generator.py` with correspondence-specific header/metadata |
| Access helpers | `core/access.py` | `ensure_document_access()`, `ensure_document_user_level_access()`, `ensure_category_access()` |
| Workflow submission | `workflow/instance_service.py` `submit_instance()` | Call directly via `WorkflowInstanceService(session).submit_instance()` |
| Signature validation | `signatures/service.py` `validate_signature_exists()` | Call directly |
| Audit logging | `audit/service.py` `AuditService.log_event()` | Call after every mutation |
| Storage paths | `core/storage.py` | Add `get_correspondence_root()` |

---

## Phase 3: Backend API Layer

### 3.1 Request Schemas (`correspondence/schemas.py`)

```python
class CorrespondenceCreate(BaseModel):
    direction: CorrespondenceDirection
    subject: str
    body: str | None = None          # required for OUT/INTERNAL
    priority: CorrespondencePriority = normal
    category_id: int | None = None
    # Sender fields
    sender_name: str | None = None
    sender_organization: str | None = None
    sender_email: str | None = None
    sender_phone: str | None = None
    # Recipient fields
    recipient_name: str | None = None
    recipient_organization: str | None = None
    recipient_email: str | None = None
    recipient_phone: str | None = None
    # Dates
    date_received: datetime | None = None  # required for INBOUND
    # Response tracking
    response_required: bool = False
    response_deadline: datetime | None = None
    parent_correspondence_id: int | None = None
    # User levels
    user_level_ids: list[int] = []
    # INBOUND: uploaded document_id (already uploaded via documents endpoint)
    document_id: int | None = None
    # OUTBOUND: author signature
    author_signature_id: int | None = None

class CorrespondenceUpdate(BaseModel):
    subject: str | None = None
    body: str | None = None
    priority: CorrespondencePriority | None = None
    category_id: int | None = None
    sender_name: str | None = None
    sender_organization: str | None = None
    sender_email: str | None = None
    sender_phone: str | None = None
    recipient_name: str | None = None
    recipient_organization: str | None = None
    recipient_email: str | None = None
    recipient_phone: str | None = None
    response_required: bool | None = None
    response_deadline: datetime | None = None
    user_level_ids: list[int] | None = None
    author_signature_id: int | None = None

class CorrespondenceSubmit(BaseModel):
    workflow_definition_id: int
    signature_id: int | None = None

class CorrespondenceAssign(BaseModel):
    to_user_id: int
    remarks: str | None = None

class CorrespondenceDispatch(BaseModel):
    dispatch_method: DispatchMethod
    dispatch_reference: str | None = None
    remarks: str | None = None

class CorrespondenceListParams(BaseModel):
    direction: CorrespondenceDirection | None = None
    priority: CorrespondencePriority | None = None
    status: CorrespondenceStatus | None = None
    category_id: int | None = None
    assigned_user_id: int | None = None
    response_required: bool | None = None
    overdue: bool | None = None
    search: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    company_id: int | None = None  # superadmin only
```

### 3.2 Router (`correspondence/router.py`)

Mounted at `/api/v1/correspondences`.

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| GET | `/` | view | List with filters, pagination |
| POST | `/` | create | Create correspondence |
| GET | `/next-reference` | view | Preview next reference number |
| GET | `/{id}` | view | Detail view |
| PATCH | `/{id}` | update | Update correspondence |
| POST | `/{id}/submit` | update | Submit for workflow approval |
| POST | `/{id}/assign` | update | Assign to user |
| POST | `/{id}/forward` | update | Forward to user |
| POST | `/{id}/dispatch` | update | Mark as dispatched |
| GET | `/{id}/movements` | view | Movement history |
| GET | `/{id}/download` | download | Download backing document |
| GET | `/{id}/download-final` | download | Download final PDF |
| POST | `/{id}/deliver` | update | Mark as delivered |
| POST | `/{id}/acknowledge` | update | Mark as acknowledged |

### 3.3 RBAC Middleware Updates (`middleware/rbac.py`)

Add to `ROUTE_PERMISSION_MAP`:
```python
(GET, "/api/v1/correspondences"): PermissionAction.VIEW,
(POST, "/api/v1/correspondences"): PermissionAction.CREATE,
(GET, "/api/v1/correspondences/next-reference"): PermissionAction.VIEW,
(PATCH, "/api/v1/correspondences/"): PermissionAction.UPDATE,
(POST, "/api/v1/correspondences/"): PermissionAction.UPDATE,  # submit/assign/forward/dispatch
(GET, "/api/v1/correspondences/"): PermissionAction.VIEW,     # movements/download
```

Note: The trailing-slash trick (same as workflow instances) routes `POST /{id}/submit`, `POST /{id}/assign`, etc. through the same `POST /api/v1/correspondences/` prefix entry.

### 3.4 `main.py` Update

Mount the correspondence router:
```python
from correspondence.router import correspondence_router
app.include_router(correspondence_router, prefix="/api/v1", tags=["Correspondence"])
```

---

## Phase 4: Backend PDF Generator

### 4.1 `correspondence/pdf_generator.py`

Create `generate_correspondence_pdf()` following the memo PDF pattern but with correspondence-specific layout:

**Header section:**
- Company name and short name (centered)
- Reference number
- Date, Direction badge, Priority badge

**Metadata table:**
- Subject, Sender, Recipient, Category
- Response requirement and deadline (if applicable)
- Related correspondence reference (if response)

**Body:**
- Sanitized HTML converted via the same `_HTMLToReportLabParser` pattern from memos

**Signatures section:**
- Author signature image
- Approval signatures from workflow

**Dispatch section (if dispatched):**
- Method, reference, date

**Footer:**
- "Document Management System - Correspondence - Generated {date}"

Reuse the `_sanitize_for_reportlab()` and `_apply_inline_formatting()` helpers from the memo PDF generator (import or extract to a shared utility).

---

## Phase 5: Frontend Types & API

### 5.1 `dms-app/src/types/correspondence.types.ts`

```typescript
type CorrespondenceDirection = 'inbound' | 'outbound' | 'internal';
type CorrespondencePriority = 'low' | 'normal' | 'high' | 'urgent';
type CorrespondenceStatus = 'received' | 'registered' | 'assigned' | 'processing'
  | 'draft' | 'submitted' | 'pending_approval' | 'returned' | 'rejected'
  | 'approved' | 'ready_for_dispatch' | 'dispatched' | 'delivered'
  | 'acknowledged' | 'completed' | 'cancelled' | 'archived';
type DispatchMethod = 'email' | 'courier' | 'post' | 'hand_delivery' | 'portal' | 'other';

interface Correspondence {
  id: number;
  document_id: number;
  company_id: number;
  created_by: number;
  reference_number: string;
  direction: CorrespondenceDirection;
  status: CorrespondenceStatus;
  subject: string;
  body: string | null;
  priority: CorrespondencePriority;
  category_id: number | null;
  sender_name: string | null;
  sender_organization: string | null;
  sender_email: string | null;
  sender_phone: string | null;
  recipient_name: string | null;
  recipient_organization: string | null;
  recipient_email: string | null;
  recipient_phone: string | null;
  date_sent: string | null;
  date_received: string | null;
  response_required: boolean;
  response_deadline: string | null;
  response_received: boolean;
  responded_at: string | null;
  parent_correspondence_id: number | null;
  author_signature_id: number | null;
  workflow_instance_id: number | null;
  dispatch_method: DispatchMethod | null;
  dispatch_reference: string | null;
  dispatched_at: string | null;
  delivered_at: string | null;
  acknowledged_at: string | null;
  created_at: string;
  updated_at: string;
  // Nested (from selectinload)
  created_by_user?: User;
  category?: Category;
  parent?: Correspondence;
  workflow_instance?: WorkflowInstance;
}

interface CorrespondenceDetail extends Correspondence {
  document?: Document;
  movements?: CorrespondenceMovement[];
}

interface CorrespondenceMovement {
  id: number;
  correspondence_id: number;
  from_user_id: number | null;
  to_user_id: number | null;
  from_department: string | null;
  to_department: string | null;
  action: string;
  remarks: string | null;
  created_by: number;
  created_at: string;
}

interface CorrespondenceListResponse {
  total: number;
  items: Correspondence[];
}

interface CorrespondenceCreateRequest { /* matches schema */ }
interface CorrespondenceUpdateRequest { /* matches schema */ }
interface CorrespondenceSubmitRequest { workflow_definition_id: number; signature_id?: number; }
interface CorrespondenceAssignRequest { to_user_id: number; remarks?: string; }
interface CorrespondenceDispatchRequest { dispatch_method: DispatchMethod; dispatch_reference?: string; remarks?: string; }
```

### 5.2 `dms-app/src/api/correspondence.api.ts`

```typescript
import apiClient from './client';
// Methods: list, get, create, update, submit, assign, forward, dispatch,
//          getMovements, download, downloadFinal, getNextReference, deliver, acknowledge
// Follow memo.api.ts pattern exactly
```

---

## Phase 6: Frontend Pages

### 6.1 Route Additions (`App.tsx`)

Add under the authenticated section:
```tsx
<Route path="/correspondence" element={<CorrespondenceListPage />} />
<Route path="/correspondence/new" element={<CorrespondenceCreatePage />} />
<Route path="/correspondence/:id" element={<CorrespondenceDetailPage />} />
<Route path="/correspondence/:id/edit" element={<CorrespondenceEditPage />} />
```

### 6.2 Sidebar Updates (`Sidebar.tsx`)

Add a "Correspondence" nav item in the bottom nav section (after Memos, before Pending Approvals). No sub-route filtering like categories — the list page handles direction tabs internally.

### 6.3 `CorrespondenceListPage.tsx`

**Layout:** Similar to `MemoListPage` but with more columns and tab filtering.

**Features:**
- Tab bar: All | Incoming | Outgoing | Internal | My Correspondence | Pending Actions | Overdue
- Each tab applies query params to the API call
- Table columns: Reference, Direction (badge), Subject, Sender/Recipient (direction-aware), Priority (color badge), Status (badge), Assigned To, Response (required/received indicator), Due Date, Created
- Search bar (searches reference, subject, sender, recipient)
- Filters: Priority dropdown, Status dropdown, Category dropdown, Date range
- Pagination (Previous/Next, matching existing pattern)
- "New Correspondence" button (direction selector: Incoming/Outgoing/Internal → routes to create page)

**Priority badge colors:**
- low → gray
- normal → blue
- high → orange
- urgent → red

**Overdue indicator:** Calculated dynamically (response_required && !response_received && deadline < now && status not terminal)

### 6.4 `CorrespondenceDetailPage.tsx`

**Layout:** Two-column grid (similar to `MemoDetailPage`).

**Left column (main):**
- Header: Reference number, direction badge, priority badge, status badge
- Subject
- Sender/Recipient section (direction-aware labels)
- Body (sanitized HTML rendered via `dangerouslySetInnerHTML`)
- Attachments (backing document + linked documents)
- Response information (related correspondence link)

**Right column (sidebar):**
- Metadata card: Category, Created by, Created date, Updated date
- Workflow status (if submitted)
- Current assignment
- Response tracking (deadline, overdue indicator)
- Action buttons (context-dependent):
  - Draft: Edit, Submit, Delete
  - Submitted/Pending: View workflow
  - Approved/Ready: Dispatch
  - Dispatched: Mark Delivered, Mark Acknowledged
  - Inbound: Assign, Forward, Create Response (→ new outbound prepopulated)
- Movement history (collapsible timeline)
- Dispatch information (if dispatched)

### 6.5 `CorrespondenceCreatePage.tsx`

**Flow:**
1. Direction selector (if not pre-selected from list page)
2. Dynamic form based on direction:
   - **INBOUND:** Received date, sender fields, subject, category, priority, response required/deadline, file upload (or reference existing document_id), assigned user, user levels
   - **OUTBOUND:** Recipient fields, subject, category, priority, body (rich text editor), related incoming (searchable dropdown), user levels, author signature
   - **INTERNAL:** Recipient user/department, subject, category, priority, body (rich text editor), user levels
3. Reference preview (fetched from `/next-reference`, displayed as disabled field)
4. Save as Draft button
5. After save: Submit for Approval section (workflow selector + optional signature)

### 6.6 `CorrespondenceEditPage.tsx`

Same form as create, pre-populated. Edit access enforced:
- Disabled in terminal statuses
- Fields locked after dispatch
- Admin bypass

### 6.7 Component Files

| Component | Purpose |
|-----------|---------|
| `CorrespondenceForm.tsx` | Shared create/edit form with direction-aware field rendering |
| `CorrespondenceFilters.tsx` | Search bar + filter dropdowns (reusable across tabs) |
| `CorrespondenceTable.tsx` | Reusable table with columns, badges, action menu |
| `CorrespondenceTimeline.tsx` | Movement history timeline (vertical, like approval history) |
| `CorrespondenceDispatchDialog.tsx` | Modal for dispatch action (method, reference, remarks) |
| `CorrespondenceAssignDialog.tsx` | Modal for assign/forward action (user selector, remarks) |
| `CorrespondenceResponsePanel.tsx` | Shows related incoming/outgoing correspondence |

---

## Phase 7: Notifications

### 7.1 Notification Events

Reuse existing notification infrastructure. Add correspondence-specific notification types:

| Event | Trigger | Recipients |
|-------|---------|------------|
| `correspondence_assigned` | Assign action | Assigned user |
| `correspondence_forwarded` | Forward action | Target user |
| `correspondence_dispatched` | Dispatch action | Creator |
| `correspondence_delivered` | Delivery confirmation | Creator, assignee |
| `response_deadline_approaching` | Background check (future) | Assigned user |
| `response_overdue` | Background check (future) | Assigned user, admin |

For Phase 1, implement assignment and dispatch notifications. SLA reminders can be added as a background task later.

### 7.2 Email Templates (`notifications/templates.py`)

Add templates:
- `build_correspondence_assigned_email()` — subject, reference, assigned by, link
- `build_correspondence_dispatched_email()` — subject, reference, dispatch method

---

## Phase 8: Testing

### 8.1 Test Files

| File | Coverage |
|------|----------|
| `tests/test_correspondence.py` | CRUD, list/filter, company isolation, direction validation, reference generation, movements |
| `tests/test_correspondence_security.py` | Cross-company access, RBAC, user level, path traversal, client field injection |
| `tests/test_correspondence_workflow.py` | Submit, approve, reject, return, resubmit, cancel |
| `tests/test_correspondence_pdf.py` | PDF generation, HTML sanitization, special characters, Unicode |

### 8.2 Key Test Scenarios

**Company isolation:**
- Company A admin cannot access Company B correspondence by ID
- Company A correspondence not visible in Company B search/pagination
- SUPERADMIN with no company selected sees empty results
- SUPERADMIN with Company A selected sees only Company A

**Reference numbers:**
- Sequential per company per year
- Concurrent creation produces unique references
- Preview endpoint does not consume sequence

**Dispatch:**
- Cannot dispatch draft/rejected/returned
- Can dispatch approved
- Dispatch is idempotent (second dispatch blocked)
- Dispatch fields become immutable

**Response tracking:**
- IN→OUT response link works
- Cross-company response link rejected
- Overdue calculated correctly
- Completed response clears overdue

---

## Implementation Order

| Step | Scope | Estimated Files |
|------|-------|----------------|
| 1 | Models + enums + migration | `correspondence/models.py`, `correspondence/__init__.py`, migration file, `audit/models.py` |
| 2 | Storage extension | `core/storage.py` (add 1 method) |
| 3 | Service layer | `correspondence/service.py` |
| 4 | Schemas | `correspondence/schemas.py` |
| 5 | Router | `correspondence/router.py` |
| 6 | RBAC + main.py | `middleware/rbac.py`, `main.py` |
| 7 | PDF generator | `correspondence/pdf_generator.py` |
| 8 | Frontend types | `dms-app/src/types/correspondence.types.ts` |
| 9 | Frontend API | `dms-app/src/api/correspondence.api.ts` |
| 10 | Frontend pages | 4 page files + 7 component files |
| 11 | Sidebar + routing | `Sidebar.tsx`, `App.tsx` |
| 12 | Notifications | `notifications/templates.py` (add templates), `correspondence/service.py` (enqueue calls) |
| 13 | Tests | 4 test files |

---

## Files to Create

```
correspondence/__init__.py
correspondence/models.py
correspondence/schemas.py
correspondence/service.py
correspondence/router.py
correspondence/pdf_generator.py
migrations/versions/<hash>_add_correspondence_tables.py
dms-app/src/types/correspondence.types.ts
dms-app/src/api/correspondence.api.ts
dms-app/src/pages/CorrespondenceListPage.tsx
dms-app/src/pages/CorrespondenceDetailPage.tsx
dms-app/src/pages/CorrespondenceCreatePage.tsx
dms-app/src/pages/CorrespondenceEditPage.tsx
dms-app/src/components/correspondence/CorrespondenceForm.tsx
dms-app/src/components/correspondence/CorrespondenceFilters.tsx
dms-app/src/components/correspondence/CorrespondenceTable.tsx
dms-app/src/components/correspondence/CorrespondenceTimeline.tsx
dms-app/src/components/correspondence/CorrespondenceDispatchDialog.tsx
dms-app/src/components/correspondence/CorrespondenceAssignDialog.tsx
dms-app/src/components/correspondence/CorrespondenceResponsePanel.tsx
tests/test_correspondence.py
tests/test_correspondence_security.py
tests/test_correspondence_workflow.py
tests/test_correspondence_pdf.py
```

## Files to Modify

```
main.py                           # mount correspondence router
middleware/rbac.py                 # add ROUTE_PERMISSION_MAP entries
core/storage.py                   # add get_correspondence_root()
audit/models.py                   # add AuditAction + AuditModule values
notifications/templates.py        # add correspondence email templates
dms-app/src/App.tsx               # add routes
dms-app/src/components/layout/Sidebar.tsx  # add nav item
```

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Reference number collision under concurrency | Row-level locking with `SELECT ... FOR UPDATE` on sequence table |
| Document model has no company_id — company isolation via user levels only | Correspondence table has explicit `company_id` FK; all queries filter by it. Document access uses existing `ensure_document_access()` + `ensure_document_user_level_access()` |
| Memo HTML sanitizer/pdf generator are memo-specific | Import `sanitize_memo_html()` directly (same bleach config). PDF generator: create correspondence-specific version reusing ReportLab parser helpers |
| Status duality (correspondence status vs workflow status) | Correspondence status is the business-level truth. Workflow status is the approval engine's internal state. Correspondence status transitions are driven by workflow status changes AND by explicit business actions (dispatch, deliver, assign). |
| Frontend form complexity (3 directions × many fields) | Single `CorrespondenceForm` with conditional field rendering based on direction. Tabs on list page for direction filtering. |
| Existing workflow forward action returns 501 | Correspondence assign/forward uses its own `correspondence_movements` table, not workflow forward. Independent of workflow forward implementation. |
