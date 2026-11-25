# DMS — Complete Correspondence Management Specification

## 1. Feature Name

**Correspondence Management**

Frontend navigation label:

```text
Correspondence
```

Primary submodules:

```text
Correspondence
├── All Correspondence
├── Incoming (IN)
├── Outgoing (OUT)
├── My Correspondence
├── Pending Actions
└── Overdue
```

The feature manages official organizational communications as first-class business records while reusing the existing DMS Document, Workflow, Signature, Notification, Audit, User Level, Category, and Company Profile infrastructure.

---

# 2. Objective

Correspondence Management must provide a complete lifecycle for:

* Incoming correspondence (`IN`)
* Outgoing correspondence (`OUT`)
* Internal correspondence (`INTERNAL`)
* Routing and assignment
* Response tracking
* Approval
* Electronic signatures
* Dispatch
* Delivery/acknowledgement tracking
* Search and filtering
* Audit history
* SLA/deadline monitoring
* Company isolation
* User Level visibility

The system must answer:

> What came in, from whom, when did it arrive, who is responsible, what action is required, what response was produced, who approved it, when was it sent, and what happened afterward?

---

# 3. Architectural Principle

Correspondence is **not a replacement for the existing Document entity**.

Use a layered architecture:

```text
Correspondence
      │
      ├── Business metadata
      ├── IN / OUT / INTERNAL direction
      ├── Reference number
      ├── Sender / recipient
      ├── Response tracking
      ├── SLA
      ├── Routing
      └── Lifecycle
            │
            ▼
       Document
            │
            ├── Physical file
            ├── User Level visibility
            ├── Versions
            └── Existing document access rules
            │
            ▼
        Workflow
            │
            ├── Approval
            ├── Return
            ├── Reject
            ├── Clarify
            └── Forward
            │
            ▼
        Signatures
            │
            ▼
        Audit / Notifications
```

Do not build a second document-permission, workflow, signature, or audit system.

The existing DMS workflow is document-type-agnostic and already supports approval actions, signatures, snapshots, User Level restrictions and audit logging.

---

# 4. Correspondence Directions

The system supports three directions:

```text
INBOUND
OUTBOUND
INTERNAL
```

## 4.1 INBOUND

Represents communication received by the company.

Examples:

* Government letter
* Regulatory notice
* Client letter
* Supplier correspondence
* Complaint
* Application
* External request
* Legal notice

Typical lifecycle:

```text
Received
   ↓
Registered
   ↓
Assigned
   ↓
Processing
   ↓
Response Required?
   ├── No → Completed
   │
   └── Yes
        ↓
     Response
        ↓
     OUTBOUND
        ↓
     Dispatched
        ↓
     Completed
```

---

# 5. OUTBOUND

Represents communication sent by the company.

Examples:

* Official reply
* Client response
* Government submission
* Regulatory response
* Notice
* Approval letter
* Request letter

Typical lifecycle:

```text
Draft
   ↓
Submitted
   ↓
Pending Approval
   ↓
Approved
   ↓
Signed
   ↓
Ready for Dispatch
   ↓
Dispatched
   ↓
Delivered / Acknowledged
   ↓
Completed
```

An OUTBOUND correspondence must not be considered dispatched merely because the PDF was generated or approved.

**Dispatch is a separate business event.**

---

# 6. INTERNAL

Internal correspondence represents communication between departments, units or users inside the same company.

Examples:

* Internal circular
* Department instruction
* Internal notice
* Office order
* Internal request

Internal correspondence must remain strictly within the same company.

A Company A user must never route internal correspondence to a Company B user.

---

# 7. Sender and Recipient Model

The current single `correspondent_*` model is too ambiguous for a complete IN/OUT implementation.

Use direction-aware concepts.

Recommended fields:

```text
sender_name
sender_organization
sender_email
sender_phone

recipient_name
recipient_organization
recipient_email
recipient_phone
```

For inbound:

```text
sender_*       = external sender
recipient_*    = receiving company / unit
```

For outbound:

```text
sender_*       = company / authorized sender
recipient_*    = external recipient
```

For internal:

```text
sender_*       = internal user/unit
recipient_*    = internal user/unit
```

If the existing architecture has reusable User/Department entities, reference them instead of duplicating data.

External correspondent information may remain denormalized as snapshot metadata because external parties do not necessarily exist as DMS users.

---

# 8. Database Model

## 8.1 `correspondences`

Create:

```text
correspondences
```

Recommended schema:

| Column                     | Type         | Constraint              |
| -------------------------- | ------------ | ----------------------- |
| `id`                       | int          | PK                      |
| `document_id`              | int          | FK, NOT NULL, UNIQUE    |
| `company_id`               | int          | FK, NOT NULL            |
| `created_by`               | int          | FK users.id, NOT NULL   |
| `reference_number`         | varchar(50)  | NOT NULL                |
| `direction`                | enum         | NOT NULL                |
| `status`                   | enum         | NOT NULL                |
| `subject`                  | varchar(255) | NOT NULL                |
| `body`                     | text         | nullable                |
| `priority`                 | enum         | NOT NULL                |
| `sender_name`              | varchar(255) | nullable                |
| `sender_organization`      | varchar(255) | nullable                |
| `sender_email`             | varchar(255) | nullable                |
| `sender_phone`             | varchar(50)  | nullable                |
| `recipient_name`           | varchar(255) | nullable                |
| `recipient_organization`   | varchar(255) | nullable                |
| `recipient_email`          | varchar(255) | nullable                |
| `recipient_phone`          | varchar(50)  | nullable                |
| `date_sent`                | datetime     | nullable                |
| `date_received`            | datetime     | nullable                |
| `response_required`        | bool         | NOT NULL, default false |
| `response_deadline`        | datetime     | nullable                |
| `response_received`        | bool         | NOT NULL, default false |
| `responded_at`             | datetime     | nullable                |
| `parent_correspondence_id` | int          | nullable FK             |
| `author_signature_id`      | int          | nullable FK             |
| `workflow_instance_id`     | int          | nullable FK             |
| `dispatch_method`          | enum/string  | nullable                |
| `dispatch_reference`       | varchar      | nullable                |
| `dispatched_at`            | datetime     | nullable                |
| `delivered_at`             | datetime     | nullable                |
| `created_at`               | datetime     | NOT NULL                |
| `updated_at`               | datetime     | NOT NULL                |

### Important correction

`company_id` should be **NOT NULL**.

Correspondence is company-specific and must never become a company-less business record.

The existing DMS uses `users.company_id` as the company relationship and applies company-level filtering at the service/database layer.

---

# 9. Category Relationship

Correspondence should support the existing **company-specific Categories** model.

Add:

```text
category_id
```

if the existing Document/Correspondence business requirements support classification.

Rules:

* Category must belong to the same company as the correspondence.
* ADMIN can select only categories belonging to their company.
* Non-admin users see only categories they are entitled to access.
* A client-supplied category from another company must be rejected.
* SUPERADMIN behavior must follow the existing Categories policy rather than bypassing it.

Do not attach a correspondence to a global/non-company category if the Categories module has now been made company-specific.

---

# 10. Reference Number

Reference numbers must be generated automatically.

Format:

```text
COR-{COMPANY_SHORT_NAME}-{YYYY}-{SEQUENCE}
```

Example:

```text
COR-ACME-2026-000042
COR-ABC-2026-000043
```

## Critical concurrency requirement

Do not implement:

```text
SELECT MAX(sequence) + 1
```

without transactional protection.

Two simultaneous requests could generate the same reference.

Use a transaction-safe sequence strategy appropriate to the existing database architecture.

The final reference number must be unique.

Recommended uniqueness:

```text
UNIQUE(reference_number)
```

The sequence should reset by company and year.

Example:

```text
ACME / 2026 → 000001
ACME / 2026 → 000002

XYZ / 2026 → 000001
```

The API:

```text
GET /correspondences/next-reference
```

must be treated as **preview information**, not as reservation of a number.

The definitive reference number is allocated during correspondence creation.

---

# 11. Document Creation Strategy

The original specification assumes every correspondence is an automatically generated HTML document.

That is insufficient for IN correspondence.

## OUTBOUND

For an OUTBOUND correspondence:

```text
Correspondence
   ↓
HTML body
   ↓
Document
   ↓
Approved PDF
```

An HTML working document is appropriate.

## INBOUND

For INBOUND correspondence, the original received document may be:

* PDF
* DOCX
* image
* scanned document
* other supported DMS file

Therefore, inbound correspondence must support **an uploaded original document/file**, rather than forcing every inbound record into a generated HTML document.

The correspondence should reference the underlying existing `Document`.

Do not duplicate the physical file unnecessarily.

---

# 12. Attachments

Correspondence must support attachments.

Examples:

```text
Incoming letter
   ├── Original Letter.pdf
   ├── Supporting Schedule.xlsx
   └── Annexure.pdf
```

Outbound:

```text
Official Reply
   ├── Final Letter.pdf
   └── Supporting Document.pdf
```

Use the existing DMS Document/DocumentVariant/attachment capabilities if available.

Do not create a second attachment storage mechanism.

All physical files must follow the existing company-aware storage architecture.

---

# 13. Physical Storage

Correspondence files must use the existing company-specific storage structure.

Target:

```text
STORAGE_ROOT/
└── {company_short_name}/
    ├── uploads/
    ├── correspondence/
    │   └── {user_id}/
    │       └── {uuid}.html
    ├── memos/
    └── signatures/
```

The company short name must be resolved server-side from:

```text
authenticated user
       ↓
user.company_id
       ↓
company.short_name
```

Never accept a client-provided physical storage path.

---

# 14. User Level Visibility

Correspondence must integrate with existing User Level visibility.

The existing DMS uses `DocumentUserLevelLink` and enforces User Level restrictions in the document access layer. Approval does not override these restrictions.

Therefore:

```text
Correspondence
      ↓
Document
      ↓
DocumentUserLevelLink
      ↓
User Level authorization
```

An approver must not automatically gain visibility simply because they are an approver.

The correspondence implementation must reuse:

```text
ensure_document_access()
ensure_document_user_level_access()
```

or the equivalent existing helpers.

---

# 15. Company Isolation

Company isolation is mandatory.

## ADMIN

ADMIN sees only:

```text
correspondences.company_id == current_user.company_id
```

This must happen at SQL level before:

* search
* sorting
* pagination
* count
* filtering

An ADMIN must not be able to access another company's correspondence by changing:

```text
?id=
/company_id=
/reference=
/search=
```

or by guessing a correspondence ID.

## SUPERADMIN

SUPERADMIN access must follow the existing DMS policy defined for this module.

Recommended:

* Can view correspondence across companies only with an explicit company context.
* No implicit "all companies" query.
* No company selected → empty result / "Please select a company."
* Company selection must be validated server-side.
* SUPERADMIN mutation permissions must be explicitly defined and must not be inferred merely from `AdminUser`.

The existing DMS distinguishes `AdminUser` from `SuperAdminUser`; `AdminUser` permits both ADMIN and SUPERADMIN, so service-level authorization is required whenever behavior differs.

---

# 16. Correspondence Lifecycle

Introduce an explicit correspondence status.

Recommended:

```text
draft
submitted
pending_approval
returned
rejected
approved
ready_for_dispatch
dispatched
delivered
completed
cancelled
archived
```

Not every direction needs every state.

## INBOUND

```text
received
registered
assigned
processing
awaiting_response
completed
archived
```

## OUTBOUND

```text
draft
submitted
pending_approval
returned
rejected
approved
ready_for_dispatch
dispatched
delivered
completed
cancelled
archived
```

## INTERNAL

```text
draft
submitted
pending_approval
approved
distributed
completed
archived
```

If the existing workflow status is authoritative, do not create conflicting status engines.

Instead, distinguish:

```text
workflow status
```

from:

```text
correspondence business status
```

and document exactly which one is authoritative for each transition.

---

# 17. Workflow Integration

Reuse the existing generic workflow engine.

Do not create a correspondence-specific approval engine.

The existing workflow lifecycle is:

```text
draft
→ submitted
→ pending_approval
→ returned / rejected / approved / cancelled
→ published
→ archived
```

and workflow instances snapshot their definition at submission time.

For outbound correspondence:

```text
Draft
   ↓
Submit
   ↓
Workflow Instance
   ↓
Approval
   ↓
Signature
   ↓
Ready for Dispatch
```

A correspondence submission must identify the correct workflow instance.

If multiple eligible workflows exist under the existing workflow rules, use the established workflow selection mechanism rather than inventing a new one.

---

# 18. Approval Actions

The existing approval engine supports:

* approve
* reject
* return
* clarify
* forward

Correspondence must integrate with those actions.

Expected behavior:

### Return

```text
Pending Approval
      ↓
Returned
      ↓
Author edits
      ↓
Resubmits
```

### Reject

Rejected correspondence must remain auditable and must not be silently deleted.

### Clarify

Clarification should generate the existing workflow notification/audit behavior.

### Forward

Forward should change workflow responsibility without physically moving the document.

---

# 19. Editing Rules

Reuse the existing Memo-style access rules where appropriate.

The existing memo rules are:

* Admin bypass
* Terminal statuses cannot be edited
* Author can edit non-terminal states
* Eligible approvers can edit draft/returned/rejected
* Approvers cannot edit during submitted/pending approval
* Signature can be updated before approval.

Correspondence should follow the same principle.

However, **dispatch data must become immutable after dispatch**, except for controlled post-dispatch updates such as delivery acknowledgement.

For example:

Before dispatch:

```text
recipient
subject
body
attachments
signature
```

may be changed according to permissions.

After dispatch:

```text
recipient
body
final PDF
dispatch reference
dispatch date
```

must not be silently altered.

Any correction should create a new correspondence/version according to existing DMS versioning rules.

---

# 20. Incoming Registration

INBOUND requires a registration workflow separate from outbound drafting.

Recommended operation:

```text
Receive
 ↓
Create IN record
 ↓
Assign reference number
 ↓
Upload original
 ↓
Enter sender metadata
 ↓
Set category
 ↓
Set priority
 ↓
Set response requirement
 ↓
Assign responsible user/unit
```

The received date must be recorded.

The document date and received date must remain separate.

---

# 21. Assignment & Routing

Correspondence must support assignment/routing.

Example:

```text
IN-ABC-2026-000042
        ↓
Admin
        ↓
Operations
        ↓
Compliance
        ↓
Manager
```

Do not physically move the document between storage folders when responsibility changes.

Record the movement in a database table.

---

# 22. New Table: `correspondence_movements`

Recommended:

| Column               | Purpose                    |
| -------------------- | -------------------------- |
| `id`                 | PK                         |
| `correspondence_id`  | Parent correspondence      |
| `from_user_id`       | Previous owner             |
| `to_user_id`         | New owner                  |
| `from_department_id` | Previous unit              |
| `to_department_id`   | New unit                   |
| `action`             | assign/forward/return/etc. |
| `remarks`            | Movement note              |
| `created_by`         | Actor                      |
| `created_at`         | Timestamp                  |

Every movement is immutable.

Do not allow users to edit historical movement records.

---

# 23. Assignment APIs

Add appropriate routes:

```text
POST /api/v1/correspondences/{id}/assign
POST /api/v1/correspondences/{id}/forward
GET  /api/v1/correspondences/{id}/movements
```

Reuse the existing workflow forward mechanism if it already represents the required business behavior.

Do not duplicate functionality if `workflow/approval_service.py` already provides it.

---

# 24. Response Tracking

The existing fields:

```text
response_required
response_deadline
response_received
```

are not sufficient by themselves.

Add:

```text
responded_at
response_correspondence_id
```

or use:

```text
parent_correspondence_id
```

with a clearly defined relationship.

Example:

```text
IN-ABC-2026-000042
        │
        └── OUT-ABC-2026-000018
```

The OUT correspondence must be able to identify the IN correspondence it answers.

Conversely, an IN correspondence should expose its response if one exists.

---

# 25. Response Relationship

Use a self-referencing relationship:

```text
parent_correspondence_id
```

Example:

```text
IN-000042
    ↑
    │ responds_to
    │
OUT-000018
```

Rules:

* OUT may reference an IN.
* The related IN must belong to the same company.
* Cross-company response relationships are forbidden.
* The frontend should offer a "Respond to" action from an IN record.
* Creating a response should prepopulate relevant metadata without copying mutable fields blindly.

---

# 26. Dispatch Management

OUT correspondence needs an explicit dispatch operation.

Add:

```text
POST /api/v1/correspondences/{id}/dispatch
```

Only an authorized user may dispatch.

Dispatch requires:

* approved correspondence
* final PDF
* required signature(s)
* valid recipient
* dispatch method

Possible dispatch methods:

```text
email
courier
post
hand_delivery
portal
other
```

Do not mark a correspondence as dispatched when merely downloading the PDF.

---

# 27. Delivery / Acknowledgement

Where the business requires it, support:

```text
dispatched
delivered
acknowledged
```

Store:

```text
dispatched_at
dispatch_reference
delivered_at
acknowledged_at
```

If acknowledgement is outside the system, allow authorized users to record the acknowledgement event and supporting evidence.

---

# 28. Final PDF

The final PDF should contain:

### Header

* Company name
* Company short name
* Correspondence reference number
* Date
* Direction

### Metadata

* Subject
* Sender
* Recipient
* Priority
* Related correspondence
* Response deadline where relevant

### Body

Sanitized correspondence HTML.

### Approval

* Approval status
* Approver information
* Approval dates
* Signatures in workflow order

### Dispatch

For finalized outbound correspondence:

* Dispatch method
* Dispatch date
* Dispatch reference

Do not expose internal database IDs.

---

# 29. Signature Integration

Reuse the existing Signature module.

The existing DMS stores signature files independently and integrates them into workflow approval without mutating the source document.

Do not duplicate signature storage.

Validate that the selected signature:

* belongs to the authorized user
* is active
* is valid for the operation
* has not been deleted

The final PDF must use the approved signature chain.

---

# 30. Notifications

Integrate with the existing Notifications module.

The existing system already sends workflow-related email notifications for submitted, approved, rejected, returned, clarified and forwarded events.

Correspondence should reuse those mechanisms.

Useful notifications:

```text
New correspondence assigned
Correspondence forwarded
Approval requested
Correspondence returned
Correspondence rejected
Correspondence approved
Response deadline approaching
Response overdue
Correspondence dispatched
Correspondence delivered
```

Do not introduce another notification service.

Email failures must not break correspondence transactions, consistent with the existing notification architecture.

---

# 31. SLA / Deadline

For `response_required = true`:

```text
response_deadline
```

is mandatory.

For:

```text
response_required = false
```

the deadline may be null.

Validation:

```text
response_required = true
AND
response_deadline IS NULL
```

→ reject request.

If deadline is in the past during creation, reject unless explicitly creating a historical record with an authorized mechanism.

---

# 32. Overdue Logic

A correspondence is overdue when:

```text
response_required = true
AND response_received = false
AND response_deadline < current UTC time
AND status not in terminal completion states
```

Do not persist a redundant `is_overdue` field unless there is a strong performance reason.

Calculate it dynamically.

Frontend should visually identify:

```text
On Track
Due Soon
Overdue
Completed
```

---

# 33. Search & Filters

List endpoint:

```text
GET /api/v1/correspondences
```

must support:

* search
* direction
* priority
* status
* category
* assigned user
* date range
* response required
* overdue
* reference number
* sender
* recipient
* company context where authorized

Search should cover:

```text
reference_number
subject
sender_name
sender_organization
recipient_name
recipient_organization
```

Company filter must be applied first at SQL level.

---

# 34. Pagination

Pagination must be performed after company and authorization filtering.

Correct:

```text
Authorization
 ↓
Company filter
 ↓
User Level/document access
 ↓
Search
 ↓
Filters
 ↓
Sort
 ↓
Pagination
 ↓
Count
```

Do not fetch all correspondence and filter in React.

---

# 35. Sorting

Support deterministic sorting.

Recommended:

```text
created_at DESC
```

as default.

Secondary sort:

```text
id DESC
```

This prevents unstable pagination when timestamps are identical.

---

# 36. Detail View

`GET /api/v1/correspondences/{id}` should return:

```text
reference number
direction
status
subject
body
sender
recipient
company
category
priority
received/sent dates
response information
workflow information
document information
attachments
current assignment
movement history
related correspondence
signature information
dispatch information
created/updated information
```

Do not return sensitive fields unnecessarily.

---

# 37. Download APIs

Separate concepts:

```text
GET /correspondences/{id}/download
```

for authorized document/file download.

And:

```text
GET /correspondences/{id}/download-final
```

for the approved/final PDF.

The existing proposed name:

```text
/download-final-draft
```

should be changed because an approved final document is no longer accurately described as a "draft."

Recommended:

```text
GET /api/v1/correspondences/{id}/download-final
```

---

# 38. Access Control

Use:

```text
CurrentUser
```

for authenticated access.

Do not rely exclusively on `AdminUser`, because it allows both ADMIN and SUPERADMIN.

Authorization must combine:

```text
Authentication
+
RBAC
+
Company isolation
+
Document access
+
User Level
+
Workflow eligibility
```

---

# 39. RBAC

Add all routes to:

```text
middleware/rbac.py
```

The existing middleware has a hardcoded route map, so missing entries create a security gap.

At minimum map:

```text
GET     /api/v1/correspondences
POST    /api/v1/correspondences
GET     /api/v1/correspondences/{id}
PATCH   /api/v1/correspondences/{id}
POST    /api/v1/correspondences/{id}/submit
POST    /api/v1/correspondences/{id}/assign
POST    /api/v1/correspondences/{id}/forward
POST    /api/v1/correspondences/{id}/dispatch
GET     /api/v1/correspondences/{id}/movements
GET     /api/v1/correspondences/{id}/download
GET     /api/v1/correspondences/{id}/download-final
GET     /api/v1/correspondences/next-reference
```

Use existing:

```text
view
download
create
update
delete
```

permissions.

Do not create:

```text
CORRESPONDENCE_APPROVE
CORRESPONDENCE_DISPATCH
```

as new global permission verbs.

Approval eligibility belongs to the existing workflow approval policy.

---

# 40. Audit

Every significant correspondence event must use:

```text
AuditService.log_event()
```

The existing DMS requires centralized audit logging and supports company-scoped audit records.

Add actions as required:

```text
CREATE_CORRESPONDENCE
UPDATE_CORRESPONDENCE
SUBMIT_CORRESPONDENCE
ASSIGN_CORRESPONDENCE
FORWARD_CORRESPONDENCE
RETURN_CORRESPONDENCE
REJECT_CORRESPONDENCE
APPROVE_CORRESPONDENCE
DISPATCH_CORRESPONDENCE
DOWNLOAD_CORRESPONDENCE
DOWNLOAD_FINAL_CORRESPONDENCE
COMPLETE_CORRESPONDENCE
ARCHIVE_CORRESPONDENCE
```

Avoid adding duplicate audit events when the existing workflow or document services already generate the corresponding event.

Every event must include the correct:

```text
company_id
actor
entity
entity_id
action
timestamp
```

---

# 41. Audit Immutability

No API may allow:

```text
PUT /audit
PATCH /audit
DELETE /audit
```

Correspondence users must never be able to modify audit history.

---

# 42. Data Integrity

Enforce:

### Company consistency

```text
correspondence.company_id
==
document.company_id
```

where the existing Document model supports company ownership.

### Creator consistency

```text
created_by
```

must be a valid user.

### User/company consistency

Assigned users must belong to the same company unless the existing architecture explicitly allows otherwise.

### Related correspondence consistency

```text
parent.company_id
==
child.company_id
```

### Category consistency

```text
category.company_id
==
correspondence.company_id
```

### Workflow consistency

The workflow instance must belong to the same document/correspondence/company context.

---

# 43. Transaction Management

Create/update operations involving:

```text
Correspondence
Document
User Level links
Workflow
Reference number
```

must be transactionally safe.

Avoid this failure:

```text
Correspondence created
Document creation fails
→ orphan correspondence
```

or:

```text
HTML file written
DB transaction fails
→ orphan physical file
```

Use a safe transaction/cleanup strategy.

Filesystem operations are not transactional, so failures must be explicitly handled.

---

# 44. HTML Sanitization

Body HTML must be sanitized using:

```text
bleach.clean()
```

with the same approved whitelist used by Memos.

Never render unsanitized user HTML into:

* browser
* PDF
* email
* preview

Do not allow arbitrary scripts.

---

# 45. PDF Security

The PDF generator must safely handle malformed HTML.

The existing Memo PDF generator has known ReportLab XML parsing constraints, including balanced-tag requirements. Reuse its safe conversion/sanitization pattern rather than introducing a separate unsafe renderer.

Test:

* nested formatting
* malformed HTML
* special characters
* long content
* tables
* empty tags
* Unicode
* RTL text where applicable

---

# 46. API Schema Separation

Create:

```text
CorrespondenceCreate
CorrespondenceUpdate
CorrespondenceSubmit
CorrespondenceAssign
CorrespondenceDispatch
```

Do not expose server-owned fields in create/update schemas:

```text company_id
created_by
document_id
workflow_instance_id
reference_number
created_at
updated_at
```

The backend owns these values.

---

# 47. Create API

```text
POST /api/v1/correspondences
```

Creation flow:

```text
Authenticate
 ↓
Authorize
 ↓
Resolve company
 ↓
Validate category
 ↓
Validate direction-specific fields
 ↓
Generate reference number
 ↓
Create Document
 ↓
Create Correspondence
 ↓
Create User Level links
 ↓
Write HTML/original file
 ↓
Commit
 ↓
Audit
```

If any critical operation fails, do not leave inconsistent database/file state.

---

# 48. Submit API

```text
POST /api/v1/correspondences/{id}/submit
```

Requirements:

* Correspondence must be editable.
* Required fields must be complete.
* Required signature must exist.
* Required workflow must exist.
* User must be authorized.
* Company must match.
* Document access must pass.

Then:

```text
WorkflowInstanceService.submit_instance()
```

must be used.

Do not implement workflow submission directly inside Correspondence.

---

# 49. Dispatch API

```text
POST /api/v1/correspondences/{id}/dispatch
```

Validation:

```text
status == approved/ready_for_dispatch
final document exists
recipient valid
dispatch method valid
```

Then:

```text
record dispatch
audit event
notification if configured
```

Dispatch must be idempotent.

A second dispatch request must not create a second dispatch event accidentally.

---

# 50. Completion

A correspondence should not be marked completed merely because it is approved.

Examples:

### OUTBOUND

```text
Approved
 ↓
Dispatched
 ↓
Delivered
 ↓
Completed
```

### INBOUND with response

```text
Received
 ↓
Processing
 ↓
Response Created
 ↓
Response Dispatched
 ↓
Completed
```

### INBOUND without response

```text
Received
 ↓
Processing
 ↓
Completed
```

---

# 51. Archiving

Archiving must use the existing DMS document/archive semantics where possible.

Do not delete the physical file when correspondence is archived.

Archived correspondence remains searchable according to user permissions.

---

# 52. Frontend Information Architecture

Recommended:

```text
Correspondence
│
├── All
├── Incoming
├── Outgoing
├── Internal
├── My Correspondence
├── Pending Actions
└── Overdue
```

The frontend must not implement authorization by hiding data only.

Backend responses remain authoritative.

---

# 53. List UI

Display:

| Column           | Description              |
| ---------------- | ------------------------ |
| Reference        | COR-ABC-2026-000001      |
| Direction        | IN / OUT / INTERNAL      |
| Subject          | Correspondence subject   |
| Sender/Recipient | Direction-aware          |
| Priority         | Badge                    |
| Status           | Lifecycle                |
| Assigned To      | Current responsible user |
| Response         | Required / received      |
| Due Date         | SLA                      |
| Created          | Date                     |

Priority badges:

```text
low      → gray
normal   → blue
high     → orange
urgent   → red
```

---

# 54. Detail UI

Sections:

```text
Header
Correspondence Metadata
Sender / Recipient
Body
Attachments
Response Information
Assignment
Workflow
Movement History
Audit/Timeline
Dispatch Information
Related Correspondence
```

Use tabs/sections if the page becomes too large.

---

# 55. Create/Edit UX

### Incoming

Fields:

```text
Direction = Incoming
Reference = auto
Received Date
Document Date
Sender
Sender Organization
Sender Email
Sender Phone
Subject
Category
Priority
Response Required
Response Deadline
Attachment
Assigned User
```

### Outgoing

Fields:

```text
Direction = Outgoing
Recipient
Recipient Organization
Recipient Email
Recipient Phone
Subject
Category
Priority
Related Incoming
Body
Author Signature
```

### Internal

Fields:

```text
Direction = Internal
Recipient User/Department
Subject
Category
Priority
Body
```

---

# 56. Direction-Specific Validation

Do not make every field universally optional.

Examples:

### INBOUND

`date_received` should be required.

Sender information should normally be required.

### OUTBOUND

Recipient information should normally be required.

`date_sent` is set at dispatch rather than merely at draft creation.

### INTERNAL

Internal recipient must be a valid user/unit in the same company.

The UI should show only fields relevant to the selected direction.

---

# 57. Reference Preview

The UI may show:

```text
Next Reference: COR-ABC-2026-000042
```

but must clearly treat it as a preview.

The backend assigns the final reference during creation.

Never trust a frontend reference number.

---

# 58. No Physical Movement During Assignment

This is important.

When:

```text
User A → User B
```

the file must remain in its company-controlled storage location.

Only the business ownership/movement record changes.

This avoids broken paths and unnecessary filesystem operations.

---

# 59. Company Short Name Changes

Because storage and reference numbers use:

```text
company.short_name
```

inspect Company Profile behavior.

If short name can change:

* storage directory must not become orphaned
* future references must use the new short name
* existing reference numbers must remain immutable
* existing document paths must remain resolvable

Do not rewrite historical correspondence reference numbers.

---

# 60. Notifications and Background Processing

Do not block correspondence transactions on email delivery.

Use the existing notification mechanism.

If response deadline reminders are introduced later, implement them through the existing background task architecture.

---

# 61. Frontend State / Race Conditions

When navigating between:

```text
Incoming
Outgoing
Internal
```

or changing filters:

* cancel/ignore stale requests
* prevent old results from overwriting new results
* reset pagination appropriately
* preserve filter state intentionally
* do not display stale correspondence from another company/user session

---

# 62. API Error Semantics

Use consistent errors.

Examples:

```text
401 → unauthenticated
403 → unauthorized
404 → inaccessible/nonexistent resource where appropriate
409 → state conflict/reference conflict
422 → validation failure
```

Do not expose cross-company existence information unnecessarily.

---

# 63. Migration

Create Alembic migrations for:

```text
correspondences
correspondence_movements
```

and any required indexes/FKs.

Production uses Alembic migrations; DEBUG-only `create_db_and_tables()` must not be treated as production schema management.

---

# 64. Indexes

At minimum index:

```text
company_id
reference_number
direction
status
priority
subject
created_by
date_received
date_sent
response_deadline
workflow_instance_id
parent_correspondence_id
```

Consider composite indexes based on actual query patterns:

```text
(company_id, status)
(company_id, direction)
(company_id, created_at)
(company_id, response_deadline)
```

Do not add excessive indexes without considering write cost.

---

# 65. Tests

Create:

```text
tests/test_correspondence.py
tests/test_correspondence_security.py
tests/test_correspondence_workflow.py
tests/test_correspondence_pdf.py
```

or consolidate according to existing project conventions.

Test all business paths.

---

# 66. Mandatory Test Matrix

## Creation

* ADMIN creates IN.
* ADMIN creates OUT.
* ADMIN creates INTERNAL.
* Maker creates correspondence if RBAC permits.
* Missing company rejected.
* Invalid category rejected.
* Cross-company category rejected.
* Client company_id rejected/ignored.
* Client created_by rejected/ignored.

## Company isolation

* Company A cannot see Company B.
* Company B cannot see Company A.
* URL ID manipulation blocked.
* Search cannot cross company.
* Pagination cannot cross company.
* Sort cannot cross company.
* Related correspondence cannot cross company.

## SUPERADMIN

Explicitly test whichever policy is selected:

* no company selected
* Company A selected
* Company B selected
* direct API manipulation
* unauthorized mutation

Do not accidentally inherit `AdminUser` behavior.

## Workflow

Test:

```text
draft
submit
pending approval
approve
return
reject
resubmit
cancel
```

## Response

Test:

```text
IN
 ↓
OUT response
```

and ensure:

* same company
* relationship is correct
* UI displays related correspondence

## Dispatch

Test:

* cannot dispatch draft
* cannot dispatch rejected
* cannot dispatch returned
* can dispatch approved
* dispatch recorded once
* dispatch audited

## SLA

Test:

* required response without deadline rejected
* deadline stored
* overdue calculated correctly
* completed response no longer overdue

## Files

Test:

* HTML generation
* inbound original upload
* download
* final PDF
* company storage path
* failed file write cleanup

## Security

Test:

* path traversal
* cross-company document ID
* cross-company category
* cross-company user assignment
* unauthorized download
* unauthorized dispatch

---

# 67. SQLite Test Compatibility

The project's tests use SQLite + StaticPool rather than PostgreSQL.

The fixture patches:

```text
core.database.engine
middleware.rbac.engine
middleware.audit.engine
```

Any new module importing the engine directly must be patched accordingly.

Prefer dependency injection/service-level sessions to minimize direct engine coupling.

---

# 68. Performance

Avoid N+1 queries.

For list responses, use appropriate eager/select-in loading for:

```text
company
created_by
category
assigned_user
document
```

Do not load movement history for every row in the list.

Load detailed movements only on the detail endpoint.

---

# 69. Audit Timeline

The detail page should ideally present a chronological timeline:

```text
15 Sep 09:15
Created by Admin

15 Sep 09:30
Assigned to Operations

15 Sep 10:20
Viewed

15 Sep 14:10
Forwarded to Compliance

16 Sep 09:00
Approved

16 Sep 11:30
Signed

16 Sep 14:00
Dispatched
```

Use existing audit/workflow/movement data rather than duplicating event storage unnecessarily.

---

# 70. Backend Files

Create:

```text
correspondence/
├── __init__.py
├── models.py
├── schemas.py
├── service.py
├── router.py
├── movement_service.py
└── pdf_generator.py
```

Only introduce additional files when the existing architecture warrants them.

Modify as necessary:

```text
audit/models.py
core/database.py
main.py
middleware/rbac.py
```

and existing:

```text
documents/
workflow/
signatures/
notifications/
categories/
```

where integration is required.

---

# 71. Frontend Files

Create:

```text
dms-app/src/types/correspondence.types.ts
dms-app/src/api/correspondence.api.ts

dms-app/src/pages/CorrespondenceListPage.tsx
dms-app/src/pages/CorrespondenceDetailPage.tsx

dms-app/src/components/correspondence/
├── CorrespondenceForm.tsx
├── CorrespondenceFilters.tsx
├── CorrespondenceTable.tsx
├── CorrespondenceTimeline.tsx
├── CorrespondenceMovementHistory.tsx
├── CorrespondenceResponsePanel.tsx
└── CorrespondenceDispatchDialog.tsx
```

Modify:

```text
App.tsx
Sidebar.tsx
```

Use:

```typescript
import apiClient from './client'
```

as required by the existing DMS frontend architecture.

---

# 72. API Endpoints — Final Set

## Core

```text
POST   /api/v1/correspondences
GET    /api/v1/correspondences
GET    /api/v1/correspondences/{id}
PATCH  /api/v1/correspondences/{id}
```

## Workflow

```text
POST /api/v1/correspondences/{id}/submit
```

Use the existing workflow instance/action APIs for approval operations rather than duplicating them.

## Movement

```text
POST /api/v1/correspondences/{id}/assign
POST /api/v1/correspondences/{id}/forward
GET  /api/v1/correspondences/{id}/movements
```

Only add these if equivalent existing workflow routes do not already satisfy the requirement.

## Dispatch

```text
POST /api/v1/correspondences/{id}/dispatch
```

## Download

```text
GET /api/v1/correspondences/{id}/download
GET /api/v1/correspondences/{id}/download-final
```

## Reference

```text
GET /api/v1/correspondences/next-reference
```

Again, this is a preview only.

---

# 73. Definition of Done

The feature is complete only when all of the following are true:

### Core

* [ ] Correspondence module exists.
* [ ] IN, OUT and INTERNAL are supported.
* [ ] Company isolation is enforced server-side.
* [ ] Reference numbers are generated safely.
* [ ] Reference numbers are unique.
* [ ] Company/year sequence works correctly under concurrency.
* [ ] Correspondence is linked 1:1 to Document where appropriate.

### IN

* [ ] Incoming documents can be registered.
* [ ] Original incoming files can be attached.
* [ ] Sender metadata is supported.
* [ ] Received date is captured.
* [ ] Response requirement is tracked.
* [ ] Incoming correspondence can be assigned.
* [ ] Incoming correspondence can be linked to an outgoing response.

### OUT

* [ ] Outgoing documents can be drafted.
* [ ] Recipient metadata is supported.
* [ ] Rich-text body is sanitized.
* [ ] Workflow approval works.
* [ ] Signatures work.
* [ ] Final PDF works.
* [ ] Dispatch is a separate operation.
* [ ] Dispatch metadata is recorded.
* [ ] Delivery/acknowledgement can be recorded where applicable.

### INTERNAL

* [ ] Internal correspondence works.
* [ ] Internal recipients are same-company only.
* [ ] Cross-company internal routing is impossible.

### Workflow

* [ ] Existing workflow engine is reused.
* [ ] Submit works.
* [ ] Approval works.
* [ ] Return works.
* [ ] Reject works.
* [ ] Resubmit works.
* [ ] Cancel/archive behavior is defined.
* [ ] Workflow instance snapshot behavior remains intact.

### Security

* [ ] RBAC routes are registered.
* [ ] Company isolation is SQL-level.
* [ ] User Level restrictions remain enforced.
* [ ] Cross-company IDs cannot be accessed.
* [ ] Cross-company categories cannot be used.
* [ ] Cross-company users cannot be assigned.
* [ ] Path traversal is blocked.
* [ ] Client cannot control company_id.
* [ ] Client cannot control created_by.
* [ ] SUPERADMIN behavior is explicitly enforced.

### Audit

* [ ] Create audited.
* [ ] Update audited.
* [ ] Submit audited.
* [ ] Movement audited.
* [ ] Approval events audited through existing workflow audit.
* [ ] Dispatch audited.
* [ ] Download audited.
* [ ] Company_id is populated correctly.
* [ ] Audit records remain immutable.

### Storage

* [ ] Company-specific storage is used.
* [ ] IN original files are stored safely.
* [ ] OUT HTML/PDF files are stored safely.
* [ ] Attachments use existing storage mechanisms.
* [ ] No absolute paths are exposed.
* [ ] Files are not physically moved during logical assignment.

### SLA

* [ ] Response required validation works.
* [ ] Deadline validation works.
* [ ] Overdue logic works.
* [ ] Response completion clears overdue state.
* [ ] Pending/overdue UI works.

### Frontend

* [ ] Correspondence navigation exists.
* [ ] IN/OUT/INTERNAL filters work.
* [ ] Search works.
* [ ] Pagination works.
* [ ] Detail page works.
* [ ] Create/edit works.
* [ ] Workflow status is visible.
* [ ] Movement history is visible.
* [ ] Response information is visible.
* [ ] Dispatch information is visible.
* [ ] Related correspondence is visible.
* [ ] No stale cross-company data is displayed.

### Testing

* [ ] `pytest` passes.
* [ ] Correspondence-specific tests pass.
* [ ] Security tests pass.
* [ ] Workflow tests pass.
* [ ] PDF tests pass.
* [ ] Storage tests pass.
* [ ] `npm run build` passes.
* [ ] `npm run lint` passes.

---

# 74. Required Verification Commands

Backend:

```bash
alembic upgrade head
pytest
```

Frontend:

```bash
cd dms-app
npm run build
npm run lint
```

Do not weaken existing tests to make the new feature pass.

---

# 75. Implementation Guardrails

Before coding:

1. Read `AGENTS.md`.
2. Inspect Memos completely.
3. Inspect Documents completely.
4. Inspect Workflow completely.
5. Inspect Signatures.
6. Inspect Notifications.
7. Inspect Categories.
8. Inspect Company Profile.
9. Inspect Audit.
10. Trace existing storage path resolution.
11. Identify reusable access helpers.
12. Identify existing workflow routes that eliminate the need for duplicate correspondence routes.

Do not blindly implement the file list in this specification if repository inspection shows an existing service already provides the required functionality.

The implementation must adapt to the actual repository.

---

# 76. Final Product Definition

The finished feature should provide this complete business flow:

```text
                         CORRESPONDENCE
                               │
               ┌───────────────┼───────────────┐
               │               │               │
             INBOUND        OUTBOUND        INTERNAL
               │               │               │
               ▼               ▼               ▼
           Register          Draft           Draft
               │               │               │
               ▼               ▼               ▼
           Classify         Submit          Submit
               │               │               │
               ▼               ▼               ▼
           Assign          Approval        Approval
               │               │               │
               ▼               ▼               ▼
          Processing        Sign            Distribute
               │               │               │
               ▼               ▼               ▼
        Response Required?  Dispatch       Complete
             │
        ┌────┴────┐
        │         │
       No        Yes
        │         │
     Complete     ▼
              Create OUT
                 │
                 ▼
              Approve
                 │
                 ▼
              Sign
                 │
                 ▼
              Dispatch
                 │
                 ▼
             Complete
```

Across every branch:

```text
Company Isolation
       +
RBAC
       +
User Level Access
       +
Document Repository
       +
Workflow
       +
Signatures
       +
Notifications
       +
Audit Trail
       +
SLA Tracking
```

must operate as one integrated DMS capability.

**The objective is not merely to create an "IN/OUT" register. The objective is to create a complete, auditable correspondence lifecycle without duplicating the DMS's existing document, workflow, authorization, signature, notification, storage or audit architecture.**
