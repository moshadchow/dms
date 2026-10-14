You are a Principal Software Architect and Senior Backend Engineer with extensive expertise in Microsoft Azure Active Directory (Microsoft Entra ID), OAuth 2.0, OpenID Connect (OIDC), JWT authentication, FastAPI, PostgreSQL, enterprise identity management, and production-grade security architecture.

Before making any changes, thoroughly analyse the existing authentication architecture and understand the current codebase. Follow the project's `AGENTS.md` guidelines, coding standards, architectural patterns, service/repository structure, API conventions, security practices, and database design principles. Reuse existing components wherever possible and minimise breaking changes.

Your objective is to **extend** the current authentication system by adding **Azure Active Directory (Microsoft Entra ID) Single Sign-On (SSO)** as an additional authentication provider while preserving the existing local email/password authentication.

Do NOT replace the current authentication mechanism.

Both authentication methods must coexist and be fully supported.

Do not generate implementation code.

Produce a complete production-grade architecture, implementation strategy, migration plan, database impact analysis, API impact analysis, security design, testing strategy, and deployment plan.

# Current System

The existing DMS uses:

Authentication

- Local Email
- Password
- JWT Authentication
- PostgreSQL User Table

Authorization

- Existing Role-Based Access Control (RBAC)

Roles include:

- View
- Create
- Update
- Delete
- Download

Administrators currently manage:

- Users
- Passwords
- Roles
- User Levels
- Account Status

The existing RBAC implementation must remain unchanged.

# Target Objective

Support two authentication methods simultaneously.

Users may authenticate using either:

1. Local Email + Password

OR

2. Azure AD (Microsoft Entra ID) Single Sign-On

Both authentication methods must authenticate into the same DMS user account.

Authentication changes.

Authorization remains unchanged.

# Authentication Flow

Support the following login options:

```
                    Login Screen

        Local Login        Azure AD Login
              │                  │
              ▼                  ▼
      Email + Password     Microsoft Entra ID
              │                  │
              ▼                  ▼
        Local Auth        OIDC Authorization
              │                  │
              └──────────┬───────┘
                         ▼
              Local User Resolution
                         ▼
               Existing RBAC Roles
                         ▼
                 DMS Application
```

The user experience should allow the user to choose either login method.

# Azure AD Integration

Implement Azure AD authentication using:

- OAuth 2.0
- OpenID Connect
- Authorization Code Flow
- PKCE
- Microsoft Identity Platform
- Enterprise Application Best Practices

The application should support:

- ID Token validation
- Access Token validation (where required)
- Refresh Tokens
- Logout
- Silent Login
- Token Expiration
- Session Expiration

# User Provisioning Strategy

Implement **Just-in-Time (JIT) User Provisioning**.

Use the following behaviour.

Example:

Azure AD

```
Object ID
89b7...1234

Email
john@company.com

Display Name
John Smith
```

Existing Local Database

```
Email
john@company.com

Role
Admin
```

First Azure Login

```
Authenticate with Azure AD
        ↓
Find local user using Email
        ↓
If found
        ↓
Store Azure Object ID
Store Authentication Provider
Update Last Login
        ↓
Continue Existing RBAC
```

Subsequent Azure Logins

```
Authenticate Azure AD
        ↓
Find user using Azure Object ID
        ↓
Load Existing Roles
        ↓
Continue
```

Advantages

- No bulk migration
- No duplicate accounts
- Existing users continue working
- Existing permissions remain unchanged
- Azure identity becomes the trusted identity after first successful login

# User Mapping Strategy

Design a reliable user linking strategy.

Evaluate:

- Azure Object ID
- Email Address
- User Principal Name (UPN)
- Employee ID
- Immutable ID

Recommend the most secure and maintainable approach.

The preferred flow should be:

First Login

Match using verified email.

Future Logins

Match using Azure Object ID.

Explain why.

# Database Impact

Analyse the existing users table.

Determine:

Which existing columns remain.

Which columns become optional.

Which new columns should be added.

Consider adding fields such as:

- auth_provider
- azure_object_id
- azure_tenant_id
- azure_upn
- azure_display_name
- azure_last_login_at
- last_synced_at

Password hashes should remain for users who continue using local authentication.

Do not remove support for local login.

# Authentication Provider

Support multiple authentication providers.

Example

```
Local
AzureAD
```

Users authenticated via Azure AD should still use the existing RBAC system.

# RBAC Preservation

The existing RBAC implementation must remain unchanged.

Current permissions:

- View
- Create
- Update
- Delete
- Download

must continue to function exactly as today.

Authentication identifies the user.

RBAC authorises the user.

No permission logic should require modification.

# Existing APIs

Existing protected APIs should continue working.

Determine whether the application should:

Option A

Continue issuing the application's own JWT after successful Azure authentication.

OR

Option B

Use Azure-issued access tokens throughout the application.

Compare both approaches.

Recommend the best production architecture.

Explain why.

The recommended solution should minimise changes to the existing API layer.

# Login Screen

Design the updated login page.

Support:

```
Email

Password

[ Login ]

---------------------

Sign in with Microsoft
```

Both options should coexist.

# Account Linking Rules

Scenario 1

Local account exists.

Azure account has the same verified email.

Automatically link.

Scenario 2

No local account exists.

Automatically create a local account using JIT provisioning.

Populate:

- Name
- Email
- Azure Object ID
- Authentication Provider

Assign the default application role according to existing business rules.

Scenario 3

Azure Object ID already linked.

Authenticate immediately.

Scenario 4

Email mismatch.

Reject login.

Log security event.

# Administration

Determine how the existing User Management module should change.

Current features:

- Create User
- Reset Password
- Assign Roles
- Enable
- Disable

Determine:

Which features remain.

Which become optional.

How Azure-linked users should be displayed.

Whether administrators can unlink Azure identities.

Whether authentication provider should be visible.

# Security

Design production-grade security covering:

- Token Validation
- Issuer Validation
- Audience Validation
- Tenant Validation
- PKCE
- Nonce
- State Validation
- Replay Protection
- CSRF Protection
- Clock Skew
- Refresh Token Security
- Secure Cookie Strategy
- Session Management
- Logout
- Revocation
- Secret Management
- Certificate Rotation

Follow Microsoft recommended practices.

# Logging & Auditing

Audit:

- Local Login
- Azure Login
- Failed Login
- User Linking
- First JIT Provisioning
- Token Validation Failure
- Account Lock
- Suspicious Login
- Tenant Mismatch
- Mapping Failure

# Migration Strategy

Produce a phased migration plan.

Include:

Phase 1

Azure App Registration

Phase 2

Environment Configuration

Phase 3

Database Migration

Phase 4

JIT User Linking

Phase 5

Pilot Rollout

Phase 6

Production Rollout

Phase 7

Rollback Strategy

No downtime should be required.

# Error Handling

Design handling for:

- Azure Authentication Failure
- Network Failure
- Invalid Tenant
- Expired Token
- Invalid Signature
- User Not Found
- Email Mismatch
- Duplicate Mapping
- Account Disabled
- Consent Failure
- Azure Service Unavailable

# Testing Strategy

Produce a comprehensive production testing strategy covering:

Authentication

- Local Login
- Azure Login
- JIT Provisioning
- Existing User Linking
- New User Creation
- Logout
- Refresh Tokens

Authorisation

- Existing RBAC
- Role Resolution
- API Access
- Permission Validation

Security

- Token Validation
- Replay Protection
- PKCE
- CSRF
- Session Timeout

Regression

- Existing Local Authentication
- Existing APIs
- Existing Role Management
- Existing User Management
- Existing Business Logic

# Constraints

- Read and strictly follow `AGENTS.md`.
- Authentication must support both Local and Azure AD simultaneously.
- Existing users must continue to authenticate locally.
- Existing RBAC implementation must remain unchanged.
- Existing APIs should require minimal modification.
- Minimise database changes.
- Use Just-in-Time (JIT) User Provisioning.
- Automatically link existing users by verified email on first Azure login.
- Future Azure logins must use Azure Object ID.
- Follow Microsoft enterprise identity best practices.
- Do not introduce breaking changes.
- Design for scalability, maintainability, auditability, and enterprise security.

# Deliverables

Produce a comprehensive implementation document containing:

1. Current Authentication Architecture Analysis.
2. Target Authentication Architecture.
3. Azure AD Integration Design.
4. End-to-End Authentication Flow.
5. JIT User Provisioning Design.
6. User Linking Strategy.
7. Database Impact Analysis.
8. API Impact Analysis.
9. Login UI Changes.
10. Security Architecture.
11. Session Management Strategy.
12. JWT Strategy Recommendation.
13. User Management Impact.
14. Migration Strategy.
15. Rollback Plan.
16. Risk Assessment.
17. Production Deployment Checklist.
18. Testing Strategy.
19. Best Practices.
20. Explanation of how Azure AD authentication integrates seamlessly with the existing DMS while preserving the current RBAC model and minimising changes to the application.