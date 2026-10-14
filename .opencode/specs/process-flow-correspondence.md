# Correspondence Management — Complete Process Flow

## 1. Simple Overview

### What It Is

Correspondence Management is a structured system for tracking all formal communications that enter, leave, or circulate within an organization. It answers the question the business needs answered:

> *What came in, from whom, when did it arrive, who is responsible, what action is required, what response was produced, who approved it, when was it sent, and what happened afterward?*

### Why the DMS Needs It

The existing Documents module stores files. It does not track who a letter came from, whether a response is due, who is currently responsible for acting on it, whether it has been dispatched, or whether the recipient acknowledged it. Correspondence Management adds this business-metadata layer on top of the existing Document infrastructure without replacing it.

### What Business Problem It Solves

| Problem | Without Correspondence | With Correspondence |
|---|---|---|
| Incoming letter arrives | Stored as "just a file" | Tracked with sender, date received, response deadline, assignee |
| Response is due in 15 days | No tracking mechanism | System calculates overdue, shows due-soon alerts |
| Letter was dispatched | No dispatch record | Method, reference number, date, delivery status all recorded |
| Who is responsible right now | Manual coordination | Current assignee always visible, movement history preserved |
| Cross-company data leakage | Relies on manual discipline | SQL-level company isolation enforced |

### Types of Correspondence

| Type | Direction | Example |
|---|---|---|
| **Incoming (IN)** | External → Company | Government letter, client complaint, vendor invoice |
| **Outgoing (OUT)** | Company → External | Response letter, contract offer, official notice |
| **Internal** | Department → Department (same company) | Memo from HR to Operations, inter-department request |

### How It Differs from Documents

| Aspect | Documents Module | Correspondence Module |
|---|---|---|
| Purpose | Store and organize files | Track the lifecycle of formal communications |
| Metadata | Title, category, directory | Sender, recipient, direction, status, priority, response tracking, dispatch tracking |
| Status model | ACTIVE / ARCHIVED | 15 statuses across direction-specific lifecycles |
| Reference number | None auto-generated | `COR-{Company}-{Year}-{SEQ:06d}` auto-generated |
| Movement tracking | None | CorrespondenceMovement records (assign, forward, dispatch) |
| Dispatch tracking | None | Method, reference, date, delivery, acknowledgement |
| Response tracking | None | Parent-child self-referencing FK, deadline, SLA |
| Backing entity | IS the document | Has a document, is NOT the document |

---

## 2. The Three Correspondence Types

### A. Incoming (IN)

Documents received by the organization from an external party.

```
External Organization
        ↓
   [ Received ]
        ↓
   [ Registered ]
        ↓
   [ Assigned to responsible person ]
        ↓
   [ Processing / Review ]
        ↓
   Response Required?
   ┌────┴────┐
  NO        YES
   │          │
[Complete]   [Create OUT Response]
                  ↓
             [ Full OUT lifecycle ]
                  ↓
             [ IN Marked Complete ]
```

**When to use:** Any document received from outside the organization — letters, emails from clients, regulatory notices, vendor submissions, court documents.

**Key characteristic:** Requires an existing uploaded document (`document_id` is mandatory). The system does not create the backing document for inbound; the user uploads it.

### B. Outgoing (OUT)

Documents created by the organization and sent to an external party.

```
Company User
     ↓
  [ Draft ] — body written, signature selected
     ↓
  [ Submitted ] — enters workflow
     ↓
  [ Pending Approval ]
     ↓
  [ Approved ] — author signature attached
     ↓
  [ Final PDF Generated ]
     ↓
  [ Dispatched ] — method + reference recorded
     ↓
  [ Delivered / Acknowledged ]
     ↓
  [ Complete ]
```

**When to use:** Response letters, official notifications to clients, contract documents, regulatory submissions, any formal communication leaving the organization.

**Key characteristic:** The system creates the backing HTML document automatically from the body content. The body is mandatory.

### C. Internal

Documents exchanged between users or departments within the same company.

```
Department A User
     ↓
  [ Draft ]
     ↓
  [ Submitted ]
     ↓
  [ Approval (if workflow configured) ]
     ↓
  [ Distributed / Forwarded ]
     ↓
  [ Recipient Action ]
     ↓
  [ Complete ]
```

**When to use:** Inter-departmental requests, internal policy communications, internal memos that need formal tracking, internal directives.

**Key characteristic:** Must remain within the same company. The system validates that the assigned/forwarded user belongs to the same company. Cross-company internal routing is rejected with HTTP 422.

---

## 3. Complete IN Workflow — Step by Step

### Step 1: Receive Document

| Aspect | Detail |
|---|---|
| **Who** | Any user with CREATE permission in the company |
| **Action** | Clicks "New Correspondence" → selects "Incoming" |
| **What happens** | System presents the create form with direction pre-set to `inbound` |
| **Status** | N/A (not yet created) |

### Step 2: Upload Original Document

| Aspect | Detail |
|---|---|
| **Who** | The creating user |
| **Action** | Uploads the original received document (PDF, image, etc.) |
| **What happens** | System stores the file, creates a `Document` record |
| **Backend** | `document_id` is required in the create payload for inbound |
| **Validation** | 422 if `document_id` is missing or the document does not exist |
| **Status** | N/A |

### Step 3: Enter Metadata

| Aspect | Detail |
|---|---|
| **Who** | The creating user |
| **Fields entered** | Subject (required), Sender name/org/email/phone, Date received (auto-set to now if blank), Priority, Category, User levels |
| **What happens** | Data is validated and stored |
| **Backend** | Category validated against company; user levels validated against active levels |
| **Status** | N/A |

### Step 4: Set Response Requirement

| Aspect | Detail |
|---|---|
| **Who** | The creating user |
| **Action** | Toggles "Response Required" and optionally sets a deadline |
| **Validation** | If `response_required=true` and `response_deadline` is null → 422 error |
| **Backend** | Stored on the correspondence record |
| **Status** | N/A |

### Step 5: Create (Save Draft)

| Aspect | Detail |
|---|---|
| **Who** | The creating user |
| **Action** | Submits the create form |
| **What happens** | Reference number generated, correspondence record created |
| **Backend** | `_next_reference_number()` generates `COR-{SHORT_NAME}-{YEAR}-{SEQ:06d}` using row-level locking on `correspondence_sequences` |
| **Status** | **`RECEIVED`** (inbound) |
| **Document** | Uses the uploaded document (existing `document_id`) |
| **User levels** | `DocumentUserLevelLink` records created for specified levels |
| **Audit** | `CREATE_CORRESPONDENCE` — entity: correspondence, new_value: `{"reference_number": ...}` |
| **Notification** | None (templates exist but are not wired) |
| **Access** | Creator and company members with appropriate user levels can view |

### Step 6: Assign Responsible User

| Aspect | Detail |
|---|---|
| **Who** | Admin only (ADMIN or SUPERADMIN) |
| **Action** | Selects a user from the same company to handle this correspondence |
| **Validation** | Target user must exist and belong to the same company (422 if not) |
| **Backend** | `CorrespondenceMovement` created with `action="assign"` |
| **Status** | **`ASSIGNED`** |
| **Audit** | `ASSIGN_CORRESPONDENCE` — description: "Assigned correspondence to user {id}" |
| **Notification** | Template exists (`build_correspondence_assigned_email`) but **not invoked** |
| **Access** | Assigned user can now see the correspondence in their view |

**Note:** Assignment has no status guard — it can be performed from any status including terminal ones. This is a gap (see Section 23).

### Step 7: Processing / Review

| Aspect | Detail |
|---|---|
| **Who** | The assigned user |
| **Action** | Reviews the correspondence, reads the document, decides next action |
| **Status** | Remains `ASSIGNED` (the `PROCESSING` status exists in the enum but is never assigned by any service method) |
| **Possible actions** | Forward to another user, Submit for workflow approval, Mark as complete (if no response needed) |

### Step 8: Forward (Optional)

| Aspect | Detail |
|---|---|
| **Who** | Any user with view access (not admin-only) |
| **Action** | Forwards to another user in the same company |
| **Validation** | Target user must exist and belong to the same company |
| **Backend** | `CorrespondenceMovement` created with `action="forward"` |
| **Status** | **Does NOT change** — remains at current status |
| **Audit** | `FORWARD_CORRESPONDENCE` |
| **Notification** | Template exists (`build_correspondence_forwarded_email`) but **not invoked** |

### Step 9: Submit for Workflow Approval

| Aspect | Detail |
|---|---|
| **Who** | Author or Admin |
| **Action** | Selects a workflow definition, optionally attaches signature |
| **Validation** | Status must be `DRAFT` or `RECEIVED` (409 otherwise); signature ownership validated if provided |
| **Backend** | Delegates to `WorkflowInstanceService.submit_instance()` — creates workflow instance linked to the backing document |
| **Status** | **`SUBMITTED`** |
| **Audit** | `SUBMIT_CORRESPONDENCE` |
| **Workflow** | Instance enters the configured approval chain |

### Step 10: Approval (External — Workflow Module)

The correspondence service does not handle approval. The existing generic workflow engine manages this:

| Action | Who | Effect on Correspondence |
|---|---|---|
| Approve | Workflow step approver | Workflow status → `approved` |
| Return | Workflow step approver | Workflow status → `returned`; author can edit and resubmit |
| Reject | Workflow step approver | Workflow status → `rejected`; terminal for this submission |
| Clarify | Workflow step approver | Workflow status → `returned` with clarification request |
| Forward | Workflow step approver | Workflow status unchanged; approver delegates to another |

The correspondence service queries `WorkflowInstance` for the document to derive `workflow_status` in the detail response. The correspondence's own `status` field remains `SUBMITTED` throughout the workflow process — it does not track pending_approval/approved/rejected. This is the **dual status model**: workflow status and correspondence business status are separate.

### Step 11: Response Required?

| Condition | Path |
|---|---|
| `response_required = false` | Skip to Step 17 (Complete) |
| `response_required = true` | Continue to Step 12 (Create OUT Response) |

### Step 12: Create OUT Response

| Aspect | Detail |
|---|---|
| **Who** | Any user with CREATE permission |
| **Action** | Creates a new OUT correspondence with `parent_correspondence_id` pointing to this IN record |
| **Prepopulation** | Subject, sender/recipient info can be prepopulated from parent |
| **Validation** | Parent must exist and belong to the same company |
| **Backend** | New reference number generated for OUT; `parent_correspondence_id` stored |
| **Status (OUT)** | `DRAFT` |

### Step 13–16: Full OUT Lifecycle

See Section 4 (Complete OUT Workflow) for Steps 13–16.

### Step 17: Complete

| Aspect | Detail |
|---|---|
| **Who** | System or authorized user |
| **Status** | **`COMPLETED`** |
| **Note** | No `complete_correspondence()` method exists in the service — this transition is **not implemented** |

---

## 4. Complete OUT Workflow — Step by Step

### Step 1: Create Draft

| Aspect | Detail |
|---|---|
| **Who** | Any user with CREATE permission |
| **Action** | Clicks "New Correspondence" → selects "Outgoing" |
| **Required fields** | Subject, Body (mandatory for outbound), Priority |
| **What happens** | Backing HTML document is created from body content |
| **Backend** | `_save_correspondence_html()` builds a full HTML page and saves to `{storage_root}/{company}/correspondence/{user_id}/{uuid}.html`. Creates `Document` record with `FileType.HTML`. |
| **Status** | **`DRAFT`** |
| **Audit** | `CREATE_CORRESPONDENCE` |

### Step 2: Select Author Signature (Optional)

| Aspect | Detail |
|---|---|
| **Who** | The author |
| **Action** | Selects an existing signature from their signature library |
| **Validation** | Signature must exist, must belong to the author (403 if not) |
| **Backend** | Stored as `author_signature_id` on the correspondence |
| **When validated** | At submit time, not at creation time |

### Step 3: Submit for Approval

| Aspect | Detail |
|---|---|
| **Who** | Author or admin |
| **Action** | Selects a workflow definition and submits |
| **Validation** | Status must be `DRAFT`; signature ownership checked if provided |
| **Backend** | Creates `WorkflowInstance` linked to the backing document |
| **Status** | **`SUBMITTED`** |
| **Audit** | `SUBMIT_CORRESPONDENCE` |
| **Notification** | Existing workflow templates handle approval request emails (reused from memo system) |

### Step 4: Workflow Approval

The generic workflow engine handles this. For each step:

| Action | Who | Effect |
|---|---|---|
| **Approve** | Step approver | Moves to next step or completes workflow |
| **Return** | Step approver | Returns to author with remarks; status becomes `returned` |
| **Reject** | Step approver | Terminal rejection; status becomes `rejected` |
| **Clarify** | Step approver | Returns with clarification request |
| **Forward** | Step approver | Delegates approval to another eligible user |

**After all steps approved:** Workflow status becomes `approved`. The correspondence `status` remains `SUBMITTED` (dual status model).

### Step 5: Signature

| Aspect | Detail |
|---|---|
| **When** | After approval, before dispatch |
| **Who** | The author |
| **What** | Author signature (already selected at Step 2) and approver signatures from the workflow |
| **Storage** | Signatures stored under `{storage_root}/signatures/{user_id}/` as image files |
| **PDF embedding** | Signatures are embedded into the final PDF as images |

### Step 6: Final PDF Generation

| Aspect | Detail |
|---|---|
| **When** | On demand (download-final endpoint) |
| **Endpoint** | `GET /api/v1/correspondences/{id}/download-final` |
| **Contents** | Company header, reference number, date, direction, priority, status, sender/recipient block, subject, body (converted to ReportLab XML), approval history, signature images, dispatch information |
| **Storage** | Generated on-the-fly; not persisted as a separate file |
| **Note** | The draft HTML file and the final PDF are distinct artifacts |

### Step 7: Dispatch

| Aspect | Detail |
|---|---|
| **Who** | Admin only |
| **Pre-conditions** | Status must be `APPROVED` or `READY_FOR_DISPATCH`; must not already be dispatched |
| **Action** | Selects dispatch method, enters dispatch reference/tracking number |
| **Methods** | email, courier, post, hand_delivery, portal, other |
| **Backend** | Sets `dispatch_method`, `dispatch_reference`, `dispatched_at`, `date_sent`; creates movement record |
| **Status** | **`DISPATCHED`** |
| **Audit** | `DISPATCH_CORRESPONDENCE` |
| **Post-dispatch** | Document becomes immutable — edits blocked by `_check_edit_access()` |

### Step 8: Delivery

| Aspect | Detail |
|---|---|
| **Who** | Admin only |
| **Pre-condition** | Status must be `DISPATCHED` |
| **Action** | Clicks "Mark as Delivered" |
| **Backend** | Sets `delivered_at` to now; creates movement record |
| **Status** | **`DELIVERED`** |
| **Audit** | **None** — `mark_delivered()` does not call `_log_audit()` (gap) |
| **Notification** | None wired |

### Step 9: Acknowledgement

| Aspect | Detail |
|---|---|
| **Who** | Admin only |
| **Pre-condition** | Status must be `DELIVERED` |
| **Action** | Clicks "Mark as Acknowledged" |
| **Backend** | Sets `acknowledged_at` to now; creates movement record |
| **Status** | **`ACKNOWLEDGED`** |
| **Audit** | **None** — `mark_acknowledged()` does not call `_log_audit()` (gap) |

### Step 10: Complete

| Aspect | Detail |
|---|---|
| **Status** | `COMPLETED` |
| **Note** | **Not implemented** — no service method transitions to `COMPLETED` |

---

## 5. Internal Correspondence Workflow

### Flow

```
Create Draft (body mandatory)
     ↓
Status: DRAFT
     ↓
Submit for Approval (optional workflow)
     ↓
Status: SUBMITTED
     ↓
Approval (if workflow configured)
     ↓
Distribute / Forward to internal recipient
     ↓
Recipient Reviews
     ↓
Complete
```

### Company Restriction

Internal correspondence must remain within the same company. This is enforced at multiple levels:

| Level | Enforcement |
|---|---|
| **Assign** | `assign_correspondence()` validates `to_user.company_id == corr.company_id` (422 if mismatch) |
| **Forward** | `forward_correspondence()` validates `to_user.company_id == corr.company_id` (422 if mismatch) |
| **Create** | `create_draft()` resolves company from the authenticated user; client cannot set `company_id` |
| **List** | SQL filter `correspondences.company_id == current_user.company_id` applied before any results returned |

**What happens if someone attempts cross-company routing:**
The API returns HTTP 422: "Invalid assignee for this company" or "Invalid target user for this company". No movement record is created. No status changes. No audit event.

---

## 6. IN → OUT Response Workflow

This is the central business flow of the entire feature.

### Scenario

```
IN-ABC-2026-000042  (Government regulatory inquiry)
        │
        │  Response Required: YES
        │  Response Deadline: 30 September 2026
        │
        ▼
   Assigned to Compliance Officer
        │
        ▼
   Compliance Reviews Document
        │
        ▼
   Determines Response Needed
        │
        ▼
   Clicks "Create Response"
        │
        ▼
OUT-ABC-2026-000018  (Response letter)
   parent_correspondence_id → IN-ABC-2026-000042
        │
        ▼
   Full OUT Lifecycle:
   Draft → Submit → Approve → Sign → Dispatch
        │
        ▼
   IN Status → COMPLETED (after OUT dispatched)
```

### How the Relationship Is Stored

| Field | Value |
|---|---|
| `OUT.parent_correspondence_id` | FK pointing to `IN.id` |
| `IN.parent_correspondence_id` | `NULL` (the IN is the parent, not the child) |
| `IN.response_received` | `false` until marked responded |
| `IN.responded_at` | `null` until responded |

### What Gets Prepopulated

When the user clicks "Create Response" from an IN record:

| Field | Prepopulated? | Source |
|---|---|---|
| Subject | Partially — prefix "RE: " suggested | Parent subject |
| Sender name | Swapped — IN's recipient becomes OUT's sender | Parent recipient fields |
| Recipient name | Swapped — IN's sender becomes OUT's recipient | Parent sender fields |
| Category | Yes | Parent category |
| Priority | Yes | Parent priority |
| Body | No — must be written fresh | User input |
| Direction | Forced to `outbound` | System |
| User levels | Inherited from parent | Parent user_level_ids |

### Company Validation

The OUT response must belong to the same company as the IN parent. Enforced by:

1. `create_draft()` validates `parent_correspondence_id` exists and `parent.company_id == current_user.company_id`
2. The OUT's `company_id` is resolved from the authenticated user (who must be in the same company)

### How the System Knows the IN Has Been Answered

**Currently:** The system does **not** automatically update the IN's `response_received` flag when the OUT is dispatched. This is a gap. The `response_received` and `responded_at` fields exist on the model but no service method sets them. The frontend would need to manually mark the IN as responded.

---

## 7. Document Movement / Routing

### Core Principle

Logical responsibility changes do **not** physically move the document file. The file remains in its original storage location. Only the metadata changes.

```
Before:
  Document at: storage/ABC/correspondence/15/abc123.html
  Responsible: User A
  Status: ASSIGNED

After Forward to User B:
  Document at: storage/ABC/correspondence/15/abc123.html  (UNCHANGED)
  Responsible: User B (tracked via movement record)
  Status: ASSIGNED (unchanged by forward)
```

### Movement Record Structure

Each movement creates a `CorrespondenceMovement` record:

| Field | Description |
|---|---|
| `correspondence_id` | Which correspondence moved |
| `from_user_id` | Previous responsible user (null for first assignment) |
| `to_user_id` | New responsible user |
| `from_department` | Previous department (optional) |
| `to_department` | New department (optional) |
| `action` | "assign", "forward", "dispatch", "delivered", "acknowledged" |
| `remarks` | Free text notes |
| `created_by` | Who performed the action |
| `created_at` | Timestamp |

### Assignment vs Forwarding vs Workflow Approval

| Aspect | Assignment | Forwarding | Workflow Approval |
|---|---|---|---|
| **Who can do it** | Admin only | Any user with view access | Workflow step approver |
| **Changes status?** | Yes → `ASSIGNED` | No | Yes (workflow status) |
| **Requires admin?** | Yes | No | No (role-based) |
| **Creates movement?** | Yes | Yes | No (workflow has its own history) |
| **Company restriction** | Same company | Same company | Same company (via document access) |
| **Use case** | Admin designates responsible person | User routes to colleague for action | Formal multi-step approval chain |

---

## 8. Approval Workflow Integration

### How It Works

Correspondence **reuses** the existing generic Workflow module. It does not have its own approval engine.

```
Correspondence Submit
        ↓
WorkflowInstanceService.submit_instance()
        ↓
WorkflowInstance created (linked to backing document)
        ↓
Active step determined by workflow definition
        ↓
Step approvers see the pending approval
        ↓
Approver takes action:
   ├── Approve → next step or complete
   ├── Return → author can edit
   ├── Reject → terminal
   ├── Clarify → returns with questions
   └── Forward → delegates to another approver
```

### Status Duality

The correspondence has two independent status tracks:

| Track | Controlled By | Values |
|---|---|---|
| **Correspondence status** | Correspondence service | `draft`, `received`, `assigned`, `submitted`, `dispatched`, `delivered`, `acknowledged`, `completed` |
| **Workflow status** | Workflow engine | `pending_approval`, `returned`, `rejected`, `approved` |

The correspondence `status` field does **not** change during workflow approval. It stays at `SUBMITTED` while the workflow status progresses through `pending_approval` → `approved`. The frontend must query both to show the full picture.

### Approval Actions — Detailed

| Action | Who | Correspondence Effect | Workflow Effect | Author Can Edit? | Resubmission? |
|---|---|---|---|---|---|
| **Approve** | Step approver | None directly | Advances to next step or completes | Yes (if returned first) | N/A |
| **Return** | Step approver | None directly | Status → `returned` | Yes | Yes, after edits |
| **Reject** | Step approver | None directly | Status → `rejected` | No (terminal) | No |
| **Clarify** | Step approver | None directly | Status → `returned` with remarks | Yes | Yes, after answering |
| **Forward** | Step approver | None directly | Delegates to another approver | N/A | N/A |

### Notifications for Approval Events

The existing workflow notification templates (from the memo system) are reused:
- `build_submit_email` — sent to active-step approvers when submitted
- `build_advance_email` — sent to next-step approvers when workflow advances
- `build_action_email` — sent to author when approved/returned/rejected

These are invoked by the workflow service, not the correspondence service.

---

## 9. Signature Processing

### When Signatures Are Selected

| Signature | When Selected | By Whom |
|---|---|---|
| **Author signature** | At draft time or submit time | The author |
| **Approver signatures** | During workflow approval | Each approver at their step |

### Signature Ownership Validation

```python
# In submit_correspondence():
sig = SignatureService(session).validate_signature_exists(data.signature_id)
if sig.user_id != current_user.id:
    raise HTTPException(403, "You can only attach your own signatures")

# In update_correspondence() for author_signature_id:
sig = SignatureService(session).validate_signature_exists(data.author_signature_id)
if sig.user_id != current_user.id:
    raise HTTPException(403, "You can only attach your own signatures")
```

### When Signatures Become Immutable

After dispatch. The `_check_edit_access()` method blocks edits when `dispatch_method is not None`.

### How Signatures Appear in the Final PDF

The `correspondence/pdf_generator.py` collects:
1. Author signature image (from `correspondence.author_signature.signature_file`)
2. Workflow approval history with approver signature images

These are embedded as images in the generated PDF.

### Original Document Modification

The original HTML backing document is **not modified** by signature attachment. Signatures are only embedded in the on-the-fly generated final PDF.

---

## 10. Final PDF Generation

### When Generated

On demand via `GET /api/v1/correspondences/{id}/download-final`. Not generated automatically at any lifecycle stage.

### What It Contains

```
┌─────────────────────────────────────┐
│         COMPANY HEADER              │
│     Company Name / Logo             │
├─────────────────────────────────────┤
│  Reference: COR-ABC-2026-000018     │
│  Date: 16 September 2026            │
│  Direction: Outbound                │
│  Priority: High                     │
│  Status: Dispatched                 │
├─────────────────────────────────────┤
│  From: John Smith                   │
│        ABC Corporation              │
│  To:   Regulatory Authority         │
│        Government Building          │
├─────────────────────────────────────┤
│  Subject: Response to Inquiry       │
│           Ref: GOV-2026-0892        │
├─────────────────────────────────────┤
│                                     │
│  [Body Content - converted from     │
│   HTML to ReportLab XML]            │
│                                     │
├─────────────────────────────────────┤
│  Approvals:                         │
│  - Step 1: Jane Doe (Approved)      │
│    [Signature Image]                │
│  - Step 2: Bob Lee (Approved)       │
│    [Signature Image]                │
├─────────────────────────────────────┤
│  Dispatch Information:              │
│  Method: Courier                    │
│  Reference: TRK-123456789           │
│  Date: 16 September 2026            │
├─────────────────────────────────────┤
│  Page X of Y                        │
└─────────────────────────────────────┘
```

### Draft HTML vs Final PDF vs Dispatched Document

| Artifact | Format | When Created | Content |
|---|---|---|---|
| **Draft HTML** | HTML file | At creation (OUT/INTERNAL) | Sanitized body with basic page structure |
| **Final PDF** | PDF (generated on demand) | When download-final is requested | Complete document with metadata, signatures, approvals, dispatch info |
| **Dispatched Document** | Whatever was dispatched | At dispatch time | The admin decides what to send; the system records the method and reference |

The "dispatched document" is whatever the admin sends via the chosen method. The system does not auto-attach the final PDF to the dispatch — the admin may print it, email it, or upload it to a portal manually.

---

## 11. Dispatch

### Dispatch Is a Separate Business Event

This is a critical design point. The following are **not** equivalent:

| Event | Does It Mean Dispatched? |
|---|---|
| Correspondence approved | No |
| Final PDF generated | No |
| PDF downloaded by user | No |
| Admin clicks "Dispatch" | **Yes** |

### Pre-Conditions

| Condition | Enforcement |
|---|---|
| Status must be `APPROVED` or `READY_FOR_DISPATCH` | `dispatch_correspondence()` checks status (409 if not) |
| Must not already be dispatched | Checks `dispatch_method is not None` (409 if already dispatched) |
| Must be admin | `_check_admin()` (403 if not) |

### Dispatch Data

| Field | Required | Description |
|---|---|---|
| `dispatch_method` | Yes | email, courier, post, hand_delivery, portal, other |
| `dispatch_reference` | No | Tracking number, email ID, courier receipt number |
| `remarks` | No | Default: "Dispatched via {method}" |

### Post-Dispatch

- `dispatched_at` is set to current time
- `date_sent` is set to current time
- Status becomes `DISPATCHED`
- Movement record created with `action="dispatch"`
- Document becomes **immutable** — `_check_edit_access()` blocks edits when `dispatch_method is not None`

### If Dispatch Fails

The system does not model dispatch failure. If the courier loses the letter, the admin would need to:
1. This is a gap — there is no "dispatch failed" status or retry mechanism
2. The admin could theoretically create a new correspondence

### Can Dispatch Be Repeated?

No. The idempotency check `if corr.dispatch_method is not None` prevents re-dispatch with HTTP 409: "Correspondence has already been dispatched".

---

## 12. Delivery and Acknowledgement

### Status Progression

```
APPROVED → DISPATCHED → DELIVERED → ACKNOWLEDGED → (COMPLETED)
```

### The Difference Between Each Stage

| Stage | Meaning | Example (Courier) | Example (Email) | Example (Government Portal) |
|---|---|---|---|---|
| **Dispatched** | Sent via chosen method | Handed to courier | Email sent | Uploaded to portal |
| **Delivered** | Confirm receipt | Courier delivery confirmation | Delivery receipt / read receipt | Portal confirmation |
| **Acknowledged** | Recipient confirms action | Signed receipt returned | Reply email received | Portal acknowledgement |

### What the System Tracks Automatically vs Manually

| Event | Automatic? | How Recorded |
|---|---|---|
| Dispatched | Semi — admin clicks button | `dispatched_at` timestamp |
| Delivered | **Manual** — admin clicks "Mark as Delivered" | `delivered_at` timestamp |
| Acknowledged | **Manual** — admin clicks "Mark as Acknowledged" | `acknowledged_at` timestamp |

The system does not receive delivery confirmations from couriers, email servers, or government portals. All post-dispatch tracking is manual.

---

## 13. Response Deadline / SLA

### How the Three Fields Work Together

| Field | Type | Purpose |
|---|---|---|
| `response_required` | boolean | Whether a response is expected |
| `response_deadline` | datetime | When the response is due |
| `response_received` | boolean | Whether the response has been provided |

### Validation Rules

| Rule | Enforcement |
|---|---|
| `response_required=true` AND `response_deadline=null` → **Rejected** | HTTP 422 at creation time |
| `response_required=false` AND `response_deadline=any` → **Allowed** | Deadline is simply ignored |
| `response_required=true` AND `response_deadline=past` → **Allowed** | For historical record entry |

### Overdue Calculation

A correspondence is overdue when **ALL** of these are true:

1. `response_required = true`
2. `response_received = false`
3. `response_deadline < current UTC time`
4. `status NOT IN [COMPLETED, CANCELLED, ARCHIVED, REJECTED]`

The system does **not** persist a redundant `is_overdue` field. It is calculated dynamically in the list query when `overdue=true` filter is used.

### Frontend Display States

| State | Condition | Visual |
|---|---|---|
| **On Track** | Deadline in the future, not responded | Normal indicator |
| **Due Soon** | Approaching deadline (threshold not defined in spec) | Warning indicator |
| **Overdue** | Past deadline, not completed | Red indicator |
| **Completed** | `response_received = true` | Green checkmark |

### What Happens When Deadline Expires

**Nothing automatic.** The system does not send reminder emails, does not escalate, does not change status. The `overdue` filter in the list query allows admins to manually identify overdue items. Automated SLA reminders are listed as a future enhancement.

---

## 14. Company Isolation

### How `company_id` Is Determined

The client **never** sets `company_id`. The server resolves it from the authenticated user:

```python
def _resolve_company(self, user: User) -> Company:
    if not user.company_id:
        raise HTTPException(400, "User must belong to a company")
    company = self.session.get(Company, user.company_id)
    if not company:
        raise HTTPException(400, "Company not found")
    return company
```

### Enforcement Points

| Check | Where | Effect |
|---|---|---|
| **Create** | `create_draft()` | Company resolved from user; `company_id` stored on correspondence |
| **View** | `_check_company_access()` | `correspondence.company_id == user.company_id` (SUPERADMIN bypasses) |
| **List** | `list_correspondences()` | SQL WHERE clause filters by company before any results returned |
| **Assign** | `assign_correspondence()` | Target user must belong to same company |
| **Forward** | `forward_correspondence()` | Target user must belong to same company |
| **Category** | `_validate_category()` | Category must belong to the same company |
| **Parent** | `create_draft()` | Parent correspondence must belong to the same company |
| **Reference** | `_next_reference_number()` | Uses company short name in reference: `COR-{SHORT_NAME}-{YEAR}-{SEQ}` |

### Concrete Example

```
Company ABC (short_name: "ABC")
├── Admin: Alice (company_id = ABC)
├── User: Bob (company_id = ABC)
├── Category: "Regulatory" (company_id = ABC)
└── Correspondence: COR-ABC-2026-000042

Company XYZ (short_name: "XYZ")
├── Admin: Carol (company_id = XYZ)
├── User: Dave (company_id = XYZ)
├── Category: "HR" (company_id = XYZ)
└── Correspondence: COR-XYZ-2026-000007
```

| Scenario | Result |
|---|---|
| Alice lists correspondence | Sees only ABC items |
| Carol lists correspondence | Sees only XYZ items |
| Alice tries to assign to Dave | HTTP 422: "Invalid assignee for this company" |
| Alice tries to set parent to COR-XYZ-... | HTTP 422: "Invalid parent correspondence" |
| Alice tries to use "HR" category | HTTP 422: "Invalid category for this company" |
| Bob searches for "regulatory" | Only sees ABC results |
| SUPERADMIN with no company selected | Sees empty list or "select a company" prompt |
| SUPERADMIN with ABC selected | Sees ABC correspondence |
| SUPERADMIN with XYZ selected | Sees XYZ correspondence |

---

## 15. User Level Visibility

### The Access Layer Stack

```
Company Access (is the user in the same company?)
        +
RBAC Permission (does the user have VIEW/CREATE/UPDATE?)
        +
Document Access (can the user see the backing document?)
        +
User Level Visibility (is the user's level linked to this document?)
        +
Workflow Eligibility (is the user an approver for this step?)
```

### How It Works for Correspondence

The correspondence service delegates document-level access to the existing helpers:

```python
def _check_view_access(self, correspondence, user):
    self._check_company_access(correspondence, user)  # Company check
    if not user.is_admin():
        ensure_document_access(self.session, user, correspondence.document_id)  # Document access
        ensure_document_user_level_access(self.session, user, correspondence.document)  # User level
```

### Why Being an Approver Does Not Bypass User Levels

The workflow module determines approver eligibility via `workflow_step_approvers`. If an approver cannot view the underlying document per their user level, they should not appear as a valid approver. The spec mandates this but the enforcement happens at the workflow eligibility layer, not the correspondence layer.

### Authorization Order

The spec requires this order (Section 34):

```
1. Authentication (is the user logged in?)
2. RBAC Permission (does the endpoint require CREATE/VIEW/UPDATE?)
3. Company Filter (is the correspondence in the user's company?)
4. User Level / Document Access (can the user see this document?)
5. Search (text matching)
6. Filters (direction, priority, status, etc.)
7. Sort (by date, etc.)
8. Pagination (skip/limit)
9. Count (total matching)
```

---

## 16. Categories

### How Correspondence Uses Categories

Categories are company-specific classification labels. Each company defines its own set.

```
Company ABC
├── Regulatory
├── Client
├── Legal
└── Finance

Company XYZ
├── HR
├── Procurement
└── Operations
```

### Category Selection

| Aspect | Detail |
|---|---|
| **When** | At creation time (optional field) |
| **Validation** | `_validate_category()` checks category exists AND `category.company_id == company.id` |
| **Error** | HTTP 422: "Invalid category for this company" |
| **Update** | Category can be changed via PATCH; re-validated on update |
| **Deactivated category** | The spec does not address this; the current implementation does not filter out inactive categories |

### Category Filtering in List

The `category_id` query parameter filters correspondences by category. Only categories belonging to the user's company are valid filter values.

---

## 17. Notifications

### Notification Matrix

| Event | Recipient | Template Exists? | Wired Up? |
|---|---|---|---|
| Assigned | Assignee | Yes (`build_correspondence_assigned_email`) | **No** — template defined but not invoked by service |
| Forwarded | Forward target | Yes (`build_correspondence_forwarded_email`) | **No** — same |
| Dispatched | Relevant users | Yes (`build_correspondence_dispatched_email`) | **No** — same |
| Submitted for approval | Active-step approvers | Reused from memo system (`build_submit_email`) | **Yes** — via workflow service |
| Advanced to next step | Next-step approvers | Reused from memo system (`build_advance_email`) | **Yes** — via workflow service |
| Approved/Returned/Rejected | Author | Reused from memo system (`build_action_email`) | **Yes** — via workflow service |
| Deadline approaching | Responsible user | Not implemented | **No** — listed as future enhancement |
| Overdue | Responsible user/manager | Not implemented | **No** — listed as future enhancement |
| Delivered | Relevant users | Not implemented | **No** |

### Notification Architecture

- Emails are fire-and-forget; failures are logged but do not block transactions
- SMTP configuration via `core/config.py` (`SMTP_*` settings)
- Background task delivery via `notifications/tasks.py`

---

## 18. Audit Trail

### Complete Audit Timeline (Example)

```
09:15  CREATE_CORRESPONDENCE    — Alice creates IN correspondence
09:15  (workflow submit)        — Alice submits for approval
09:30  ASSIGN_CORRESPONDENCE    — Alice assigns to Bob
10:15  (view)                   — Bob views the correspondence
14:00  FORWARD_CORRESPONDENCE   — Bob forwards to Carol
16:30  (workflow approve)       — Carol approves
Next Day 09:00  DISPATCH_CORRESPONDENCE — Alice dispatches via courier
       (manual)                 — Alice marks as delivered
       (manual)                 — Alice marks as acknowledged
```

### What Is Logged Per Event

| Field | Value |
|---|---|
| `company_id` | The company owning the correspondence |
| `user_id` | The acting user |
| `username` | The acting user's email |
| `full_name` | The acting user's full name |
| `action` | The AuditAction enum value |
| `module` | `AuditModule.DOCUMENTS` (note: `CORRESPONDENCE` exists but is unused) |
| `entity_name` | `"correspondence"` |
| `entity_id` | String of the correspondence ID |
| `timestamp` | UTC timestamp |
| `old_value` | Previous state (only for UPDATE) |
| `new_value` | New state (varies by action) |
| `description` | Human-readable description |

### Immutability

No PUT/PATCH/DELETE endpoints exist for audit records. Users cannot modify audit history. The `AuditService` uses its own独立 session to write audit logs, ensuring logs are committed even if the outer transaction rolls back.

---

## 19. Physical Storage

### Directory Structure

```
{STORAGE_ROOT}/
└── {company.short_name}/
    ├── uploads/              (general document uploads)
    ├── correspondence/
    │   └── {user_id}/
    │       └── {uuid}.html   (backing HTML for OUT/INTERNAL)
    ├── memos/
    └── signatures/
        └── {user_id}/
            └── {uuid}.png    (signature images)
```

### Key Points

| Aspect | Detail |
|---|---|
| **Company isolation** | Each company has its own subdirectory named by `short_name` |
| **User isolation** | Correspondence HTML files are under `{user_id}/` |
| **File naming** | UUID-based (`{uuid}.html`) — no name collisions |
| **No physical movement** | When correspondence is forwarded/assigned, the file stays in place |
| **Cross-company prevention** | `_check_company_access()` prevents accessing another company's files |
| **IN correspondence** | Uses the uploaded document's existing storage path (no new file created) |
| **OUT/INTERNAL** | HTML file created by `_save_correspondence_html()` |

---

## 20. Complete End-to-End Scenario

### Scenario: Government Regulatory Inquiry

> The Environmental Protection Agency sends Company ABC an official letter requesting a compliance report within 15 days.

### Step-by-Step Walkthrough

**Step 1: Letter Received**
- Front desk receives the physical letter
- Admin Alice scans the letter and uploads the PDF to the DMS
- User sees: Upload dialog, file is stored

**Step 2: Register IN Correspondence**
- Alice clicks "New Correspondence" → "Incoming"
- User sees: Create form with direction=INBOUND
- Alice enters:
  - Subject: "EPA Compliance Report Request - Ref: EPA-2026-4821"
  - Sender name: "John Williams"
  - Sender organization: "Environmental Protection Agency"
  - Date received: auto-set to today
  - Priority: High
  - Category: Regulatory
  - Response Required: Yes
  - Response Deadline: 30 September 2026 (15 days)
- Alice links the uploaded PDF as the backing document
- User clicks "Save"
- System generates: `COR-ABC-2026-000042`
- Status: `RECEIVED`
- Audit: `CREATE_CORRESPONDENCE`

**Step 3: Assign to Compliance Officer**
- Alice opens COR-ABC-2026-000042
- Alice clicks "Assign" → selects Bob (Compliance Officer)
- User sees: Assign dialog with user dropdown
- Alice adds remarks: "Please review and prepare response by deadline"
- System creates: Movement record (action=assign, from=Alice, to=Bob)
- Status: `ASSIGNED`
- Audit: `ASSIGN_CORRESPONDENCE`
- Notification: Would be sent (template exists, not wired)

**Step 4: Bob Reviews**
- Bob sees the correspondence in his "Assigned to Me" list
- Bob opens it, reads the attached PDF
- Bob determines a response letter is needed
- Status remains: `ASSIGNED`

**Step 5: Create OUT Response**
- Bob clicks "Create Response"
- System presents the OUT create form with prepopulated fields:
  - Subject: "RE: EPA Compliance Report Request - Ref: EPA-2026-4821"
  - Recipient: John Williams, Environmental Protection Agency (from IN sender)
  - Category: Regulatory (inherited)
  - Priority: High (inherited)
- Bob writes the response body in the HTML editor
- Bob selects his author signature
- User clicks "Save"
- System generates: `COR-ABC-2026-000018`
- `parent_correspondence_id` → COR-ABC-2026-000042
- Status (OUT): `DRAFT`
- Audit: `CREATE_CORRESPONDENCE` (for the OUT)

**Step 6: Submit for Approval**
- Bob clicks "Submit" on the OUT correspondence
- Bob selects workflow: "Two-Step Management Approval"
- System creates workflow instance linked to the backing document
- Status (OUT): `SUBMITTED`
- Audit: `SUBMIT_CORRESPONDENCE`
- Notification: Approval request email sent to Step 1 approver (via workflow system)

**Step 7: Step 1 Approval**
- Manager Carol receives approval request email
- Carol opens the correspondence, reviews the body
- Carol clicks "Approve"
- Workflow advances to Step 2
- Notification: Approval request email sent to Step 2 approver

**Step 8: Step 2 Approval**
- Director Dave receives approval request email
- Dave reviews and approves
- Workflow status: `approved`
- Notification: Approval confirmation email sent to Bob

**Step 9: Final PDF Generation**
- Bob opens the approved OUT correspondence
- Bob clicks "Download Final PDF"
- System generates PDF with:
  - Company ABC header
  - Reference: COR-ABC-2026-000018
  - Sender/Recipient details
  - Response body
  - Carol's approval + signature image
  - Dave's approval + signature image
- Bob saves the PDF to send via courier

**Step 10: Dispatch**
- Admin Alice opens the OUT correspondence
- Alice clicks "Dispatch"
- Alice enters:
  - Method: Courier
  - Reference: DHL-TRK-987654321
- Status (OUT): `DISPATCHED`
- `dispatched_at`: now
- `date_sent`: now
- Audit: `DISPATCH_CORRESPONDENCE`
- Movement record created

**Step 11: Mark Delivered**
- Three days later, courier confirms delivery
- Alice clicks "Mark as Delivered"
- Status (OUT): `DELIVERED`
- `delivered_at`: now
- Movement record created

**Step 12: Mark Acknowledged**
- One week later, EPA sends acknowledgement letter
- Alice clicks "Mark as Acknowledged"
- Status (OUT): `ACKNOWLEDGED`
- `acknowledged_at`: now
- Movement record created

**Step 13: Complete IN Correspondence**
- **Note:** This step has no automated mechanism — Alice would manually note completion
- Status (IN): Should become `COMPLETED` (not implemented)

---

## 21. Exception and Failure Scenarios

### 1. User Submits Incomplete Correspondence

| Aspect | Detail |
|---|---|
| **Trigger** | Missing required fields (subject, direction, body for OUT/INTERNAL, document_id for IN) |
| **Validation** | Pydantic schema validation rejects at API level |
| **System response** | HTTP 422 with field-specific error messages |
| **Status** | Unchanged (record not created) |
| **Audit** | None (record not created) |

### 2. No Workflow Is Configured

| Aspect | Detail |
|---|---|
| **Trigger** | User submits with invalid `workflow_definition_id` |
| **Validation** | `WorkflowInstanceService.submit_instance()` rejects |
| **System response** | HTTP error from workflow service |
| **Status** | Remains `DRAFT` or `RECEIVED` |
| **Audit** | None |

### 3. Approver Rejects

| Aspect | Detail |
|---|---|
| **Trigger** | Approver clicks "Reject" in workflow |
| **Workflow effect** | Status → `rejected` |
| **Correspondence effect** | None directly (status remains `SUBMITTED`) |
| **Can author edit?** | No — `rejected` is in `TERMINAL_STATUSES` |
| **Resubmission?** | No — terminal state |
| **Notification** | Rejection email sent to author (via workflow system) |

### 4. Approver Returns

| Aspect | Detail |
|---|---|
| **Trigger** | Approver clicks "Return" with remarks |
| **Workflow effect** | Status → `returned` |
| **Correspondence effect** | None directly |
| **Can author edit?** | Yes — `returned` is NOT in `TERMINAL_STATUSES` |
| **Resubmission?** | Yes — author edits and resubmits |
| **Notification** | Return email sent to author (via workflow system) |

### 5. Cross-Company Access Attempt

| Aspect | Detail |
|---|---|
| **Trigger** | User from Company A tries to view/assign/use correspondence from Company B |
| **Validation** | `_check_company_access()` compares `correspondence.company_id == user.company_id` |
| **System response** | HTTP 404 (deliberately not 403 to avoid revealing existence) |
| **Status** | Unchanged |
| **Audit** | Security audit event via `middleware/audit.py` (403/401 events) |

### 6. Response Deadline Expires

| Aspect | Detail |
|---|---|
| **Trigger** | Current time passes `response_deadline` |
| **System response** | **Nothing automatic** — no status change, no notification, no escalation |
| **Detection** | Admin can filter by `overdue=true` in the list query |
| **Note** | Automated SLA reminders are a future enhancement |

### 7. PDF Generation Fails

| Aspect | Detail |
|---|---|
| **Trigger** | ReportLab error during PDF generation |
| **System response** | HTTP 500 |
| **Note** | PDF is generated on-the-fly; no cached version to fall back to |

### 8. Dispatch of Unapproved Document

| Aspect | Detail |
|---|---|
| **Trigger** | Admin tries to dispatch a correspondence in `DRAFT`, `SUBMITTED`, or `RECEIVED` status |
| **Validation** | `dispatch_correspondence()` checks status |
| **System response** | HTTP 409: "Cannot dispatch correspondence in '{status}' status" |
| **Status** | Unchanged |

### 9. Duplicate Reference Number / Concurrency

| Aspect | Detail |
|---|---|
| **Mechanism** | `CorrespondenceSequence` table with `company_id + year` unique constraint |
| **Row-level locking** | `with_for_update()` on PostgreSQL (skipped on SQLite) |
| **Race condition** | Two simultaneous creates for the same company/year: one succeeds, the other gets a DB integrity error on the unique constraint. The service does not catch this — it would surface as an HTTP 500. |
| **Note** | The `with_for_update()` mitigates this on PostgreSQL but the SQLite test path has no locking |

### 10. Edit of Terminal Correspondence

| Aspect | Detail |
|---|---|
| **Trigger** | User tries to update a correspondence in APPROVED, DISPATCHED, DELIVERED, ACKNOWLEDGED, COMPLETED, CANCELLED, ARCHIVED, or REJECTED status |
| **Validation** | `_check_edit_access()` checks `TERMINAL_STATUSES` |
| **System response** | HTTP 409: "Cannot edit correspondence in '{status}' status" |
| **Also blocked** | Post-dispatch edits (checks `dispatch_method is not None`) |

---

## 22. QA Validation Checklist

### Functional Testing

- [ ] Create IN correspondence with uploaded document
- [ ] Create OUT correspondence with body content
- [ ] Create INTERNAL correspondence with body content
- [ ] Reference number auto-generation format: `COR-{SHORT}-{YEAR}-{SEQ:06d}`
- [ ] Reference number increments correctly per company per year
- [ ] Subject, priority, category, sender/recipient fields stored correctly
- [ ] Body HTML sanitization (script tags stripped, allowed tags preserved)
- [ ] Update correspondence (subject, body, priority, category)
- [ ] Body update regenerates backing HTML file
- [ ] User level links created on correspondence creation
- [ ] User level links updated on correspondence update

### Workflow Testing

- [ ] Submit OUT correspondence creates workflow instance
- [ ] Submit IN correspondence creates workflow instance
- [ ] Approve advances workflow
- [ ] Return sends back to author with remarks
- [ ] Reject is terminal
- [ ] Clarify returns with questions
- [ ] Forward delegates to another approver
- [ ] Author can edit after return
- [ ] Author cannot edit after reject
- [ ] Multiple workflow steps execute sequentially
- [ ] Parallel workflow step (any approver) completes correctly

### Permission/RBAC Testing

- [ ] CREATE permission required to create correspondence
- [ ] VIEW permission required to list/view correspondence
- [ ] UPDATE permission required to update/submit/assign/forward/dispatch
- [ ] Admin-only enforcement on assign, dispatch, deliver, acknowledge
- [ ] Non-admin can forward
- [ ] Unauthenticated access returns 401/403

### Company Isolation Testing

- [ ] Company A cannot see Company B correspondence in list
- [ ] Company A cannot view Company B correspondence by ID
- [ ] Company A cannot assign to Company B user
- [ ] Company A cannot use Company B category
- [ ] Company A cannot set parent to Company B correspondence
- [ ] SUPERADMIN with no company sees empty list or prompt
- [ ] SUPERADMIN with Company A selected sees only Company A
- [ ] URL parameter manipulation cannot bypass company isolation
- [ ] Search does not return cross-company results

### User Level Testing

- [ ] User with "High" level sees all linked correspondence
- [ ] User with "Medium" level sees only medium-linked correspondence
- [ ] User with "Low" level sees only low-linked correspondence
- [ ] Admin bypasses user level restrictions
- [ ] Approver does NOT automatically gain visibility

### Document/File Testing

- [ ] IN correspondence uses uploaded document
- [ ] OUT correspondence creates HTML backing document
- [ ] INTERNAL correspondence creates HTML backing document
- [ ] HTML file stored under correct company/user path
- [ ] Body update deletes old HTML and creates new one
- [ ] Document title synchronized with correspondence subject

### Signature Testing

- [ ] Author can select own signature
- [ ] Author cannot select another user's signature (403)
- [ ] Signature validated at submit time
- [ ] Signatures embedded in final PDF
- [ ] Original document not modified by signature

### Notification Testing

- [ ] Workflow approval notifications sent (submitted, approved, returned, rejected)
- [ ] Assignment notification template exists
- [ ] Forward notification template exists
- [ ] Dispatch notification template exists
- [ ] Email failures do not block transactions

### Audit Testing

- [ ] CREATE_CORRESPONDENCE logged with reference number
- [ ] UPDATE_CORRESPONDENCE logged with changed fields
- [ ] SUBMIT_CORRESPONDENCE logged with workflow_definition_id
- [ ] ASSIGN_CORRESPONDENCE logged with target user ID
- [ ] FORWARD_CORRESPONDENCE logged with target user ID
- [ ] DISPATCH_CORRESPONDENCE logged with method and reference
- [ ] Audit records include company_id
- [ ] Audit records are immutable (no edit/delete endpoints)

### SLA Testing

- [ ] `response_required=true` without deadline → 422
- [ ] `response_required=true` with deadline → stored
- [ ] Overdue filter returns only overdue items
- [ ] Completed response clears overdue state
- [ ] Cancelled/archived not flagged as overdue

### Concurrency Testing

- [ ] Two simultaneous creates for same company generate different reference numbers
- [ ] Sequence table correctly incremented under load

### Security Testing

- [ ] Script injection in body is sanitized
- [ ] HTML in body is bleach-cleaned
- [ ] Company isolation enforced at SQL level
- [ ] No path traversal in storage
- [ ] Signature ownership validated

### UI Testing

- [ ] List page shows direction badges (IN/OUT/INTERNAL)
- [ ] List page shows priority indicators
- [ ] List page shows overdue indicators
- [ ] Detail page shows full metadata
- [ ] Detail page shows movement timeline
- [ ] Detail page shows workflow status
- [ ] Create form adapts to direction (IN requires upload, OUT/INTERNAL require body)
- [ ] Assign dialog shows company users only
- [ ] Dispatch dialog shows dispatch method options

### Regression Testing

- [ ] Existing memo tests still pass (28/28)
- [ ] Existing audit tests still pass
- [ ] Frontend build succeeds
- [ ] Existing document operations unaffected

---

## 23. Identified Gaps

### Confirmed Behavior (Implemented)

| Feature | Status |
|---|---|
| Create IN/OUT/INTERNAL correspondence | Implemented |
| Auto-generated reference numbers | Implemented |
| Company isolation (SQL-level) | Implemented |
| User level visibility integration | Implemented |
| Workflow integration (submit/approve/return/reject) | Implemented |
| Signature selection and validation | Implemented |
| Final PDF generation | Implemented |
| Dispatch tracking | Implemented |
| Delivery/Acknowledgement tracking | Implemented |
| Movement history (assign/forward) | Implemented |
| Audit logging (6 of 10 actions) | Implemented |
| Notification templates (3 correspondence-specific) | Defined |
| Frontend: list, detail, create, edit pages | Implemented |
| Frontend: assign, forward, dispatch dialogs | Implemented |
| Frontend: response panel, timeline | Implemented |

### Ambiguous Behavior (Needs Business Decision)

| Question | Detail |
|---|---|
| **What is `PROCESSING` status for?** | Defined in enum but never assigned. Is it a manual status or should the system auto-set it? |
| **What is `REGISTERED` status for?** | Defined in enum but never assigned. Is this a separate step from `RECEIVED`? |
| **What is `READY_FOR_DISPATCH` for?** | Defined in enum, accepted by dispatch validation, but no method transitions to it. Is this an intermediate status between approval and dispatch? |
| **When is correspondence COMPLETED?** | Status exists, is terminal, but no method transitions to it. Should there be a `complete_correspondence()` method? Who triggers it? |
| **When is correspondence CANCELLED/ARCHIVED?** | Same as above — statuses exist but no transition logic. |
| **Who marks IN as responded?** | `response_received` and `responded_at` fields exist but no method sets them. When the OUT is dispatched? When the user manually marks it? |
| **What is the "Due Soon" threshold?** | Spec mentions visual distinction but defines no time threshold (3 days? 5 days? configurable?) |
| **Can dispatched correspondence be re-dispatched?** | Currently blocked by idempotency check. Business may want to re-dispatch with a new courier if the first fails. |
| **Should `assigned_user_id` filter work?** | Parameter accepted but dead code in the query. |
| **Can SUPERADMIN create/update correspondence?** | Service has no SUPERADMIN-specific restrictions on correspondence mutation (unlike workflow where SUPERADMIN is blocked). |

### Missing Behavior (Not Implemented)

| Feature | Detail |
|---|---|
| **`complete_correspondence()` method** | No way to transition to COMPLETED status |
| **`cancel_correspondence()` method** | No way to transition to CANCELLED status |
| **`archive_correspondence()` method** | No way to transition to ARCHIVED status |
| **`response_received` auto-update** | No mechanism to mark IN as responded when OUT is dispatched |
| **Automated SLA reminders** | No background task to send deadline-approaching emails |
| **Overdue escalation** | No automatic escalation when deadline passes |
| **Dispatch failure/retry** | No "dispatch failed" status or re-dispatch mechanism |
| **Audit for deliver/acknowledge** | `mark_delivered()` and `mark_acknowledged()` do not call `_log_audit()` |
| **Notifications wired for assign/forward/dispatch** | Templates exist but are not invoked by service methods |
| **`AuditModule.CORRESPONDENCE` usage** | Audit module constant exists but service uses `AuditModule.DOCUMENTS` |
| **Duplicate dispatch prevention audit** | When re-dispatch is blocked, no audit event is generated |
| **Download audit events** | `DOWNLOAD_CORRESPONDENCE` and `DOWNLOAD_FINAL_CORRESPONDENCE` actions defined but never logged |
| **Workflow status sync to correspondence status** | Correspondence `status` stays at `SUBMITTED` during workflow; no mechanism to update it to `APPROVED` when workflow completes |

### Potential Implementation Risks

| Risk | Severity | Detail |
|---|---|---|
| **No `completed` transition** | High | Correspondence can never reach terminal `COMPLETED` state; lifecycle is incomplete |
| **No response-received linkage** | High | IN → OUT response chain has no automatic completion trigger |
| **Notifications not wired** | Medium | Assignment, forward, dispatch emails defined but never sent |
| **Audit gaps** | Medium | Deliver, acknowledge, download events not audited |
| **SQLite concurrency** | Low | `with_for_update()` skipped in tests; race condition possible in SQLite deployments |
| **`assigned_user_id` dead code** | Low | Filter parameter accepted but ignored in query |
| **`AuditModule.DOCUMENTS` misuse** | Low | All correspondence audits logged under DOCUMENTS module, not CORRESPONDENCE |
| **Status model confusion** | Medium | Dual status model (correspondence status vs workflow status) may confuse users if frontend doesn't clearly distinguish them |
| **`assign` from terminal status** | Low | `assign_correspondence()` has no status guard; can assign a COMPLETED correspondence |

---

## 24. Final Master Flow

### Master Diagram

```
                         CORRESPONDENCE MANAGEMENT
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
           INBOUND              OUTBOUND             INTERNAL
              │                    │                    │
              ▼                    ▼                    ▼
        ┌──────────┐         ┌──────────┐         ┌──────────┐
        │ Upload   │         │ Write    │         │ Write    │
        │ Document │         │ Body     │         │ Body     │
        └────┬─────┘         └────┬─────┘         └────┬─────┘
             │                    │                    │
             ▼                    ▼                    ▼
        ┌──────────┐         ┌──────────┐         ┌──────────┐
        │ RECEIVED │         │  DRAFT   │         │  DRAFT   │
        └────┬─────┘         └────┬─────┘         └────┬─────┘
             │                    │                    │
             ▼                    │                    │
        ┌──────────┐              │                    │
        │ Assign   │◄─────────────┼────────────────────┘
        └────┬─────┘              │
             │                    │
             ▼                    ▼
        ┌──────────┐         ┌──────────┐
        │ ASSIGNED │         │ Submit   │
        └────┬─────┘         └────┬─────┘
             │                    │
             ▼                    ▼
        ┌──────────┐         ┌──────────┐
        │ Review   │         │SUBMITTED │
        └────┬─────┘         └────┬─────┘
             │                    │
             ▼                    ▼
     ┌───────────────┐      ┌───────────────┐
     │Response Req?  │      │   WORKFLOW    │
     └───┬───────┬───┘      └───┬───────┬───┘
        YES      NO            Approve  Reject/Return
         │        │               │        │
         ▼        │               ▼        ▼
    ┌─────────┐   │          ┌────────┐  (Edit & Resubmit)
    │Create OUT│   │          │APPROVED│
    └────┬────┘   │          └────┬───┘
         │        │               │
         ▼        │               ▼
    ┌─────────┐   │          ┌──────────┐
    │OUT Full │   │          │ Signature│
    │Lifecycle│   │          └────┬─────┘
    └────┬────┘   │               │
         │        │               ▼
         │        │          ┌──────────┐
         │        │          │Final PDF │
         │        │          └────┬─────┘
         │        │               │
         │        │               ▼
         │        │          ┌──────────┐
         │        │          │ Dispatch │
         │        │          └────┬─────┘
         │        │               │
         │        │               ▼
         │        │          ┌──────────┐
         │        │          │ Delivered│
         │        │          └────┬─────┘
         │        │               │
         │        │               ▼
         │        │          ┌──────────────┐
         │        │          │ Acknowledged │
         │        │          └────┬─────────┘
         │        │               │
         ▼        ▼               ▼
    ┌─────────────────────────────────┐
    │           COMPLETED            │
    └─────────────────────────────────┘
```

### Executive Summary

**Correspondence Management** is a formal communication tracking system that sits on top of the existing DMS document infrastructure. It handles three types of organizational communication: **Incoming** (from external parties), **Outgoing** (to external parties), and **Internal** (between departments).

Every correspondence receives a unique reference number (`COR-{Company}-{Year}-{Sequence}`), is owned by a specific company, and follows a defined lifecycle from creation through completion.

**The core business value** is answering: *What came in, who is responsible, what action was taken, what response was produced, and what happened afterward?*

**The lifecycle in plain language:**

1. **Receive or Create** — A letter arrives (IN) or a user drafts one (OUT/INTERNAL). The system records who sent it, who it's for, and when it arrived.

2. **Classify and Assign** — An administrator categorizes the correspondence, sets its priority, and assigns a responsible person. The system tracks who is currently responsible.

3. **Route and Review** — The responsible person reviews the correspondence, may forward it to a colleague, and determines if a formal response is needed.

4. **Submit for Approval** — If approval is required, the correspondence enters a multi-step approval workflow. Approvers can approve, return for changes, reject, or request clarification.

5. **Sign and Finalize** — After approval, the author's signature and approver signatures are attached. A final PDF can be generated on demand.

6. **Dispatch** — An administrator records how the correspondence was sent (courier, email, hand delivery), the tracking reference, and when it was dispatched. This is a deliberate, recorded business event — not an automatic consequence of approval.

7. **Track Delivery** — The system tracks whether the correspondence was delivered and acknowledged. These are manual records, not automated.

8. **Complete** — The correspondence lifecycle concludes when all required actions are taken and any response deadlines are met.

**Throughout the entire lifecycle**, every action is audited (who did what, when, for which company), company isolation is enforced (Company A cannot see Company B's data), and user-level visibility restrictions apply (not everyone sees everything).

**What is fully working today:** Create, list, view, update, assign, forward, submit, dispatch, deliver, acknowledge, reference generation, company isolation, user level integration, workflow integration, signature handling, PDF generation, movement history, and most audit events.

**What needs attention:** The `COMPLETED`/`CANCELLED`/`ARCHIVED` status transitions have no service methods, the IN→OUT response completion linkage is not automated, notification templates for assign/forward/dispatch are defined but not wired, and audit logging is missing for deliver/acknowledge/download events.
