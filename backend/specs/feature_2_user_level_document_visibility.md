You are working on this project. Before making any changes, thoroughly read and strictly follow the guidelines defined in `AGENTS.md`. Follow the existing architecture, coding standards, database design principles, RBAC implementation, service/repository pattern, API conventions, and UI design. Reuse existing components and business logic wherever possible. Do not duplicate code or introduce unnecessary complexity.

# Objective

Extend the existing **Document Upload** functionality to support **User Level-based document visibility**.

Only users with the **Maker** role are allowed to upload documents. During the upload process, the Maker must explicitly select which **User Levels** are permitted to view the uploaded document.

The existing Role-Based Access Control (RBAC) system must remain unchanged.

This feature introduces an additional **document visibility layer** based on User Levels. It does **not** replace the existing RBAC model.

---

# Business Requirement

Every user belongs to exactly one User Level.

Example:

| User | Role | User Level |
|------|------|------------|
| maker1@dms.com | Maker | High |
| maker2@dms.com | Maker | Medium |
| reviewer1@dms.com | Reviewer | High |
| reviewer2@dms.com | Reviewer | Low |
| admin@dms.com | Admin | All Levels |

---

# Upload Behaviour

Only users having the **Maker** role can upload documents.

During document upload, the Maker must be presented with a list of all active User Levels as a **multi-select checkbox list**.

Example:

```
Document Visibility

☑ High
☑ Medium
☐ Low
```

The Maker can select one or more User Levels.

The selected User Levels determine which users are allowed to view the uploaded document.

The document should store the selected User Level permissions as part of its metadata/relationship.

The uploader's own User Level must **not** automatically determine document visibility.

Visibility is based **only** on the User Levels explicitly selected by the Maker during upload.

---

# Document Visibility Rules

A document is visible only when:

1. The authenticated user has the required RBAC permission (View).
2. The authenticated user's assigned User Level is included in the document's permitted User Levels.

Example 1

Maker selects:

```
☑ High
☑ Medium
☐ Low
```

The document is visible to:

✔ High users

✔ Medium users

✔ Administrators

The document is NOT visible to:

✖ Low users

---

Example 2

Maker selects:

```
☐ High
☐ Medium
☑ Low
```

Visible to:

✔ Low users

✔ Administrators

Not visible to:

✖ High users

✖ Medium users

---

# Administrator Behaviour

Administrators always have unrestricted access.

Administrators can:

- View every document
- Search every document
- Download every document
- Preview every document
- Manage every document

Administrators bypass User Level visibility restrictions while continuing to respect the existing RBAC model.

---

# Existing RBAC

Do **not** modify the existing Role-Based Access Control implementation.

Existing permissions remain unchanged:

- View
- Create
- Update
- Delete
- Download

User Level visibility must be evaluated **after** the RBAC permission check.

Access flow:

```
Authentication
        ↓
RBAC Permission Check
        ↓
Document User Level Permission Check
        ↓
Access Granted / Denied
```

Both checks must succeed before access is granted.

---

# Document Retrieval

Apply User Level visibility filtering to every API that returns document information, including but not limited to:

- Dashboard
- Document List
- Search
- Folder View
- Recent Documents
- Document Details
- Preview
- Download
- Any document listing API

Filtering must be enforced in the backend.

Do not rely on frontend filtering.

---

# Search Behaviour

Search results must only include documents that the authenticated user is authorised to view.

Example:

A High-level user searches for:

```
Financial Report
```

Matching documents exist:

- High-only
- Medium-only
- High & Medium
- Low-only

The High-level user should only receive:

- High-only
- High & Medium

The remaining documents must not appear in the results.

---

# Download & Preview

Download and Preview require:

1. Existing RBAC permission.
2. User's assigned User Level must exist in the document's permitted User Levels.

Otherwise, access must be denied.

---

# User Interface

Enhance the existing Upload Document page.

Add a new section:

```
Document Visibility

Select User Levels allowed to view this document

☐ High
☐ Medium
☐ Low
```

Requirements:

- Multi-select checkbox control.
- Load active User Levels dynamically.
- At least one User Level must be selected.
- Display validation if none are selected.
- Preserve the existing upload workflow.

---

# Database Design

Design the solution following normalised database principles.

A document may be visible to multiple User Levels.

Implement a proper many-to-many relationship between:

- Documents
- User Levels

Do not store comma-separated values.

Do not duplicate User Level names.

Follow the existing database design conventions defined in `AGENTS.md`.

---

# Backend Architecture

Follow the architecture defined in `AGENTS.md`.

```
Frontend
    ↓
FastAPI Routes
    ↓
Service Layer
    ↓
Repository Layer
    ↓
Database
```

Repository responsibilities:

- Persist document visibility mappings.
- Apply User Level filtering in document queries.
- Retrieve permitted User Levels for documents.

Service responsibilities:

- Validate selected User Levels.
- Enforce business rules.
- Apply Administrator bypass.
- Coordinate repository operations.

Routes:

- Reuse existing endpoints where appropriate.
- Preserve existing API contracts whenever possible.

---

# Security

User Level visibility must be enforced entirely on the backend.

Users must not be able to bypass restrictions by:

- Manipulating API requests
- Changing query parameters
- Modifying frontend state
- Guessing document IDs
- Direct URL access

Every document access request must validate:

1. Authentication
2. RBAC Permission
3. Document User Level Permission

---

# Validation Rules

- Only Makers can upload documents.
- At least one User Level must be selected during upload.
- A document may be assigned to multiple User Levels.
- Users can only view documents if their assigned User Level is included in the document's permitted User Levels.
- Administrators bypass User Level restrictions.
- Existing RBAC behaviour remains unchanged.
- Existing APIs remain backward compatible wherever possible.

---

# Testing

Add or update tests covering:

1. Only Makers can upload documents.
2. Upload fails if no User Level is selected.
3. Upload succeeds with one selected User Level.
4. Upload succeeds with multiple selected User Levels.
5. High-level users can access High documents.
6. Medium-level users can access Medium documents.
7. Users cannot access documents outside their permitted User Levels.
8. Documents shared with multiple User Levels are visible to all selected levels.
9. Administrators can access every document.
10. Search respects document visibility.
11. Download respects document visibility.
12. Preview respects document visibility.
13. Existing RBAC permissions continue to function correctly.
14. Existing document upload and management functionality remains unaffected.

---

# Constraints

- Read and strictly follow `AGENTS.md`.
- Reuse existing architecture, services, repositories, and components.
- Do not duplicate business logic.
- Do not modify the authentication mechanism.
- Do not replace or redesign the existing RBAC implementation.
- Implement User Level visibility as an additional authorisation layer.
- Keep the implementation modular, maintainable, extensible, and backward compatible.

---

# Deliverables

After implementation, provide:

1. Architecture summary.
2. Database design changes.
3. API changes.
4. Service layer changes.
5. Repository changes.
6. Frontend changes.
7. Files modified.
8. Security considerations.
9. Testing summary.
10. Explanation of how document visibility based on multiple User Levels integrates with the existing RBAC model without affecting existing functionality.