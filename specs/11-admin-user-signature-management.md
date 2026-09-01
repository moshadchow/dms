# Prompt: Implement Admin User Signature Management

Act as a **Senior Full-Stack Engineer**.

Your task is to implement a complete **User Signature Management** feature in the existing application, including all necessary backend and frontend changes.

## Objective

Allow authorized **Admin users** to manage signatures for users from the Admin Panel.

Admin must be able to:

- Add/upload a user's signature.
- View an existing user's signature.
- Replace/update a user's signature.
- Delete a user's signature.

## Signature Storage

- Store uploaded signature files in a dedicated folder:

```text
signatures/
```

- Do not store the physical file itself in the database.
- Store the signature file path/reference in the database.
- Use the existing application file-storage architecture where applicable.
- Generate safe and unique filenames to prevent filename conflicts.

## Backend Requirements

Implement the necessary:

- Database model/schema changes.
- API endpoints.
- Service/business logic.
- File upload handling.
- File replacement handling.
- File deletion handling.
- Validation and authorization.

### Suggested operations

- Upload User Signature
- View User Signature
- Update/Replace User Signature
- Delete User Signature

### Update/Replace Behavior

When Admin uploads a new signature for a user:

```text
Existing Signature
        ↓
Replace with New Signature
        ↓
Update Database Path
```

- Ensure obsolete signature files are handled appropriately and do not leave unnecessary orphan files.

### Delete Behavior

When Admin deletes a user's signature:

```text
Delete Signature File
        ↓
Clear/Delete Signature Path from Database
```

- Ensure database and file storage remain consistent.

## Authorization

Only authorized Admin users can add, update, or delete user signatures. Regular users must not be able to manage another user's signature.

- Reuse the existing authentication and RBAC architecture.
- Do not bypass existing permission checks.

## Frontend Requirements

Add User Signature Management to the existing Admin Panel/User Management interface.

For each user, Admin should be able to:

```text
User
 ├── View Signature
 ├── Upload Signature
 ├── Replace Signature
 └── Delete Signature
```

### UI Requirements

- Show the current signature preview if available.
- Provide an upload control when no signature exists.
- Allow replacing the existing signature.
- Require confirmation before deleting a signature.
- Display meaningful success and error messages.
- Refresh the signature preview after upload, update, or deletion.

## File Validation

Apply appropriate validation based on the existing application standards.

At minimum, verify:

- Allowed signature file types.
- File size limits.
- Invalid or unsupported file handling.

Do not allow unsafe file uploads.

## Data Integrity

Ensure consistency between:

```text
Database Signature Path
        ↕
Physical File in signatures/ Folder
```

- Handle failures safely so that database records do not point to missing or invalid files.

## Existing Workflow Compatibility

Do not break existing:

- Memo functionality.
- Memo signature widgets.
- Approval workflow.
- Existing Maker/Approver signatures.
- User management.
- Authentication and RBAC.
- File/document management.

Reuse existing signature and file-storage functionality where possible instead of creating duplicate mechanisms.

## Acceptance Criteria

- [ ] Admin can upload a signature for a user.
- [ ] Signature file is stored in the `signatures/` folder.
- [ ] Signature path/reference is stored in the database.
- [ ] Admin can view the user's existing signature.
- [ ] Admin can replace/update the user's signature.
- [ ] Admin can delete the user's signature.
- [ ] Database and physical files remain consistent.
- [ ] Only authorized Admin users can manage signatures.
- [ ] Appropriate validation and error handling are implemented.
- [ ] Existing Memo, Workflow, Signature, RBAC, and User functionality remains unchanged.

## Final Instruction

First inspect the existing codebase, AGENTS.md, user model, file-storage implementation, signature functionality, Admin Panel architecture, and authentication/RBAC mechanisms.

Then implement the feature using the existing project patterns and architecture. Avoid duplicate file-storage or signature-management logic and do not modify unrelated functionality.
