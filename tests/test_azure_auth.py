"""Tests for company-scoped Azure AD authentication.

Covers: company config resolution (no global .env fallback), OAuth state /
company context integrity, token exchange and ID-token validation against the
selected company's tenant, JIT provisioning + cross-company isolation, and
guard tests proving the removed global settings no longer exist.
"""

import asyncio
import base64
import json
import pathlib
import re
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi import HTTPException
from jose import jwt as jose_jwt
from sqlmodel import Session, select

from auth import azure_service
from auth import router as auth_router
from auth.azure_service import (
    generate_nonce,
    generate_pkce_pair,
    generate_state,
    get_azure_config_for_company,
    resolve_azure_user,
    validate_id_token,
)
from core.config import settings
from users.models import AuthProvider, User


# ── Helpers ──────────────────────────────────────

def _configure_azure(
    test_client,
    auth_headers,
    company_id,
    *,
    client_id,
    tenant_id,
    secret="test-secret",
    enabled=True,
):
    """Set a company's Azure AD config through the real SUPERADMIN endpoint."""
    resp = test_client.put(
        f"/api/v1/companies/{company_id}/azure-config",
        json={
            "azure_client_id": client_id,
            "azure_tenant_id": tenant_id,
            "azure_client_secret": secret,
            "azure_enabled": enabled,
            "azure_default_role_name": "auditor",
        },
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _login_redirect(test_client, company_id=None):
    url = "/api/v1/auth/azure/login"
    if company_id is not None:
        url += f"?company_id={company_id}"
    return test_client.get(url, follow_redirects=False)


def _location_error(location: str) -> str:
    from urllib.parse import parse_qs, unquote, urlparse
    query = parse_qs(urlparse(location).query)
    return unquote(query.get("error", [""])[0])


def _assert_login_error(resp, expected_fragment=None):
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith(f"{settings.FRONTEND_URL}/login?error=")
    assert "microsoftonline.com" not in location
    if expected_fragment:
        assert expected_fragment.lower() in _location_error(location).lower()


def _state_from_location(location: str) -> str:
    from urllib.parse import parse_qs, urlparse
    return parse_qs(urlparse(location).query)["state"][0]


def _parse_authorize(location: str):
    """Split an Entra authorize redirect into (path, query params)."""
    from urllib.parse import parse_qs, urlparse
    parsed = urlparse(location)
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    return parsed, params


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
        decoded = base64.urlsafe_b64decode(challenge + "==")
        assert len(decoded) == 32  # SHA-256 produces 32 bytes

    def test_pkce_pair_is_random(self):
        v1, c1 = generate_pkce_pair()
        v2, c2 = generate_pkce_pair()
        assert v1 != v2
        assert c1 != c2


class TestStateAndNonce:
    def test_generate_state_is_url_safe(self):
        state = generate_state(generate_nonce(), company_id=7)
        assert isinstance(state, str)
        assert len(state) > 20
        assert re.match(r'^[A-Za-z0-9_-]+=*$', state)

    def test_generate_state_encodes_company_id(self):
        nonce = generate_nonce()
        state = generate_state(nonce, company_id=42)
        decoded = json.loads(base64.urlsafe_b64decode(state))
        assert decoded["cid"] == 42
        assert decoded["n"] == nonce

    def test_generate_state_requires_company_id(self):
        with pytest.raises(TypeError):
            generate_state(generate_nonce())

    def test_generate_nonce_is_unique(self):
        assert generate_nonce() != generate_nonce()


# ── Azure config discovery endpoint ──────────────

class TestAzureConfigEndpoint:
    def test_defaults_to_disabled_without_global_config(self, client):
        test_client, _, _ = client
        resp = test_client.get("/api/v1/auth/azure/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "global_enabled" not in data
        assert data["enabled"] is False
        assert data["companies"] == []

    def test_lists_only_active_fully_configured_companies(
        self, client, seeded_data, auth_headers
    ):
        test_client, _, _ = client
        company_id = seeded_data["company_id"]
        _configure_azure(
            test_client, auth_headers, company_id,
            client_id="cid-a", tenant_id="tid-a",
        )

        resp = test_client.get("/api/v1/auth/azure/config")
        data = resp.json()
        assert data["enabled"] is True
        assert [c["id"] for c in data["companies"]] == [company_id]
        # Login page needs id/name/short_name only — no secrets/config details
        company = data["companies"][0]
        assert set(company.keys()) == {"id", "name", "short_name"}

    def test_excludes_companies_without_azure_enabled(
        self, client, seeded_data, auth_headers
    ):
        test_client, _, _ = client
        company_id = seeded_data["company_id"]
        # Config written but never enabled
        _configure_azure(
            test_client, auth_headers, company_id,
            client_id="cid-a", tenant_id="tid-a", enabled=False,
        )

        data = test_client.get("/api/v1/auth/azure/config").json()
        assert data["enabled"] is False
        assert data["companies"] == []

    def test_excludes_deactivated_company(self, client, seeded_data, auth_headers):
        test_client, _, _ = client
        company_id = seeded_data["company_id"]
        _configure_azure(
            test_client, auth_headers, company_id,
            client_id="cid-a", tenant_id="tid-a",
        )
        test_client.patch(
            f"/api/v1/companies/{company_id}/deactivate",
            headers=auth_headers["superadmin"],
        )

        data = test_client.get("/api/v1/auth/azure/config").json()
        assert data["enabled"] is False
        assert data["companies"] == []

    def test_excludes_incomplete_config(self, client, seeded_data):
        test_client, engine, _ = client
        # Simulate legacy/partial data: enabled but missing client id
        with Session(engine) as session:
            from company_profile.models import Company
            company = session.get(Company, seeded_data["company_id"])
            company.azure_enabled = True
            company.azure_client_id = None
            company.azure_tenant_id = "tid-x"
            session.add(company)
            session.commit()

        data = test_client.get("/api/v1/auth/azure/config").json()
        assert data["enabled"] is False
        assert data["companies"] == []


# ── Azure login redirect (company context first) ─

class TestAzureLoginRedirect:
    def test_missing_company_id_is_rejected(self, client):
        test_client, _, _ = client
        resp = _login_redirect(test_client)
        _assert_login_error(resp, "Company selection is required")

    def test_unknown_company_is_rejected(self, client):
        test_client, _, _ = client
        resp = _login_redirect(test_client, company_id=999999)
        _assert_login_error(resp, "not valid")

    def test_company_without_azure_config_is_rejected(
        self, client, seeded_data, auth_headers
    ):
        test_client, _, _ = client
        resp = _login_redirect(test_client, company_id=seeded_data["company_id"])
        _assert_login_error(resp, "not configured")

    def test_disabled_azure_config_is_rejected(
        self, client, seeded_data, auth_headers
    ):
        test_client, _, _ = client
        company_id = seeded_data["company_id"]
        _configure_azure(
            test_client, auth_headers, company_id,
            client_id="cid-a", tenant_id="tid-a", enabled=False,
        )
        resp = _login_redirect(test_client, company_id=company_id)
        _assert_login_error(resp, "not configured")

    def test_deactivated_company_is_rejected(
        self, client, seeded_data, auth_headers
    ):
        test_client, _, _ = client
        company_id = seeded_data["company_id"]
        _configure_azure(
            test_client, auth_headers, company_id,
            client_id="cid-a", tenant_id="tid-a",
        )
        test_client.patch(
            f"/api/v1/companies/{company_id}/deactivate",
            headers=auth_headers["superadmin"],
        )
        resp = _login_redirect(test_client, company_id=company_id)
        _assert_login_error(resp, "not available")

    def test_valid_company_redirects_to_its_tenant(
        self, client, seeded_data, auth_headers
    ):
        test_client, _, _ = client
        company_id = seeded_data["company_id"]
        _configure_azure(
            test_client, auth_headers, company_id,
            client_id="cid-a", tenant_id="tenant-a",
        )

        resp = _login_redirect(test_client, company_id=company_id)
        assert resp.status_code == 302
        location = resp.headers["location"]
        parsed, params = _parse_authorize(location)
        assert parsed.netloc == "login.microsoftonline.com"
        assert parsed.path.startswith("/tenant-a/oauth2/v2.0/authorize")
        assert params["client_id"] == "cid-a"
        assert "code_challenge" in params
        assert "state" in params
        assert params["scope"] == "openid profile email"

        # The validated company context is stored server-side, keyed by state
        assert auth_router._pending_auth[params["state"]]["company_id"] == company_id

    def test_two_companies_use_their_own_configuration(
        self, client, seeded_data, auth_headers
    ):
        test_client, _, _ = client
        company_a = seeded_data["company_id"]
        company_b = seeded_data["other_company_id"]
        _configure_azure(
            test_client, auth_headers, company_a,
            client_id="cid-a", tenant_id="tenant-a", secret="secret-a",
        )
        _configure_azure(
            test_client, auth_headers, company_b,
            client_id="cid-b", tenant_id="tenant-b", secret="secret-b",
        )

        location_a = _login_redirect(test_client, company_id=company_a).headers["location"]
        location_b = _login_redirect(test_client, company_id=company_b).headers["location"]

        parsed_a, params_a = _parse_authorize(location_a)
        parsed_b, params_b = _parse_authorize(location_b)

        # Each company authenticates against its own tenant with its own client
        assert parsed_a.path.startswith("/tenant-a/")
        assert params_a["client_id"] == "cid-a"
        assert parsed_b.path.startswith("/tenant-b/")
        assert params_b["client_id"] == "cid-b"

        assert auth_router._pending_auth[params_a["state"]]["company_id"] == company_a
        assert auth_router._pending_auth[params_b["state"]]["company_id"] == company_b


# ── Callback state integrity ─────────────────────

class TestCallbackStateIntegrity:
    def test_tampered_state_is_rejected(self, client, seeded_data, auth_headers):
        test_client, _, _ = client
        company_id = seeded_data["company_id"]
        _configure_azure(
            test_client, auth_headers, company_id,
            client_id="cid-a", tenant_id="tenant-a",
        )
        state = _state_from_location(
            _login_redirect(test_client, company_id=company_id).headers["location"]
        )

        # Rewrite the company inside the state — it no longer matches the
        # server-side pending entry and must be refused.
        payload = json.loads(base64.urlsafe_b64decode(state))
        payload["cid"] = seeded_data["other_company_id"]
        tampered = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode()
        ).decode()

        resp = test_client.get(
            f"/api/v1/auth/azure/callback?code=abc&state={tampered}",
            follow_redirects=False,
        )
        _assert_login_error(resp, "Invalid state")

    def test_unknown_state_is_rejected(self, client):
        test_client, _, _ = client
        resp = test_client.get(
            "/api/v1/auth/azure/callback?code=abc&state=not-a-real-state",
            follow_redirects=False,
        )
        _assert_login_error(resp, "Invalid state")

    def test_state_is_single_use(self, client, seeded_data, auth_headers):
        test_client, _, _ = client
        company_id = seeded_data["company_id"]
        _configure_azure(
            test_client, auth_headers, company_id,
            client_id="cid-a", tenant_id="tenant-a",
        )
        state = _state_from_location(
            _login_redirect(test_client, company_id=company_id).headers["location"]
        )

        first = test_client.get(
            f"/api/v1/auth/azure/callback?state={state}",  # no code
            follow_redirects=False,
        )
        _assert_login_error(first, "Missing authorization code")

        # The entry was consumed — replaying the same state must fail
        second = test_client.get(
            f"/api/v1/auth/azure/callback?code=abc&state={state}",
            follow_redirects=False,
        )
        _assert_login_error(second, "Invalid state")


# ── Config resolution (DB is the only source) ────

class TestCompanyConfigResolution:
    def test_returns_company_configuration(self, client, seeded_data, auth_headers):
        test_client, engine, _ = client
        company_id = seeded_data["company_id"]
        _configure_azure(
            test_client, auth_headers, company_id,
            client_id="cid-a", tenant_id="tenant-a", secret="super-secret",
        )

        with Session(engine) as session:
            config = get_azure_config_for_company(session, company_id)

        assert config["client_id"] == "cid-a"
        assert config["tenant_id"] == "tenant-a"
        assert config["client_secret"] == "super-secret"
        assert config["company_id"] == company_id
        assert config["redirect_uri"] == settings.AZURE_REDIRECT_URI
        assert config["scopes"] == ["openid", "profile", "email"]
        assert config["default_role_name"] == "auditor"

    def test_missing_company_id_raises(self, client):
        _, engine, _ = client
        with Session(engine) as session:
            with pytest.raises(HTTPException) as exc:
                get_azure_config_for_company(session, None)
        assert exc.value.status_code == 400

    def test_unknown_company_raises(self, client):
        _, engine, _ = client
        with Session(engine) as session:
            with pytest.raises(HTTPException) as exc:
                get_azure_config_for_company(session, 999999)
        assert exc.value.status_code == 404

    def test_company_without_config_raises(self, client, seeded_data):
        _, engine, _ = client
        with Session(engine) as session:
            with pytest.raises(HTTPException) as exc:
                get_azure_config_for_company(session, seeded_data["company_id"])
        assert exc.value.status_code == 503
        # User-safe message: no secrets, no tenant/client identifiers
        assert "not configured" in exc.value.detail

    def test_never_falls_back_to_global_env(
        self, client, seeded_data, auth_headers
    ):
        """Even with config env vars present, an unconfigured company stays unconfigured."""
        import os
        from core.config import Settings

        test_client, engine, _ = client
        env = {
            "AZURE_CLIENT_ID": "global-client",
            "AZURE_CLIENT_SECRET": "global-secret",
            "AZURE_TENANT_ID": "global-tenant",
        }
        with patch.dict(os.environ, env):
            assert "AZURE_CLIENT_ID" not in Settings.model_fields
            fresh = Settings(_env_file=None)
            assert not hasattr(fresh, "AZURE_CLIENT_ID")

            with Session(engine) as session:
                with pytest.raises(HTTPException) as exc:
                    get_azure_config_for_company(
                        session, seeded_data["company_id"]
                    )
        assert exc.value.status_code == 503


# ── Token exchange uses the company credentials ──

class _FakeAsyncClient:
    """Captures the token-exchange request instead of calling Microsoft."""

    captured: dict = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, data=None, **kwargs):
        type(self).captured = {"url": url, "data": data}

        class _Resp:
            status_code = 200

            def json(self):
                return {"id_token": "fake-token"}

        return _Resp()


class TestTokenExchangeUsesCompanyConfig:
    def test_uses_company_client_secret_and_tenant(
        self, client, seeded_data, auth_headers
    ):
        from auth.azure_service import exchange_code_for_tokens

        test_client, engine, _ = client
        company_id = seeded_data["company_id"]
        _configure_azure(
            test_client, auth_headers, company_id,
            client_id="cid-a", tenant_id="tenant-a", secret="secret-a",
        )

        with Session(engine) as session:
            config = get_azure_config_for_company(session, company_id)

        with patch(
            "auth.azure_service.httpx.AsyncClient", _FakeAsyncClient
        ):
            asyncio.run(
                exchange_code_for_tokens("auth-code", "pkce-verifier", config)
            )

        captured = _FakeAsyncClient.captured
        assert (
            captured["url"]
            == "https://login.microsoftonline.com/tenant-a/oauth2/v2.0/token"
        )
        assert captured["data"]["client_id"] == "cid-a"
        assert captured["data"]["client_secret"] == "secret-a"
        assert captured["data"]["code"] == "auth-code"
        assert captured["data"]["code_verifier"] == "pkce-verifier"
        assert captured["data"]["redirect_uri"] == settings.AZURE_REDIRECT_URI
        # No trace of any global environment credential
        assert "global-client" not in str(captured)


# ── ID token validation against the company tenant ─

def _b64url_uint(value: int) -> str:
    length = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(length, "big")).rstrip(b"=").decode()


def _make_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _public_jwk(key, kid: str) -> dict:
    numbers = key.public_key().public_numbers()
    return {
        "kid": kid,
        "kty": "RSA",
        "n": _b64url_uint(numbers.n),
        "e": _b64url_uint(numbers.e),
    }


def _x5c_jwk(key, kid: str) -> dict:
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "dms-test")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    der = cert.public_bytes(serialization.Encoding.DER)
    return {"kid": kid, "kty": "RSA", "x5c": [base64.b64encode(der).decode()]}


def _sign_token(key, claims: dict, kid: str) -> str:
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return jose_jwt.encode(claims, pem, algorithm="RS256", headers={"kid": kid})


def _claims(tenant="tenant-a", audience="cid-a", nonce="nonce-1", **overrides):
    now = int(time.time())
    claims = {
        "iss": f"https://login.microsoftonline.com/{tenant}/v2.0",
        "aud": audience,
        "sub": "subject-1",
        "oid": "oid-1",
        "email": "user@company-a.com",
        "name": "User",
        "tid": tenant,
        "nonce": nonce,
        "iat": now - 60,
        "nbf": now - 60,
        "exp": now + 300,
    }
    claims.update(overrides)
    return claims


def _validate(token, nonce, tenant="tenant-a", client_id="cid-a"):
    config = {
        "client_id": client_id,
        "client_secret": "s",
        "tenant_id": tenant,
        "redirect_uri": settings.AZURE_REDIRECT_URI,
        "scopes": ["openid"],
        "default_role_name": "auditor",
        "company_id": 1,
    }
    return asyncio.run(validate_id_token(token, nonce, config))


class TestIdTokenValidation:
    def test_valid_token_for_company_tenant_is_accepted(self):
        key = _make_key()
        token = _sign_token(key, _claims(), kid="kid-a")
        with patch.object(
            azure_service, "_get_signing_keys", AsyncMock(return_value=[_public_jwk(key, "kid-a")])
        ):
            claims = _validate(token, "nonce-1")
        assert claims["oid"] == "oid-1"

    def test_wrong_tenant_issuer_is_rejected(self):
        key = _make_key()
        token = _sign_token(key, _claims(tenant="tenant-b"), kid="kid-a")
        with patch.object(
            azure_service, "_get_signing_keys", AsyncMock(return_value=[_public_jwk(key, "kid-a")])
        ):
            with pytest.raises(HTTPException) as exc:
                _validate(token, "nonce-1", tenant="tenant-a")
        assert exc.value.status_code == 401

    def test_wrong_audience_is_rejected(self):
        key = _make_key()
        token = _sign_token(key, _claims(audience="cid-other"), kid="kid-a")
        with patch.object(
            azure_service, "_get_signing_keys", AsyncMock(return_value=[_public_jwk(key, "kid-a")])
        ):
            with pytest.raises(HTTPException) as exc:
                _validate(token, "nonce-1", tenant="tenant-a", client_id="cid-a")
        assert exc.value.status_code == 401

    def test_wrong_nonce_is_rejected(self):
        key = _make_key()
        token = _sign_token(key, _claims(nonce="other-nonce"), kid="kid-a")
        with patch.object(
            azure_service, "_get_signing_keys", AsyncMock(return_value=[_public_jwk(key, "kid-a")])
        ):
            with pytest.raises(HTTPException) as exc:
                _validate(token, "nonce-1")
        assert exc.value.status_code == 401

    def test_tampered_signature_is_rejected(self):
        key = _make_key()
        other_key = _make_key()
        token = _sign_token(other_key, _claims(), kid="kid-a")
        with patch.object(
            azure_service, "_get_signing_keys", AsyncMock(return_value=[_public_jwk(key, "kid-a")])
        ):
            with pytest.raises(HTTPException) as exc:
                _validate(token, "nonce-1")
        assert exc.value.status_code == 401

    def test_x5c_certificate_key_is_supported(self):
        """Azure signs with x5c certificate chains — that path must keep working."""
        key = _make_key()
        token = _sign_token(key, _claims(), kid="kid-x5c")
        with patch.object(
            azure_service, "_get_signing_keys", AsyncMock(return_value=[_x5c_jwk(key, "kid-x5c")])
        ):
            claims = _validate(token, "nonce-1")
        assert claims["oid"] == "oid-1"


# ── User resolution / JIT provisioning ───────────

class TestAzureUserResolution:
    def _make_claims(
        self,
        oid="test-oid-123",
        email="user@company.com",
        name="Test User",
        tid="tenant-a",
    ):
        return {"oid": oid, "email": email, "name": name, "tid": tid}

    def test_resolve_existing_azure_linked_user(
        self, seeded_data, client
    ):
        _, engine, _ = client
        company_id = seeded_data["company_id"]
        with Session(engine) as session:
            user = User(
                full_name="Azure User",
                email="azure@example.com",
                is_active=True,
                auth_provider=AuthProvider.AZURE_AD.value,
                azure_object_id="existing-azure-oid",
                azure_tenant_id="tenant-a",
                company_id=company_id,
            )
            session.add(user)
            session.commit()

            resolved = resolve_azure_user(
                session, self._make_claims(oid="existing-azure-oid"), company_id
            )

            assert resolved.id == user.id
            assert resolved.company_id == company_id
            assert resolved.azure_last_login_at is not None

    def test_existing_user_of_other_company_is_rejected(
        self, seeded_data, client
    ):
        _, engine, _ = client
        company_a = seeded_data["company_id"]
        company_b = seeded_data["other_company_id"]
        with Session(engine) as session:
            user = User(
                full_name="Other Company User",
                email="elsewhere@example.com",
                is_active=True,
                auth_provider=AuthProvider.AZURE_AD.value,
                azure_object_id="other-co-oid",
                company_id=company_b,
            )
            session.add(user)
            session.commit()
            user_id = user.id

            with pytest.raises(HTTPException) as exc:
                resolve_azure_user(
                    session, self._make_claims(oid="other-co-oid"), company_a
                )
            assert exc.value.status_code == 403

            # Not silently moved between companies
            session.expire_all()
            unchanged = session.get(User, user_id)
            assert unchanged.company_id == company_b

    def test_email_match_same_company_links_identity(
        self, seeded_data, client
    ):
        _, engine, _ = client
        company_id = seeded_data["company_id"]
        with Session(engine) as session:
            # Seeded admin belongs to the test company
            admin = session.exec(
                select(User).where(User.email == "admin@example.com")
            ).first()
            assert admin.company_id == company_id

            resolved = resolve_azure_user(
                session,
                self._make_claims(oid="new-azure-oid", email="admin@example.com"),
                company_id,
            )

            assert resolved.id == admin.id
            assert resolved.azure_object_id == "new-azure-oid"
            assert resolved.auth_provider == AuthProvider.AZURE_AD.value

    def test_email_match_other_company_is_rejected_and_not_linked(
        self, seeded_data, client
    ):
        _, engine, _ = client
        company_a = seeded_data["company_id"]
        with Session(engine) as session:
            other_admin = session.exec(
                select(User).where(User.email == "other_admin@example.com")
            ).first()
            assert other_admin.company_id == seeded_data["other_company_id"]

            with pytest.raises(HTTPException) as exc:
                resolve_azure_user(
                    session,
                    self._make_claims(
                        oid="attacker-oid", email="other_admin@example.com"
                    ),
                    company_a,
                )
            assert exc.value.status_code == 403

            session.expire_all()
            unchanged = session.get(User, other_admin.id)
            assert unchanged.azure_object_id is None
            assert unchanged.company_id == seeded_data["other_company_id"]

    def test_company_less_user_is_rejected(self, seeded_data, client):
        _, engine, _ = client
        company_id = seeded_data["company_id"]
        with Session(engine) as session:
            global_user = User(
                full_name="Global User",
                email="global@example.com",
                is_active=True,
                company_id=None,
            )
            session.add(global_user)
            session.commit()

            with pytest.raises(HTTPException) as exc:
                resolve_azure_user(
                    session, self._make_claims(email="global@example.com"),
                    company_id,
                )
            assert exc.value.status_code == 403

    def test_jit_provision_assigns_selected_company(
        self, seeded_data, client
    ):
        _, engine, _ = client
        company_id = seeded_data["company_id"]
        with Session(engine) as session:
            resolved = resolve_azure_user(
                session,
                self._make_claims(
                    oid="company-user-oid", email="companyuser@company.com"
                ),
                company_id,
            )

            assert resolved.email == "companyuser@company.com"
            assert resolved.company_id == company_id
            assert resolved.auth_provider == AuthProvider.AZURE_AD.value
            assert resolved.azure_object_id == "company-user-oid"
            assert resolved.hashed_password is None
            assert resolved.is_active is True
            assert len(resolved.roles) > 0  # seeded auditor role fallback

    def test_jit_provision_never_joins_other_company(
        self, seeded_data, client
    ):
        _, engine, _ = client
        with Session(engine) as session:
            resolved = resolve_azure_user(
                session,
                self._make_claims(
                    oid="oid-for-b", email="newuser@other-company.com"
                ),
                seeded_data["other_company_id"],
            )
            assert resolved.company_id == seeded_data["other_company_id"]

    def test_reject_inactive_user(self, seeded_data, client):
        _, engine, _ = client
        company_id = seeded_data["company_id"]
        with Session(engine) as session:
            user = User(
                full_name="Inactive User",
                email="inactive@example.com",
                hashed_password="fake-hash",
                is_active=False,
                company_id=company_id,
            )
            session.add(user)
            session.commit()

            with pytest.raises(HTTPException) as exc:
                resolve_azure_user(
                    session, self._make_claims(email="inactive@example.com"),
                    company_id,
                )
            assert "inactive" in exc.value.detail.lower()

    def test_reject_missing_oid(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            with pytest.raises(HTTPException) as exc:
                resolve_azure_user(
                    session,
                    {"email": "user@company.com", "name": "User"},
                    seeded_data["company_id"],
                )
            assert "oid" in exc.value.detail.lower()

    def test_reject_missing_email(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            with pytest.raises(HTTPException) as exc:
                resolve_azure_user(
                    session,
                    {"oid": "some-oid", "name": "User"},
                    seeded_data["company_id"],
                )
            assert "email" in exc.value.detail.lower()


# ── No global .env dependency (guard tests) ──────

class TestNoGlobalAzureEnvDependency:
    def test_settings_has_no_global_azure_fields(self):
        from core.config import Settings
        for attr in (
            "AZURE_CLIENT_ID",
            "AZURE_CLIENT_SECRET",
            "AZURE_TENANT_ID",
            "AZURE_SCOPES",
            "AZURE_DEFAULT_ROLE_NAME",
            "AZURE_ENABLED",
            "AZURE_AUTHORITY",
        ):
            assert attr not in Settings.model_fields
            assert not hasattr(settings, attr)

    @pytest.mark.parametrize(
        "relative_path",
        ["core/config.py", "auth/azure_service.py", "auth/router.py", "main.py"],
    )
    def test_auth_runtime_never_references_global_settings(self, relative_path):
        root = pathlib.Path(__file__).resolve().parents[1]
        source = (root / relative_path).read_text(encoding="utf-8")
        for name in (
            "AZURE_CLIENT_ID",
            "AZURE_CLIENT_SECRET",
            "AZURE_TENANT_ID",
            "AZURE_SCOPES",
            "AZURE_ENABLED",
            "AZURE_AUTHORITY",
        ):
            assert name not in source, f"{name} still referenced in {relative_path}"

    def test_auth_service_module_has_no_fallback(self):
        source = pathlib.Path(azure_service.__file__).read_text(encoding="utf-8")
        assert "Fallback to global config" not in source
        # The only settings reference allowed is the redirect URI (kept in .env)
        assert set(re.findall(r"settings\.AZURE_\w+", source)) == {"settings.AZURE_REDIRECT_URI"}


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
