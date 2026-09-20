# Implementation Plan: Phase 3 - Signature & History

## Overview
This plan implements Phase 3 of the Approval Workflow System:
1. Signature model, service, and API endpoints
2. Link signatures to workflow actions
3. Frontend signature components (SignaturePad, SignatureUpload)
4. Frontend workflow instance pages (PendingApproval, ApprovalHistory)
5. Tests for all new functionality

## Estimated Effort
- Backend: ~4 hours
- Frontend: ~4 hours
- Tests: ~2 hours
- Total: ~10 hours

---

## Phase 3A: Backend - Signature Model & Service

### Step 1: Add Signature Model to workflow/models.py
**File:** workflow/models.py
**Changes:**
- Add SignatureType enum (e_signature, wet_signature)
- Add SignatureBase SQLModel class
- Add Signature table class with fields:
  - id (PK)
  - user_id (FK -> users.id)
  - file_name (VARCHAR 255)
  - file_path (VARCHAR 512)
  - mime_type (VARCHAR 127)
  - file_size (INT)
  - sig_type (SignatureType enum)
  - is_active (BOOLEAN, default True)
  - created_at (TIMESTAMP)
  - updated_at (TIMESTAMP)
- Add SignatureRead Pydantic schema
- Add relationship from WorkflowAction to Signature (optional)

### Step 2: Add SignatureCreate Schema to workflow/schemas.py
**File:** workflow/schemas.py
**Changes:**
- Add SignatureCreate request schema (for metadata, not file upload)

### Step 3: Create SignatureService in workflow/service.py
**File:** workflow/service.py
**Changes:**
- Add SignatureService class with methods:
  - upload_signature(file, current_user, sig_type) -> SignatureRead
    - Validate file type (JPEG, PNG only)
    - Save to storage/uploads/signatures/{user_id}/
    - Create DB record
    - Log audit event
  - get_signature(signature_id, current_user) -> SignatureRead
    - Check ownership or admin
  - get_signature_file(signature_id, current_user) -> Path
    - Return file path for serving
  - soft_delete_signature(signature_id, current_user) -> SignatureRead
    - Set is_active=False
    - Log audit event
  - alidate_signature_exists(signature_id) -> Signature
    - Used by act_on_instance to validate signature_id

### Step 4: Add Signature Endpoints to workflow/router.py
**File:** workflow/router.py
**Changes:**
- Add signature_router = APIRouter()
- Endpoints:
  - POST /signatures - upload signature (multipart form data)
  - GET /signatures/{id} - get signature metadata
  - GET /signatures/{id}/file - serve signature file
  - DELETE /signatures/{id} - soft delete signature

### Step 5: Update ROUTE_PERMISSION_MAP in middleware/rbac.py
**File:** middleware/rbac.py
**Changes:**
- Add: ("POST", "/api/v1/signatures") -> PermissionAction.CREATE
- Add: ("GET", "/api/v1/signatures") -> PermissionAction.VIEW
- Add: ("DELETE", "/api/v1/signatures") -> PermissionAction.DELETE

### Step 6: Register Signature Router in main.py
**File:** main.py
**Changes:**
- Import signature_router from workflow.router
- Mount at /api/v1/signatures

### Step 7: Create Alembic Migration
**File:** migrations/versions/<timestamp>_signatures.py
**Changes:**
- Create signatures table with all columns and indexes
- down_revision = "c3d4e5f6a7b8" (workflow_instances)

---

## Phase 3B: Backend - Link Signature to Workflow Actions

### Step 8: Add FK Relationship to WorkflowAction
**File:** workflow/models.py
**Changes:**
- Add signature: Optional[Signature] relationship to WorkflowAction
- The signature_id field already exists (line 184)

### Step 9: Validate Signature in act_on_instance
**File:** workflow/service.py (ApprovalActionService.act_on_instance)
**Changes:**
- After creating action_record (line 920-930)
- If data.signature_id is provided:
  - Validate signature exists and is_active
  - Validate signature.user_id == current_user.id
  - If invalid, raise HTTPException

---

## Phase 3C: Frontend - Signature Components

### Step 10: Add Types to workflow.types.ts
**File:** dms-app/src/types/workflow.types.ts
**Changes:**
- Add SignatureType = 'e_signature' | 'wet_signature'
- Add Signature interface
- Add WorkflowInstance interface
- Add WorkflowAction interface
- Add WorkflowHistory interface
- Add WorkflowInstanceDetail interface

### Step 11: Add API Methods to workflow.api.ts
**File:** dms-app/src/api/workflow.api.ts
**Changes:**
- submitInstance(data) -> POST /workflow-instances
- getInstances(params) -> GET /workflow-instances
- getPendingInstances(params) -> GET /workflow-instances/pending
- getMyInstances(params) -> GET /workflow-instances/mine
- getInstance(id) -> GET /workflow-instances/{id}
- actOnInstance(id, data) -> POST /workflow-instances/{id}/actions
- getHistory(id) -> GET /workflow-instances/{id}/history
- uploadSignature(file, sigType) -> POST /signatures
- getSignature(id) -> GET /signatures/{id}

### Step 12: Create SignaturePad Component
**File:** dms-app/src/components/SignaturePad.tsx
**Features:**
- HTML5 Canvas for wet-signature capture
- Mouse and touch event support
- Clear button
- Save button (returns base64 or blob)
- Responsive design

### Step 13: Create SignatureUpload Component
**File:** dms-app/src/components/SignatureUpload.tsx
**Features:**
- File input for image upload (JPEG, PNG)
- Preview of uploaded signature
- Drag-and-drop support
- File size validation

---

## Phase 3D: Frontend - Workflow Instance Pages

### Step 14: Create PendingApprovalPage
**File:** dms-app/src/pages/PendingApprovalPage.tsx
**Features:**
- List of documents pending current user's approval
- Show document title, submitter, submission date
- Approve/Reject/Return action buttons
- Signature attachment option (SignaturePad or SignatureUpload)
- Remarks text field
- Confirmation dialog

### Step 15: Create ApprovalHistoryPage
**File:** dms-app/src/pages/ApprovalHistoryPage.tsx
**Features:**
- Timeline view of workflow events
- Show event type, actor name, designation, timestamp
- Show remarks for each event
- Filter by event type
- Status badges

### Step 16: Update App.tsx Routes
**File:** dms-app/src/App.tsx
**Changes:**
- Add route for /approvals/pending -> PendingApprovalPage
- Add route for /approvals/history/:instanceId -> ApprovalHistoryPage

---

## Phase 3E: Tests

### Step 17: Create tests/test_signatures.py
**Tests:**
- test_upload_signature_success
- test_upload_signature_invalid_file_type
- test_get_signature_metadata
- test_get_signature_file
- test_soft_delete_signature
- test_cannot_delete_others_signature
- test_validate_signature_exists

### Step 18: Update tests/test_workflow.py
**Add tests:**
- test_act_on_instance_with_valid_signature
- test_act_on_instance_with_invalid_signature
- test_act_on_instance_with_others_signature
- test_history_records_signature_reference

### Step 19: Run All Tests
**Command:** pytest
**Verify:** All tests pass

---

## Implementation Order

1. **3A: Backend Signature** (Steps 1-7)
2. **3B: Link to Actions** (Steps 8-9)
3. **3E: Backend Tests** (Steps 17-19) - run after backend changes
4. **3C: Frontend Signature** (Steps 10-13)
5. **3D: Frontend Pages** (Steps 14-16)

---

## Risk Areas

1. **File storage security:** Ensure path traversal prevention (use resolve_storage_path pattern from documents/utils.py)
2. **SQLite vs PostgreSQL:** Test migration works with both (SQLite doesn't support all PostgreSQL features)
3. **Canvas compatibility:** SignaturePad must work across browsers (use established canvas patterns)
4. **Signature validation:** Must validate signature belongs to acting user, not just exists

---

## Dependencies

- No new pip packages required
- No new npm packages required (use native HTML5 Canvas API)
- Existing: FastAPI, SQLModel, React, Zustand

---

## Definition of Done

### Backend
- [ ] POST /api/v1/signatures accepts file upload, returns SignatureRead
- [ ] GET /api/v1/signatures/{id} returns metadata (owner or admin)
- [ ] GET /api/v1/signatures/{id}/file serves binary file
- [ ] DELETE /api/v1/signatures/{id} soft-deletes (is_active=False)
- [ ] act_on_instance validates signature_id (exists, active, owned by user)
- [ ] Alembic migration creates signatures table
- [ ] Audit events logged for signature operations
- [ ] All pytest tests pass

### Frontend
- [ ] SignaturePad.tsx captures wet-signature via canvas
- [ ] SignatureUpload.tsx handles image upload
- [ ] PendingApprovalPage shows signature attachment option
- [ ] ApprovalHistoryPage displays timeline
- [ ] npm run build passes
- [ ] npm run lint passes
