"""Azure AD (Microsoft Entra ID) OIDC authentication service.

Handles:
- PKCE code-verifier / code-challenge generation
- Authorization URL construction
- Authorization code → token exchange
- ID token validation (JWT, issuer, audience, nonce, expiry)
- User resolution (JIT provisioning and account linking)
"""

import base64
import hashlib
import secrets
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from jose import JWTError, jwt
from jose.utils import long_to_base64
from sqlmodel import Session, select

from core.audit import AuditEvent, log_audit_event
from core.config import settings
from core.security import create_token_pair
from users.models import AuthProvider, Role, RoleName, User, UserRoleLink


# ── Microsoft OIDC discovery endpoints ────────────

OPENID_CONFIG_URL = (
    "https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration"
)
JWKS_URL_TEMPLATE = (
    "https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
)
TOKEN_ENDPOINT = (
    "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
)
AUTHORIZE_ENDPOINT = (
    "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize"
)

# Cache for signing keys: {kid: (keys_data, fetched_at)}
_jwks_cache: dict[str, tuple[list[dict], float]] = {}
_JWKS_CACHE_TTL = 3600  # 1 hour


# ── PKCE helpers ──────────────────────────────────

def generate_pkce_pair() -> tuple[str, str]:
    """Generate a PKCE code_verifier and code_challenge (S256)."""
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def generate_state() -> str:
    """Generate a cryptographically random state parameter for CSRF protection."""
    return secrets.token_urlsafe(32)


def generate_nonce() -> str:
    """Generate a nonce for id_token replay protection."""
    return secrets.token_urlsafe(32)


# ── Authorization URL ─────────────────────────────

def build_authorization_url(state: str, code_challenge: str, nonce: str) -> str:
    """Build the Microsoft authorization endpoint URL."""
    params = {
        "client_id": settings.AZURE_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": settings.AZURE_REDIRECT_URI,
        "response_mode": "query",
        "scope": " ".join(settings.AZURE_SCOPES),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "nonce": nonce,
    }
    return f"{AUTHORIZE_ENDPOINT.format(tenant_id=settings.AZURE_TENANT_ID)}?{urlencode(params)}"


# ── Token exchange ────────────────────────────────

async def exchange_code_for_tokens(
    code: str, code_verifier: str
) -> dict:
    """Exchange an authorization code for tokens at the Microsoft token endpoint."""
    data = {
        "client_id": settings.AZURE_CLIENT_ID,
        "client_secret": settings.AZURE_CLIENT_SECRET,
        "code": code,
        "redirect_uri": settings.AZURE_REDIRECT_URI,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            TOKEN_ENDPOINT.format(tenant_id=settings.AZURE_TENANT_ID),
            data=data,
        )

    if resp.status_code != 200:
        error_detail = resp.text
        log_audit_event(
            AuditEvent.AZURE_LOGIN_FAILED,
            detail=f"Token exchange failed: {error_detail}",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Azure AD token exchange failed",
        )

    return resp.json()


# ── JWKS fetching & caching ───────────────────────

async def _get_signing_keys() -> list[dict]:
    """Fetch Azure AD signing keys with caching."""
    cache_key = settings.AZURE_TENANT_ID
    now = time.time()

    if cache_key in _jwks_cache:
        keys, fetched_at = _jwks_cache[cache_key]
        if now - fetched_at < _JWKS_CACHE_TTL:
            return keys

    url = JWKS_URL_TEMPLATE.format(tenant_id=settings.AZURE_TENANT_ID)
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    keys_data = resp.json().get("keys", [])
    _jwks_cache[cache_key] = (keys_data, now)
    return keys_data


# ── ID token validation ───────────────────────────

async def validate_id_token(id_token: str, expected_nonce: str) -> dict:
    """Validate an Azure AD id_token and return the decoded claims.

    Validates:
    - Signature (against Azure signing keys)
    - Issuer (must match Azure tenant)
    - Audience (must match our client_id)
    - Expiration
    - Nonce (replay protection)
    """
    # Decode header to find kid
    try:
        header = jwt.get_unverified_header(id_token)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid id_token header: {e}",
        )

    kid = header.get("kid")
    if not kid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="id_token missing 'kid' header",
        )

    # Fetch signing keys and find the matching one
    signing_keys = await _get_signing_keys()
    key_data = None
    for k in signing_keys:
        if k.get("kid") == kid:
            key_data = k
            break

    if not key_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to find matching signing key for id_token",
        )

    # Build the RSA public key from JWK
    from jose import jwk
    public_key = jwk.construct(key_data)

    # Decode and validate
    expected_issuer = f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}/v2.0"
    try:
        claims = jwt.decode(
            id_token,
            public_key,
            algorithms=["RS256"],
            audience=settings.AZURE_CLIENT_ID,
            issuer=expected_issuer,
            options={
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "verify_aud": True,
                "verify_iss": True,
                "leeway": 300,  # 5 minutes clock skew tolerance
            },
        )
    except JWTError as e:
        log_audit_event(
            AuditEvent.AZURE_TOKEN_VALIDATION_FAILURE,
            detail=f"Token validation failed: {e}",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid id_token: {e}",
        )

    # Validate nonce
    token_nonce = claims.get("nonce")
    if token_nonce != expected_nonce:
        log_audit_event(
            AuditEvent.AZURE_TOKEN_VALIDATION_FAILURE,
            detail="Nonce mismatch — possible replay attack",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nonce mismatch in id_token",
        )

    return claims


# ── User resolution / JIT provisioning ────────────

def resolve_azure_user(
    session: Session,
    claims: dict,
    ip_address: Optional[str] = None,
) -> User:
    """Resolve an Azure AD identity to a DMS user.

    Resolution order:
    1. Match by azure_object_id (returning Azure-linked users immediately).
    2. Match by email (link Azure identity to existing local account).
    3. No match → JIT provision a new user.

    Raises HTTPException on unrecoverable errors (email mismatch, inactive account).
    """
    azure_oid = claims.get("oid")
    email = claims.get("email") or claims.get("preferred_username")
    display_name = claims.get("name", "")
    tenant_id = claims.get("tid", "")

    if not azure_oid or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Azure AD token missing required claims (oid, email)",
        )

    # 1. Look up by azure_object_id
    existing = session.exec(
        select(User).where(User.azure_object_id == azure_oid)
    ).first()
    if existing:
        if not existing.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive. Contact your administrator.",
            )
        # Update last login timestamp
        existing.azure_last_login_at = datetime.now(timezone.utc)
        existing.azure_display_name = display_name
        session.add(existing)
        session.commit()
        log_audit_event(
            AuditEvent.AZURE_LOGIN_SUCCESS,
            user_id=existing.id,
            email=existing.email,
            azure_oid=azure_oid,
            ip_address=ip_address,
        )
        return existing

    # 2. Look up by email (link to existing local account)
    existing = session.exec(
        select(User).where(User.email == email)
    ).first()
    if existing:
        if not existing.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive. Contact your administrator.",
            )
        # Link Azure identity
        existing.azure_object_id = azure_oid
        existing.azure_tenant_id = tenant_id
        existing.azure_display_name = display_name
        existing.azure_last_login_at = datetime.now(timezone.utc)
        existing.auth_provider = AuthProvider.AZURE_AD.value
        session.add(existing)
        session.commit()
        log_audit_event(
            AuditEvent.AZURE_USER_LINKED,
            user_id=existing.id,
            email=existing.email,
            azure_oid=azure_oid,
            ip_address=ip_address,
            detail="Linked Azure identity to existing local account",
        )
        log_audit_event(
            AuditEvent.AZURE_LOGIN_SUCCESS,
            user_id=existing.id,
            email=existing.email,
            azure_oid=azure_oid,
            ip_address=ip_address,
        )
        return existing

    # 3. JIT provision a new user
    default_role_name = settings.AZURE_DEFAULT_ROLE_NAME
    role = session.exec(
        select(Role).where(Role.name == default_role_name)
    ).first()
    if not role:
        # Fallback to auditor if configured role doesn't exist
        role = session.exec(
            select(Role).where(Role.name == RoleName.AUDITOR)
        ).first()

    new_user = User(
        full_name=display_name or email.split("@")[0],
        email=email,
        is_active=True,
        auth_provider=AuthProvider.AZURE_AD.value,
        azure_object_id=azure_oid,
        azure_tenant_id=tenant_id,
        azure_display_name=display_name,
        azure_last_login_at=datetime.now(timezone.utc),
    )
    session.add(new_user)
    session.flush()

    # Assign default role
    if role:
        session.add(UserRoleLink(user_id=new_user.id, role_id=role.id))

    session.commit()

    log_audit_event(
        AuditEvent.AZURE_JIT_PROVISIONING,
        user_id=new_user.id,
        email=new_user.email,
        azure_oid=azure_oid,
        ip_address=ip_address,
        detail=f"JIT provisioned with role: {role.name.value if role else 'none'}",
    )
    log_audit_event(
        AuditEvent.AZURE_LOGIN_SUCCESS,
        user_id=new_user.id,
        email=new_user.email,
        azure_oid=azure_oid,
        ip_address=ip_address,
    )

    # Re-fetch to load relationships
    from users.models import get_user_with_roles
    return get_user_with_roles(session, new_user.id) or new_user
