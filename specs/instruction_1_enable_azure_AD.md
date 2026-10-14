# When "Sign in with Microsoft" Button Is Shown

The visibility of the **"Sign in with Microsoft"** button is controlled by the `AZURE_ENABLED` property in `core/config.py`.

```python
@property
def AZURE_ENABLED(self) -> bool:
    return bool(
        self.AZURE_CLIENT_ID
        and self.AZURE_CLIENT_SECRET
        and self.AZURE_TENANT_ID
    )
```

The button is displayed **only when all three Azure configuration values are present**.

## Required Environment Variables

| Environment Variable | Where to Configure | Example Value |
|----------------------|-------------------|---------------|
| `AZURE_CLIENT_ID` | `.env` file | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| `AZURE_CLIENT_SECRET` | `.env` file | `~abc123...` *(generated from Azure App Registration)* |
| `AZURE_TENANT_ID` | `.env` file | `11111111-2222-3333-4444-555555555555` |

---

# End-to-End Flow

## 1. Backend

The endpoint:

```http
GET /api/v1/auth/azure/config
```

returns:

```json
{
  "enabled": true
}
```

or

```json
{
  "enabled": false
}
```

based on the value of:

```python
settings.AZURE_ENABLED
```

---

## 2. Frontend (`LoginPage.tsx`)

When the login page loads:

1. It sends a request to:

   ```http
   GET /api/v1/auth/azure/config
   ```

2. If the response is:

   ```json
   {
     "enabled": true
   }
   ```

   the page renders:

   - **Sign in with Microsoft** button
   - **"or"** divider between authentication methods

3. If the response is:

   ```json
   {
     "enabled": false
   }
   ```

   neither the Microsoft button nor the divider is rendered.

---

## 3. When Azure Is Not Configured

If **any one** of the following environment variables is missing or empty:

- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`
- `AZURE_TENANT_ID`

then:

- `AZURE_ENABLED` evaluates to `false`
- `GET /api/v1/auth/azure/config` returns:

  ```json
  {
    "enabled": false
  }
  ```

- The **"Sign in with Microsoft"** button is hidden.
- Calling:

  ```http
  GET /api/v1/auth/azure/login
  ```

  returns:

  ```http
  HTTP 503 Service Unavailable
  ```

---

# How to Enable Azure AD Authentication

## Step 1 — Create an Azure App Registration

In the **Microsoft Azure Portal**, create a new **App Registration**.

---

## Step 2 — Configure Environment Variables

Add the following values to your `.env` file:

```env
AZURE_CLIENT_ID=<your-app-client-id>
AZURE_CLIENT_SECRET=<your-client-secret>
AZURE_TENANT_ID=<your-tenant-id>
```

---

## Step 3 — Configure Redirect URI

Navigate to:

**Azure Portal → App Registration → Authentication**

Add the following Redirect URI:

```text
http://localhost:8000/api/v1/auth/azure/callback
```

Replace the hostname if your application is deployed to another environment.

---

## Step 4 — Restart the Backend

Restart the backend application so that the updated environment variables are loaded.

---

# How to Disable Azure AD Authentication

To disable Azure AD authentication, simply leave the following environment variables unset or empty:

- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`
- `AZURE_TENANT_ID`

When these values are not configured:

- Azure AD authentication is automatically disabled.
- The **"Sign in with Microsoft"** button is not displayed.
- Users can continue signing in using the existing local email/password authentication.
- The application defaults to the existing local authentication behaviour without requiring any code changes.