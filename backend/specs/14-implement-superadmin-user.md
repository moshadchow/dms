Act as a **Senior Backend & Frontend Engineer** working on the existing DMS application.

Before making **any changes**, you must first read and follow the repository guidelines in **`AGENTS.md`** and thoroughly inspect the existing codebase, especially the current RBAC, roles, users, authentication, authorization, migration, and seed-data implementation. Do not make assumptions or introduce a parallel authorization mechanism.

Repository guidance:

### Objective

Introduce a new system role named **`SUPERADMIN`** into the existing role-based access control system.

### Requirements

1. **Create the `SUPERADMIN` role**

   * Add a new entry to the existing `roles` table.
   * Use the existing role model and migration conventions.
   * Role details:

     * `name`: `SUPERADMIN`
     * `description`: `Full system access; manages admins & companies.`
     * `id`: Use the existing identity/auto-generation mechanism.
     * `created_at`: Current datetime using the existing model/database convention.
   * Do not modify the existing roles or their permission behavior.

2. **SUPERADMIN authorization**

   * `SUPERADMIN` must have full system-level access according to the existing RBAC architecture.
   * A `SUPERADMIN` is specifically authorized to **create `ADMIN` users only**.
   * `SUPERADMIN` must **not** be allowed to create `MAKER`, `CHECKER`, `AUDITOR`, or other non-admin users through the user-management functionality.
   * Preserve the existing `ADMIN` user-management behavior unless the existing architecture requires a minimal change to enforce this distinction.
   * Do not introduce new permission verbs when the existing `view`, `create`, `update`, `delete`, and `download` permissions are sufficient.

3. **Use the existing `users` table**

   * Do not create a separate table/model for Super Admin users.
   * The default Super Admin must be stored in the existing `users` table and associated with the `SUPERADMIN` role using the existing role relationship.
   * Reuse the existing password hashing, authentication, role assignment, audit, and user-creation mechanisms.

4. **Seed migration**

   * Update the existing `seed.py` to create a default Super Admin user as part of the existing one-time seed/migration process.
   * Default username:

     * `superadmin`
   * Inspect the existing `users` schema and authentication implementation to determine the required fields and appropriate default values.
   * Do not hardcode an incompatible schema or bypass existing user creation logic.
   * The seed operation must be **idempotent**: running `python seed.py` multiple times must not create duplicate `SUPERADMIN` roles or duplicate `superadmin` users.
   * Follow the existing seed conventions for passwords and credentials.

5. **Database migration**

   * If the current database schema requires no structural change, do not create an unnecessary migration.
   * If role/user data or constraints require a migration, create an appropriate Alembic migration following the project's existing migration conventions.
   * Production environments must remain compatible with the documented Alembic workflow.

6. **Backend implementation**

   * Inspect the existing RBAC middleware, role models, user service, user router, authentication dependencies, and permission checks.
   * Implement the smallest production-safe change required to support `SUPERADMIN`.
   * Ensure authorization is enforced **server-side**, not only in the frontend.
   * Prevent privilege escalation by ensuring a Super Admin cannot assign arbitrary roles when creating users.
   * Ensure the API rejects unauthorized role creation attempts with the application's existing authorization/error-handling conventions.

7. **Frontend implementation**

   * Inspect the existing user-management UI and role-selection logic.
   * If the frontend exposes role selection for user creation, update it so that:

     * A `SUPERADMIN` can create/select **ADMIN** users only.
     * The UI does not present unauthorized roles to a Super Admin.
   * Treat frontend restrictions as UX only; backend authorization remains the authoritative security boundary.
   * Preserve the existing behavior for other roles.

8. **Audit**

   * Reuse the existing `AuditService` for Super Admin-related user/role management actions.
   * Do not introduce a separate audit mechanism.
   * Ensure relevant create-user and role-management activities remain auditable.

9. **Testing**

   * Inspect the existing test structure and fixtures before writing tests.
   * Add/update tests covering at minimum:

     * `SUPERADMIN` role is seeded correctly.
     * `superadmin` user is seeded correctly.
     * Seed execution is idempotent.
     * Super Admin can authenticate successfully.
     * Super Admin can create an `ADMIN` user.
     * Super Admin cannot create `MAKER`.
     * Super Admin cannot create `CHECKER`.
     * Super Admin cannot create `AUDITOR`.
     * Existing Admin/Maker/Checker/Auditor behavior remains unchanged.
     * Unauthorized API requests are rejected server-side.
   * Follow the existing SQLite in-memory test setup and patching conventions described in `AGENTS.md`.

10. **Regression and security validation**

    * Verify that the change does not bypass existing RBAC middleware or permission checks.
    * Inspect `ROUTE_PERMISSION_MAP` and update it only if required by the implementation.
    * Ensure existing authentication mechanisms, including Azure AD/JIT provisioning, continue to work.
    * Do not expose credentials, secrets, or sensitive configuration in source code, logs, tests, or responses.
    * Do not commit `.env` or any secret values.

### Implementation constraints

* **First inspect `AGENTS.md` and the existing codebase.**
* Reuse existing models, services, dependencies, RBAC, audit, migration, and seed patterns.
* Do not create duplicate authentication or authorization logic.
* Do not redesign the RBAC system.
* Do not make unrelated changes.
* Prefer minimal, maintainable, production-grade changes.
* Preserve backward compatibility with existing users and roles.

### Expected outcome

After implementation:

* `roles` contains a single `SUPERADMIN` role.
* `users` contains a single default `superadmin` user linked to `SUPERADMIN`.
* `SUPERADMIN` has full system access through the existing RBAC architecture.
* `SUPERADMIN` can create **ADMIN users only**.
* Attempts by `SUPERADMIN` to create other roles are rejected server-side.
* Existing roles and users continue to function without regression.
* Seed execution is safe to run repeatedly.
* All relevant actions remain covered by the existing audit mechanism.
* Database migrations and automated tests are updated as required.

Before finalizing, review the complete diff and verify that every change is directly related to this requirement. Report the files changed, migration/seed impact, authorization behavior, tests added/updated, and any assumptions discovered from the existing codebase.
