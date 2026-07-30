"""Tests for Azure AD authentication."""

import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone
from sqlmodel import select

from sqlmodel import Session

from auth.azure_service import (
    generate_pkce_pair,
    generate_state,
    generate_nonce,
    resolve_azure_user,
)
from users.models import AuthProvider, User, Role, RoleName, UserRoleLink


# ── PKCE / State / Nonce generation ──────────────

class TestPkceGeneration:
    def test_generate_pkce_pair_returns_two_strings(self):
        verifier, challenge = generate_pkce_pair()
        assert isinstance(verifier, str)
        assert isinstance(challenge, str)
        assert len(verifier) > 40
        assert len(challenge) > 40

    def test_pkce_challenge_is_base64url(self):
        _, challenge = generate_pkce_pair()
        import base64
        # Should not raise
        decoded = base64.urlsafe_b64decode(challenge + "==")
        assert len(decoded) == 32  # SHA-256 produces 32 bytes

    def test_pkce_pair_is_deterministic_from_same_random(self):
        v1, c1 = generate_pkce_pair()
        v2, c2 = generate_pkce_pair()
        # Different each time (randomness)
        assert v1 != v2
        assert c1 != c2


class TestStateAndNonce:
    def test_generate_state_is_url_safe(self):
        state = generate_state()
        assert isinstance(state, str)
        assert len(state) > 20
        # Should be URL-safe base64
        import re
        assert re.match(r'^[A-Za-z0-9_-]+$', state)

    def test_generate_nonce_is_unique(self):
        n1 = generate_nonce()
        n2 = generate_nonce()
        assert n1 != n2


# ── Azure config endpoint ────────────────────────

class TestAzureConfigEndpoint:
    def test_azure_config_returns_enabled_false_when_not_configured(self, client, monkeypatch):
        test_client, _, _ = client
        monkeypatch.setattr("auth.router.settings", type("S", (), {
            "AZURE_CLIENT_ID": "",
            "AZURE_CLIENT_SECRET": "",
            "AZURE_TENANT_ID": "",
            "AZURE_ENABLED": False,
        })())

        resp = test_client.get("/api/v1/auth/azure/config")
        assert resp.status_code == 200
        assert resp.json() == {"enabled": False}

    def test_azure_config_returns_enabled_true_when_configured(self, client, monkeypatch):
        test_client, _, _ = client
        monkeypatch.setattr("auth.router.settings", type("S", (), {
            "AZURE_CLIENT_ID": "test-client-id",
            "AZURE_CLIENT_SECRET": "test-secret",
            "AZURE_TENANT_ID": "test-tenant-id",
            "AZURE_ENABLED": True,
        })())

        resp = test_client.get("/api/v1/auth/azure/config")
        assert resp.status_code == 200
        assert resp.json() == {"enabled": True}


# ── Azure login redirect ─────────────────────────

class TestAzureLoginRedirect:
    def test_azure_login_returns_503_when_not_configured(self, client, monkeypatch):
        test_client, _, _ = client
        # Patch the router's imported settings reference
        monkeypatch.setattr("auth.router.settings", type("S", (), {
            "AZURE_ENABLED": False,
        })())

        resp = test_client.get("/api/v1/auth/azure/login", follow_redirects=False)
        assert resp.status_code == 503

    def test_azure_login_redirects_to_microsoft(self, client, monkeypatch):
        test_client, _, _ = client
        mock_settings = type("S", (), {
            "AZURE_ENABLED": True,
            "AZURE_CLIENT_ID": "test-client-id",
            "AZURE_TENANT_ID": "test-tenant-id",
            "AZURE_SCOPES": ["openid", "profile", "email"],
            "AZURE_REDIRECT_URI": "http://localhost:8000/api/v1/auth/azure/callback",
        })()
        monkeypatch.setattr("auth.router.settings", mock_settings)
        monkeypatch.setattr("auth.azure_service.settings", mock_settings)

        resp = test_client.get("/api/v1/auth/azure/login", follow_redirects=False)
        assert resp.status_code == 302
        assert "login.microsoftonline.com" in resp.headers["location"]
        assert "test-client-id" in resp.headers["location"]
        assert "code_challenge" in resp.headers["location"]
        assert "state=" in resp.headers["location"]


# ── User resolution / JIT provisioning ───────────

class TestAzureUserResolution:
    def _make_claims(self, oid="test-oid-123", email="user@company.com", name="Test User", tid="test-tenant"):
        return {
            "oid": oid,
            "email": email,
            "name": name,
            "tid": tid,
        }

    def test_resolve_existing_azure_linked_user(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            # Create an auditor role for testing
            auditor_role = session.exec(
                select(Role).where(Role.name == RoleName.AUDITOR)
            ).first()
            if not auditor_role:
                auditor_role = Role(name=RoleName.AUDITOR, description="Auditor")
                session.add(auditor_role)
                session.flush()

            # Create a user already linked to Azure
            user = User(
                full_name="Azure User",
                email="azure@example.com",
                is_active=True,
                auth_provider=AuthProvider.AZURE_AD.value,
                azure_object_id="existing-azure-oid",
                azure_tenant_id="test-tenant",
            )
            session.add(user)
            session.flush()
            session.commit()

            claims = self._make_claims(oid="existing-azure-oid", email="azure@example.com")
            resolved = resolve_azure_user(session, claims)

            assert resolved.id == user.id
            assert resolved.azure_object_id == "existing-azure-oid"
            assert resolved.azure_last_login_at is not None

    def test_resolve_local_user_links_azure_identity(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            # Get the admin user from seeded data
            from sqlmodel import select
            admin = session.exec(
                select(User).where(User.email == "admin@example.com")
            ).first()
            assert admin is not None

            claims = self._make_claims(oid="new-azure-oid", email="admin@example.com")
            resolved = resolve_azure_user(session, claims)

            assert resolved.id == admin.id
            assert resolved.azure_object_id == "new-azure-oid"
            assert resolved.auth_provider == AuthProvider.AZURE_AD.value

    def test_jit_provision_new_user(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            # Ensure auditor role exists (resolve_azure_user falls back to it)
            auditor = session.exec(select(Role).where(Role.name == RoleName.AUDITOR)).first()
            if not auditor:
                auditor = Role(name=RoleName.AUDITOR, description="Auditor")
                session.add(auditor)
                session.flush()

            claims = self._make_claims(
                oid="brand-new-oid",
                email="newuser@company.com",
                name="New User",
            )
            resolved = resolve_azure_user(session, claims)

            assert resolved.email == "newuser@company.com"
            assert resolved.full_name == "New User"
            assert resolved.auth_provider == AuthProvider.AZURE_AD.value
            assert resolved.azure_object_id == "brand-new-oid"
            assert resolved.hashed_password is None
            assert resolved.is_active is True
            # Should have a role assigned (auditor fallback)
            assert len(resolved.roles) > 0

    def test_reject_inactive_user(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            # Create an inactive user with matching email
            user = User(
                full_name="Inactive User",
                email="inactive@example.com",
                hashed_password="fake-hash",
                is_active=False,
            )
            session.add(user)
            session.flush()
            session.commit()

            claims = self._make_claims(oid="some-oid", email="inactive@example.com")
            with pytest.raises(Exception) as exc_info:
                resolve_azure_user(session, claims)
            assert "inactive" in str(exc_info.value).lower()

    def test_reject_missing_oid(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            claims = {"email": "user@company.com", "name": "User"}
            with pytest.raises(Exception) as exc_info:
                resolve_azure_user(session, claims)
            assert "oid" in str(exc_info.value).lower()

    def test_reject_missing_email(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            claims = {"oid": "some-oid", "name": "User"}
            with pytest.raises(Exception) as exc_info:
                resolve_azure_user(session, claims)
            assert "email" in str(exc_info.value).lower()


# ── Existing local login still works ─────────────

class TestLocalLoginRegression:
    def test_local_login_still_works(self, seeded_data, client):
        test_client, _, _ = client
        resp = test_client.post("/api/v1/auth/login", json={
            "email": "admin@example.com",
            "password": "Admin@1234",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_local_login_rejects_wrong_password(self, seeded_data, client):
        test_client, _, _ = client
        resp = test_client.post("/api/v1/auth/login", json={
            "email": "admin@example.com",
            "password": "WrongPassword",
        })
        assert resp.status_code == 401

    def test_local_login_rejects_azure_only_user(self, seeded_data, client):
        """A user created via JIT (no password) should not be able to login via local auth."""
        _, engine, _ = client
        with Session(engine) as session:
            user = User(
                full_name="Azure Only",
                email="azureonly@example.com",
                is_active=True,
                auth_provider=AuthProvider.AZURE_AD.value,
                azure_object_id="azure-only-oid",
            )
            session.add(user)
            session.commit()

        test_client, _, _ = client
        resp = test_client.post("/api/v1/auth/login", json={
            "email": "azureonly@example.com",
            "password": "anything",
        })
        assert resp.status_code == 401
