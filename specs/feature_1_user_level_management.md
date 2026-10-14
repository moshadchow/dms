You are working on this project. Before making any changes, read and strictly follow the guidelines defined in `AGENTS.md`. Adhere to the existing project architecture, coding standards, naming conventions, database design principles, RBAC implementation, and UI conventions. Reuse existing components, services, repositories, and APIs wherever possible. Do not duplicate logic.

# Objective

Implement a **User Level Management** feature that allows administrators to create logical user level groups and assign users to those groups.

This feature introduces an additional access control layer that works alongside the existing Role-Based Access Control (RBAC) system.

**Existing roles and permissions must remain unchanged.**

---

# Business Requirements

The administrator should be able to create one or more **User Levels**.

Example:

```
High
Medium
Low
```

These are logical access groups and are independent of existing user roles.

---

# User Assignment

After creating User Levels, the administrator should be able to assign each user to exactly one User Level.

Example:

| User | User Level |
|------|------------|
| user@dms.com | High |
| user1@dms.com | Low |
| user2@dms.com | Medium |

Every user should belong to one User Level.

If required by the existing business rules, provide a configurable default level for newly created users.

---

# Administrator Access

By default, users with the **Administrator** role must have unrestricted access.

Administrators should:

- View all User Levels.
- View users from all User Levels.
- Assign users to any User Level.
- Modify User Levels.
- Delete User Levels (subject to validation).
- Manage users regardless of their assigned User Level.

Administrators must never be restricted by User Level filtering.

---

# Relationship with Existing RBAC

The current Role-Based Access Control system must remain unchanged.

Current permissions such as:

- View
- Create
- Update
- Delete
- Download

must continue to work exactly as they do today.

The new **User Level** feature is **not a replacement for roles**.

Instead:

```
Authentication
        ↓
User
        ↓
Role (existing RBAC)
        ↓
User Level (new logical grouping)
        ↓
Business Logic
```

Roles determine **what** a user can do.

User Level determines **which users, records, or resources** the user is allowed to access (based on future business rules).

---

# Functional Requirements

## User Level Management

Administrators should be able to:

- Create a User Level.
- Update a User Level.
- Delete a User Level.
- Activate/Deactivate a User Level (if supported by the existing architecture).
- View all configured User Levels.

Validation:

- User Level names must be unique.
- User Level names cannot be empty.
- Prevent duplicate names.
- Prevent deletion of a User Level that is still assigned to users, unless reassignment is performed first.

---

## User Management

Extend the existing User Management module.

When creating or editing a user:

- Display a User Level dropdown.
- Allow the administrator to assign a User Level.
- Persist the selected User Level.

The existing user creation and role assignment workflow must remain unchanged.

---

# Database Design

Design the solution following normalization principles.

Recommend introducing a dedicated table for User Levels rather than hardcoding values.

Example:

```
user_levels
------------
id
name
description
is_active
created_at
updated_at
```

Users should reference the assigned User Level through a foreign key.

Do not duplicate User Level names within the users table.

Follow the existing database design patterns used throughout the project.

---

# Backend Architecture

Follow the existing project architecture defined in `AGENTS.md`.

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

Responsibilities:

Repository

- CRUD operations for User Levels.
- User Level assignment.
- Database queries.

Service

- Business validation.
- Duplicate checking.
- Assignment rules.
- Deletion rules.
- Administrator bypass logic.

Routes

- Expose REST endpoints following existing API conventions.

---

# Frontend Requirements

Extend the existing Administration module.

Add a new section:

```
Administration
    └── User Levels
```

Features:

- User Level List
- Create User Level
- Edit User Level
- Delete User Level
- Search
- Pagination (if applicable)

Update the existing User Management screen:

- Add a User Level selector.
- Display the assigned User Level.
- Preserve existing Role assignment functionality.

---

# Future Compatibility

Design the feature so it can later support:

- Data visibility restrictions by User Level.
- Workflow approvals by User Level.
- Escalation based on User Level.
- Reporting by User Level.
- Dashboard filtering by User Level.

The implementation should be extensible without requiring major refactoring.

---

# Validation Rules

- User Level names must be unique.
- A user must have only one active User Level assignment.
- Administrators bypass User Level restrictions.
- Existing authentication and authorization must remain unaffected.
- Existing APIs must continue to function without regression.

---

# Testing

Add or update tests covering:

1. Create User Level.
2. Update User Level.
3. Delete User Level.
4. Prevent duplicate User Levels.
5. Assign User Level to a user.
6. Update a user's User Level.
7. Administrator can access all User Levels.
8. Existing RBAC permissions continue to work.
9. Existing User Management functionality remains unchanged.
10. Database integrity and foreign key validation.

---

# Constraints

- Read and strictly follow `AGENTS.md`.
- Reuse existing architecture and coding patterns.
- Do not duplicate repository or service logic.
- Keep the implementation modular and maintainable.
- Minimize breaking changes.
- Preserve backward compatibility.
- Do not modify the existing authentication mechanism.
- Do not change the existing RBAC implementation.

---

# Deliverables

After implementation, provide:

1. Architecture summary.
2. Database changes.
3. API changes.
4. Frontend changes.
5. Files modified.
6. Validation rules implemented.
7. Testing summary.
8. Explanation of how User Levels integrate with the existing RBAC model while preserving backward compatibility.