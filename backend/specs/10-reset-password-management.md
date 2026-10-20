# Prompt: Admin Password Reset

Act as a **Senior Frontend and Backend Engineer**.

Implement a secure **Admin Password Reset** feature.

## Requirements

- Admin can reset a user's password from the User Management section.
- When the Admin clicks **Reset Password**:
  1. Generate a secure random password.
  2. Update the user's password securely using the existing password hashing mechanism.
  3. Send the generated temporary password to the user's registered email address.
- The user can use the temporary password to log in.

## Workflow

```text
Admin
  ↓
Select User
  ↓
Click Reset Password
  ↓
Generate Random Password
  ↓
Hash & Update Password
  ↓
Send Temporary Password to User Email
  ↓
User Logs In Using New Password


## Security Requirements

Only authorized Admin users can reset passwords.
Generate passwords securely.
Never store passwords in plain text.
Do not log or expose the generated password through APIs or audit logs.
Send the password only to the user's registered email address.
Use the existing authentication, RBAC, email, and audit infrastructure.

## Frontend

Add a Reset Password action for Admin users.
Show a confirmation dialog before resetting the password.
Show appropriate success or error messages.

## Acceptance Criteria

Admin can reset a user's password.
A random password is generated securely.
The password is hashed before storing.
The temporary password is sent to the user's email.
The user can log in using the new password.
Existing authentication, RBAC, email, and user management functionality remains unchanged.

Follow the existing project architecture and AGENTS.md. Do not introduce duplicate password hashing, authentication, or email mechanisms.