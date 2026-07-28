from base64 import urlsafe_b64decode

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import RedirectResponse
from jose import JWTError
from sqlmodel import Session

from auth.azure_service import (
    build_authorization_url,
    exchange_code_for_tokens,
    generate_nonce,
    generate_pkce_pair,
    generate_state,
    resolve_azure_user,
    validate_id_token,
)
from auth.schemas import LoginRequest, PasswordChangeRequest, RefreshRequest, TokenResponse
from auth.service import AuthService
from core.audit import AuditEvent, log_audit_event
from core.config import settings
from core.database import get_session
from core.dependencies import CurrentUser
from core.security import create_token_pair
from users.models import AssignedCategoryRead, PermissionRead, RoleRead, UserRead

router = APIRouter()

# In-memory store for PKCE/state/nonce (production should use Redis or encrypted cookies)
_pending_auth: dict[str, dict] = {}


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ─────────────────────────────────────────────────
# Local Authentication
# ─────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse, summary="Obtain JWT token pair")
def login(
    payload: LoginRequest,
    session: Session = Depends(get_session),
):
    """
    Authenticate with email + password.
    Returns an access token (1 h) and a refresh token (7 days).
    """
    token_pair = AuthService(session).login(payload.email, payload.password)
    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse, summary="Rotate token pair")
def refresh(
    payload: RefreshRequest,
    session: Session = Depends(get_session),
):
    """Exchange a valid refresh token for a new access + refresh token pair."""
    token_pair = AuthService(session).refresh(payload.refresh_token)
    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
    )


@router.get("/me", response_model=UserRead, summary="Current user profile")
def me(current_user: CurrentUser):
    """
    Return the authenticated user's profile and assigned roles.
    Roles and permissions are already eagerly loaded by get_current_user
    so this serialises safely after the session closes.
    """
    return UserRead(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        is_active=current_user.is_active,
        auth_provider=current_user.auth_provider,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        roles=[
            RoleRead(
                id=role.id,
                name=role.name,
                description=role.description,
                created_at=role.created_at,
                permissions=[
                    PermissionRead(
                        id=perm.id,
                        action=perm.action,
                        description=perm.description,
                    )
                    for perm in role.permissions
                ],
            )
            for role in current_user.roles
        ],
        categories=[
            AssignedCategoryRead(
                id=category.id,
                name=category.name,
                description=category.description,
                is_active=category.is_active,
            )
            for category in current_user.categories
        ],
    )


@router.post("/change-password", summary="Change own password")
def change_password(
    payload:      PasswordChangeRequest,
    current_user: CurrentUser,
    session:      Session = Depends(get_session),
):
    """Allow any authenticated user to change their own password."""
    AuthService(session).change_password(
        current_user, payload.current_password, payload.new_password
    )
    return {"detail": "Password updated successfully"}


# ─────────────────────────────────────────────────
# Azure AD Authentication
# ─────────────────────────────────────────────────

@router.get(
    "/azure/login",
    summary="Initiate Azure AD login",
    response_class=RedirectResponse,
)
async def azure_login(request: Request):
    """
    Redirect the browser to the Microsoft Entra ID login page.

    Generates PKCE code_verifier + code_challenge, state, and nonce,
    stores them temporarily, and redirects to Azure's authorize endpoint.
    """
    if not settings.AZURE_ENABLED:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure AD authentication is not configured",
        )

    code_verifier, code_challenge = generate_pkce_pair()
    state = generate_state()
    nonce = generate_nonce()

    # Store temporarily (keyed by state) — production should use encrypted cookie or Redis
    _pending_auth[state] = {
        "code_verifier": code_verifier,
        "nonce": nonce,
    }

    auth_url = build_authorization_url(state, code_challenge, nonce)
    return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/azure/callback",
    summary="Azure AD OAuth callback",
    response_class=RedirectResponse,
)
async def azure_callback(
    request: Request,
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
    error_description: str = Query(None),
    session: Session = Depends(get_session),
):
    """
    Handle the redirect back from Microsoft Entra ID.

    Validates the state parameter, exchanges the authorization code for tokens,
    validates the id_token, resolves/creates the DMS user, and redirects
    to the frontend with the application's own JWT pair.
    """
    ip_address = _get_client_ip(request)

    # Check for Azure-side errors
    if error:
        log_audit_event(
            AuditEvent.AZURE_LOGIN_FAILED,
            ip_address=ip_address,
            detail=f"Azure returned error: {error} — {error_description}",
        )
        return RedirectResponse(
            url=f"http://localhost:5173/login?error={error_description or error}",
            status_code=status.HTTP_302_FOUND,
        )

    # Validate state
    if not state or state not in _pending_auth:
        log_audit_event(
            AuditEvent.AZURE_LOGIN_FAILED,
            ip_address=ip_address,
            detail="Invalid or missing state parameter",
        )
        return RedirectResponse(
            url="http://localhost:5173/login?error=Invalid+state+parameter",
            status_code=status.HTTP_302_FOUND,
        )

    pending = _pending_auth.pop(state)
    code_verifier = pending["code_verifier"]
    expected_nonce = pending["nonce"]

    if not code:
        log_audit_event(
            AuditEvent.AZURE_LOGIN_FAILED,
            ip_address=ip_address,
            detail="Missing authorization code in callback",
        )
        return RedirectResponse(
            url="http://localhost:5173/login?error=Missing+authorization+code",
            status_code=status.HTTP_302_FOUND,
        )

    try:
        # Exchange code for tokens
        token_data = await exchange_code_for_tokens(code, code_verifier)
        raw_id_token = token_data.get("id_token")

        if not raw_id_token:
            log_audit_event(
                AuditEvent.AZURE_LOGIN_FAILED,
                ip_address=ip_address,
                detail="No id_token in token response",
            )
            return RedirectResponse(
                url="http://localhost:5173/login?error=No+ID+token+received",
                status_code=status.HTTP_302_FOUND,
            )

        # Validate the id_token
        claims = await validate_id_token(raw_id_token, expected_nonce)

        # Resolve user (JIT provisioning)
        user = resolve_azure_user(session, claims, ip_address=ip_address)

        if not user.is_active:
            return RedirectResponse(
                url="http://localhost:5173/login?error=Account+is+inactive",
                status_code=status.HTTP_302_FOUND,
            )

        # Issue DMS JWT tokens
        token_pair = create_token_pair(user.id)

        # Redirect to frontend callback page with tokens
        redirect_url = (
            f"http://localhost:5173/auth/callback"
            f"?access_token={token_pair.access_token}"
            f"&refresh_token={token_pair.refresh_token}"
        )
        return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)

    except Exception as exc:
        log_audit_event(
            AuditEvent.AZURE_LOGIN_FAILED,
            ip_address=ip_address,
            detail=f"Unexpected error during Azure authentication: {exc}",
        )
        return RedirectResponse(
            url="http://localhost:5173/login?error=Authentication+failed",
            status_code=status.HTTP_302_FOUND,
        )


@router.get(
    "/azure/config",
    summary="Check if Azure AD is enabled",
)
def azure_config():
    """Return whether Azure AD authentication is available."""
    return {"enabled": settings.AZURE_ENABLED}
