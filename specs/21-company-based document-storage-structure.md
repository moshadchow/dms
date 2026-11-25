# DMS — Company-Based Document Storage Structure

## Objective

Modify the existing DMS storage architecture so that all company-owned uploaded documents are physically stored under a directory named after the company's **short name**.

The company short name must become the top-level storage namespace under `dms/storage/`.

The existing document/user/directory hierarchy underneath `uploads/` should be preserved wherever possible.

### Target structure

```text
dms/
└── storage/
    ├── {COMPANY_SHORT_NAME}/
    │   ├── uploads/
    │   │   └── <existing document hierarchy>
    │   ├── memos/
    │   └── signatures/
    │
    └── {ANOTHER_COMPANY_SHORT_NAME}/
        ├── uploads/
        │   └── <existing document hierarchy>
        ├── memos/
        └── signatures/
```

Example:

```text
dms/storage/
├── ABC/
│   ├── uploads/
│   │   ├── 1/
│   │   │   └── 1/
│   │   │       └── document1.pdf
│   │   └── 1/
│   │       └── 2/
│   │           └── document2.docx
│   ├── memos/
│   └── signatures/
│
└── XYZ/
    ├── uploads/
    │   ├── 2/
    │   │   ├── 3/
    │   │   │   └── document1.pdf
    │   │   └── 4/
    │   │       └── document2.docx
    │   ├── memos/
    │   └── signatures/
```

---

# 1. First Inspect the Existing Implementation

Before changing anything:

1. Read `AGENTS.md`.
2. Inspect the entire existing storage implementation.
3. Identify how `STORAGE_ROOT` is configured.
4. Inspect:

   * `documents/`
   * `memos/`
   * `signatures/`
   * `storage_usage/`
   * `company_profile/`
   * `users/`
5. Find every place where a physical filesystem path is constructed.
6. Find every place where uploaded files are:

   * created
   * saved
   * downloaded
   * streamed
   * deleted
   * moved
   * restored
   * versioned
   * copied
   * referenced
7. Identify whether document paths are stored in the database and determine their current format.
8. Determine whether memos and signatures currently use independent storage paths.

Do not modify the code until the complete existing storage flow is understood.

---

# 2. Company Must Be the Storage Boundary

The existing company relationship is:

```text
users.company_id
        ↓
companies.id
        ↓
companies.short_name
```

Use this existing relationship.

Do NOT introduce:

* a new company table
* a second company identifier
* a new tenant table
* a duplicate company mapping
* hardcoded company names

The canonical company short name must come from the existing `Company` record.

---

# 3. Storage Path Resolution

Introduce/reuse a centralized storage-path resolution mechanism.

Conceptually:

```text
STORAGE_ROOT
    /
    <company.short_name>
        /
        uploads
```

For example:

```text
STORAGE_ROOT/ABC/uploads/
STORAGE_ROOT/XYZ/uploads/
```

Do not scatter path-building logic across multiple services.

There should be one authoritative mechanism for resolving company storage roots.

---

# 4. Company Short Name Validation

Because `company.short_name` becomes part of a filesystem path, it must be handled safely.

Never directly concatenate an untrusted request parameter into a filesystem path.

The company must be resolved from the authenticated user's/company relationship or an existing database entity.

The implementation must:

* normalize the short name according to existing company rules
* prevent path traversal
* prevent `../`
* prevent absolute paths
* prevent path separator injection
* prevent Windows path traversal
* prevent null-byte/path manipulation
* ensure the resolved path remains underneath `STORAGE_ROOT`

Do not trust a client-provided company short name.

---

# 5. Uploaded Documents

All newly uploaded documents must be stored under:

```text
STORAGE_ROOT/{company_short_name}/uploads/
```

The existing document hierarchy should remain beneath `uploads/`.

For example, if the current application produces:

```text
uploads/1/1/document1.pdf
```

it should become:

```text
ABC/uploads/1/1/document1.pdf
```

for a document belonging to Company ABC.

For Company XYZ:

```text
XYZ/uploads/2/3/document1.pdf
```

The company directory must therefore be the first physical storage boundary.

---

# 6. Determine Company from the Document/User

Do not allow the frontend to determine the physical storage company.

When uploading a document, determine the company from the authoritative backend relationship.

For example:

```text
Authenticated User
       ↓
User.company_id
       ↓
Company
       ↓
Company.short_name
       ↓
Storage Path
```

If the document itself has a company relationship already, verify that it is consistent with the authenticated user's company and existing access-control rules.

Never allow:

```text
POST /documents
company_short_name=XYZ
```

to cause a Company A user to write into:

```text
storage/XYZ/
```

---

# 7. Existing Document Access

Changing the physical storage structure must NOT weaken document authorization.

Existing access controls must remain intact.

Continue enforcing:

* authentication
* RBAC
* company isolation
* User Level visibility
* document permissions
* workflow restrictions
* existing access helpers

A valid physical path must never itself grant access to a document.

---

# 8. Download / View / Stream

Update every document download/view/stream operation to resolve the new company-based path.

Example:

```text
Document
   ↓
Company
   ↓
Company.short_name
   ↓
STORAGE_ROOT/{short_name}/uploads/...
   ↓
physical file
```

Do not accept an arbitrary filesystem path from the client.

Do not expose the physical server path in API responses.

The API should continue returning the existing logical document/file representation.

---

# 9. Delete / Restore / Archive

Review every operation that manipulates physical document files.

Ensure the company prefix is consistently used for:

* delete
* soft delete
* restore
* archive
* unarchive
* replacement
* version creation
* version deletion
* document duplication
* file replacement

No operation should accidentally operate on:

```text
STORAGE_ROOT/uploads/...
```

after the new structure is introduced.

---

# 10. Memos

Inspect the existing memo storage implementation.

The target structure should be:

```text
STORAGE_ROOT/{company_short_name}/memos/
```

if memo files are physically stored under the storage root.

For example:

```text
dms/storage/ABC/memos/
dms/storage/XYZ/memos/
```

Do not change memo database semantics unnecessarily.

Existing memo access and workflow behavior must remain unchanged.

---

# 11. Signatures

The existing signature implementation currently stores signatures under:

```text
STORAGE_ROOT/signatures/{user_id}/
```

as documented in the project guidelines.

Update the physical storage namespace to:

```text
STORAGE_ROOT/{company_short_name}/signatures/{user_id}/
```

For example:

```text
dms/storage/ABC/signatures/15/
dms/storage/XYZ/signatures/27/
```

Preserve the existing UUID filename strategy and signature security restrictions.

Do not change signature ownership semantics.

---

# 12. Storage Usage

Inspect `storage_usage/`.

The company-specific physical structure must remain compatible with the existing storage quota/usage calculation.

The existing project already tracks storage consumption per user/company.

Ensure storage calculations correctly account for:

```text
STORAGE_ROOT/{company_short_name}/
```

rather than assuming all company files exist directly under:

```text
STORAGE_ROOT/uploads/
```

Do not introduce double-counting.

Do not cause storage usage to remain incorrectly fixed because the scanner is looking at the old path.

Test:

* Company A usage
* Company B usage
* user-level usage, if applicable
* upload increases usage
* delete decreases usage
* files from Company A are never counted toward Company B

---

# 13. Database References

Inspect how document file paths are currently persisted.

Do not blindly rewrite database paths without understanding the existing contract.

If the database currently stores a relative path such as:

```text
uploads/1/1/document1.pdf
```

determine whether the best production approach is to:

### Preferred approach

Store a logical relative path that includes the company namespace:

```text
ABC/uploads/1/1/document1.pdf
```

and resolve it against `STORAGE_ROOT`.

OR, if the application already stores a logical document identifier separately from physical paths, preserve that abstraction and make the storage resolver generate the company-specific physical path.

Choose the approach that creates the smallest safe change while ensuring future uploads are company-isolated.

Do not store absolute filesystem paths in the database.

---

# 14. Existing Files / Migration

Do not leave existing production files inaccessible.

Before implementation, determine the current physical storage layout.

If existing files are currently:

```text
STORAGE_ROOT/uploads/...
STORAGE_ROOT/memos/...
STORAGE_ROOT/signatures/...
```

create a safe migration strategy.

Existing files must be moved into:

```text
STORAGE_ROOT/{company_short_name}/uploads/...
STORAGE_ROOT/{company_short_name}/memos/...
STORAGE_ROOT/{company_short_name}/signatures/...
```

where their company can be reliably determined.

### Critical requirement

Do NOT guess company ownership.

For every existing document:

```text
document
    ↓
owner/user/company
    ↓
company.short_name
```

must be deterministically resolved.

If a file cannot be safely attributed to a company:

* do not randomly assign it
* do not delete it
* do not silently move it
* report it for manual remediation or use an explicitly documented quarantine strategy

The migration must be idempotent.

Running it twice must not duplicate or corrupt files.

---

# 15. Backward Compatibility During Migration

If zero-downtime or staged deployment is relevant to the existing environment, design the migration so that there is no period where existing documents become inaccessible.

Consider a safe sequence such as:

```text
1. Deploy code capable of resolving old + new paths
2. Migrate existing files
3. Update database references if required
4. Verify files
5. Disable old-path fallback
```

Do not implement a destructive migration without first validating file ownership and path integrity.

---

# 16. Company Rename / Short Name Changes

This is an important production consideration.

Because `company.short_name` is being used as a physical directory name, inspect the existing Company Profile update behavior.

Determine whether `short_name` can currently be changed.

If it can be changed, do NOT leave the system pointing to:

```text
storage/OLD_SHORT_NAME/
```

after changing the company to:

```text
NEW_SHORT_NAME
```

Implement a safe strategy.

Preferred behavior:

```text
Company short name change
        ↓
validate old/new storage namespace
        ↓
move/rename company storage directory safely
        ↓
update references if required
        ↓
commit company change
```

Ensure partial failures do not result in lost files.

If the existing application intentionally treats `short_name` as immutable, preserve that behavior and document the dependency.

Do not silently change Company Profile semantics without inspecting the current implementation.

---

# 17. Company Deactivation

Company deactivation must not delete its storage.

For example:

```text
ABC
XYZ
```

If ABC becomes inactive:

```text
storage/ABC/
```

must remain intact.

Existing documents must remain physically preserved according to the existing DMS retention rules.

---

# 18. SUPERADMIN

Do not give SUPERADMIN implicit access to company storage merely because the filesystem contains company directories.

Physical storage organization and application authorization are separate concerns.

All API-level access must continue through the existing authorization model.

Do not create a new SUPERADMIN storage permission.

---

# 19. API Security

Review all APIs that accept:

* document IDs
* file IDs
* document paths
* filenames
* directory IDs
* memo IDs
* signature IDs

Ensure no endpoint can be exploited to escape the company-specific storage boundary.

Especially test:

```text
../../XYZ/...
```

and Windows-style traversal:

```text
..\..\XYZ\...
```

Also test encoded traversal and absolute path attempts where applicable.

Use canonical path resolution and verify the resulting path remains under the intended company storage root.

---

# 20. Race Conditions & Directory Creation

Directory creation must be safe under concurrent uploads.

Use:

```text
mkdir(..., exist_ok=True)
```

or the project's equivalent safe mechanism.

Two simultaneous uploads for the same company must not cause failures because the directory already exists.

---

# 21. Filename Safety

Continue using the existing secure filename/UUID strategy.

Never use the original uploaded filename directly as a path component without sanitization.

Prevent:

* path traversal
* separator injection
* control characters
* null bytes
* unexpected absolute paths

The original filename may remain metadata/display information if the existing application supports it.

---

# 22. Centralized Storage Service

If the current project does not already have a sufficiently centralized storage abstraction, introduce one rather than duplicating logic.

For example, conceptually:

```text
StorageService
    get_company_root(company)
    get_upload_path(company, ...)
    get_memo_path(company, ...)
    get_signature_path(company, ...)
    resolve_document_path(...)
    validate_path(...)
```

Adapt this to the existing architecture rather than blindly creating these exact methods.

The objective is:

> One authoritative implementation for company-aware physical storage paths.

---

# 23. Frontend

This change should normally require little or no visible frontend change.

The frontend must NOT:

* construct storage paths
* know `STORAGE_ROOT`
* determine company short names for filesystem purposes
* access physical storage directly

Existing API calls should continue to work.

If an API response currently exposes a file URL, update it only as necessary to work with the new backend storage resolver.

Do not expose internal filesystem paths.

---

# 24. Tests

Add comprehensive backend tests.

### Company isolation

Test:

```text
Company A upload → storage/ABC/...
Company B upload → storage/XYZ/...
```

Verify the files physically exist in the correct company directory.

### Cross-company protection

Verify Company A cannot access Company B files through the API.

### Path traversal

Test:

```text
../../
..\..\
absolute paths
encoded traversal
```

and verify they are rejected.

### Concurrent uploads

Test multiple uploads into the same company.

### Storage usage

Verify company storage calculations remain correct.

### Download

Verify uploaded files can still be downloaded.

### Delete

Verify deletion operates on the correct company path.

### Restore

Verify restore operates on the correct company path.

### Signatures

Verify:

```text
ABC/signatures/{user_id}/...
XYZ/signatures/{user_id}/...
```

### Memos

Verify:

```text
ABC/memos/...
XYZ/memos/...
```

### Existing files

If migration is implemented, test:

* migration
* ownership resolution
* idempotency
* missing company
* missing file
* duplicate destination
* rollback/error handling

---

# 25. Regression Tests

Run the complete existing test suite.

The project uses SQLite + StaticPool for tests rather than PostgreSQL, and the test fixture patches the relevant engines. Follow the existing test architecture.

Run:

```bash
pytest
```

Then:

```bash
cd dms-app
npm run build
npm run lint
```

Also run:

```bash
alembic upgrade head
```

against the development/test database as appropriate.

---

# 26. Acceptance Criteria

The implementation is complete only when:

* [ ] Company short name is the first-level storage namespace.
* [ ] Uploaded documents are stored under `{company_short_name}/uploads/`.
* [ ] Company A files never get stored under Company B's directory.
* [ ] Company cannot be selected by the client to determine physical storage.
* [ ] Company is resolved server-side.
* [ ] Existing document hierarchy under `uploads/` is preserved where possible.
* [ ] Memos are company-scoped physically.
* [ ] Signatures are company-scoped physically.
* [ ] Storage usage calculations remain correct.
* [ ] Download works.
* [ ] Delete works.
* [ ] Restore works.
* [ ] Archive/unarchive works.
* [ ] Versioning works.
* [ ] Cross-company access remains blocked.
* [ ] Path traversal is blocked.
* [ ] Absolute path manipulation is blocked.
* [ ] Existing User Level access remains unchanged.
* [ ] Existing RBAC remains unchanged.
* [ ] SUPERADMIN does not bypass application-level storage authorization.
* [ ] Existing files are safely migrated or explicitly accounted for.
* [ ] Migration is idempotent.
* [ ] Company short-name changes cannot orphan files.
* [ ] Company deactivation does not delete files.
* [ ] No absolute filesystem paths are exposed to clients.
* [ ] No frontend filesystem logic is introduced.
* [ ] Tests cover company isolation.
* [ ] Full backend test suite passes.
* [ ] Frontend build passes.
* [ ] Frontend lint passes.

---

# Final Implementation Principle

The final physical storage architecture must be:

```text
STORAGE_ROOT/
│
├── ABC/
│   ├── uploads/
│   ├── memos/
│   └── signatures/
│
├── XYZ/
│   ├── uploads/
│   ├── memos/
│   └── signatures/
│
└── ...
```

The authoritative mapping is:

```text
Authenticated User
        ↓
User.company_id
        ↓
Company
        ↓
Company.short_name
        ↓
Company Storage Root
        ↓
uploads / memos / signatures
```

Never use a client-provided company name or path to determine where a file is stored.

Do not claim the task is complete unless the actual repository has been modified and the migration, tests, build, and security checks have been executed successfully.
