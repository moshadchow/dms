import logging
from base64 import urlsafe_b64decode
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from jose import JWTError
from sqlmodel import Session

from auth.azure_service import (
    build_authorization_url,
    decode_state,
    exchange_code_for_tokens,
    generate_nonce,
    generate_pkce_pair,
    generate_state,
    get_azure_config_for_company,
    resolve_azure_user,
    validate_id_token,
)
from auth.schemas import LoginRequest, PasswordChangeRequest, RefreshRequest, TokenResponse
from auth.service import AuthService
from audit.models import AuditAction, AuditModule
from audit.service import AuditService
from core.config import settings
from core.database import get_session
from core.dependencies import CurrentUser
from core.security import create_token_pair
from users.models import AssignedCategoryRead, PermissionRead, RoleRead, UserRead

router = APIRouter()

# In-memory store for PKCE/state/nonce (production should use Redis or encrypted cookies)
_pending_auth: dict[str, dict] = {}

logger = logging.getLogger("dms.auth")


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
# Azure AD Authentication (company-scoped)
# ─────────────────────────────────────────────────

@router.get(
    "/azure/login",
    summary="Initiate Azure AD login",
    response_class=RedirectResponse,
)
async def azure_login(
    request: Request,
    company_id: int = Query(None, description="Company ID for company-scoped Azure AD"),
):
    """
    Redirect the browser to the Microsoft Entra ID login page.

    When company_id is provided, uses that company's Azure AD config.
    Otherwise falls back to the global .env Azure AD config.

    Generates PKCE code_verifier + code_challenge, state (encoding nonce + company_id),
    and redirects to Azure's authorize endpoint.
    """
    session = next(get_session())
    try:
        azure_config = get_azure_config_for_company(session, company_id)
    finally:
        session.close()

    code_verifier, code_challenge = generate_pkce_pair()
    nonce = generate_nonce()
    state = generate_state(nonce, company_id)

    # Store temporarily (keyed by state) — production should use encrypted cookie or Redis
    _pending_auth[state] = {
        "code_verifier": code_verifier,
        "nonce": nonce,
        "company_id": company_id,
    }

    auth_url = build_authorization_url(state, code_challenge, nonce, azure_config)
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
        AuditService(session).log_event(
            action=AuditAction.FAILED_LOGIN,
            module=AuditModule.AUTH,
            description=f"Azure returned error: {error} — {error_description}",
            ip_address=ip_address,
            is_success=False,
            failure_reason=f"{error}: {error_description}",
        )
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error={error_description or error}",
            status_code=status.HTTP_302_FOUND,
        )

    # Validate state
    if not state or state not in _pending_auth:
        AuditService(session).log_event(
            action=AuditAction.FAILED_LOGIN,
            module=AuditModule.AUTH,
            description="Invalid or missing state parameter",
            ip_address=ip_address,
            is_success=False,
            failure_reason="Invalid or missing state parameter",
        )
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error=Invalid+state+parameter",
            status_code=status.HTTP_302_FOUND,
        )

    pending = _pending_auth.pop(state)
    code_verifier = pending["code_verifier"]
    expected_nonce = pending["nonce"]
    company_id = pending.get("company_id")

    if not code:
        AuditService(session).log_event(
            action=AuditAction.FAILED_LOGIN,
            module=AuditModule.AUTH,
            description="Missing authorization code in callback",
            ip_address=ip_address,
            is_success=False,
            failure_reason="Missing authorization code",
        )
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error=Missing+authorization+code",
            status_code=status.HTTP_302_FOUND,
        )

    try:
        # Get Azure config for this company (or global fallback)
        azure_config = get_azure_config_for_company(session, company_id)

        # Exchange code for tokens
        token_data = await exchange_code_for_tokens(code, code_verifier, azure_config)
        raw_id_token = token_data.get("id_token")

        if not raw_id_token:
            AuditService(session).log_event(
                action=AuditAction.FAILED_LOGIN,
                module=AuditModule.AUTH,
                description="No id_token in token response",
                ip_address=ip_address,
                is_success=False,
                failure_reason="No id_token in token response",
            )
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/login?error=No+ID+token+received",
                status_code=status.HTTP_302_FOUND,
            )

        # Validate the id_token
        claims = await validate_id_token(raw_id_token, expected_nonce, azure_config)

        # Resolve user (JIT provisioning)
        user = resolve_azure_user(
            session,
            claims,
            ip_address=ip_address,
            company_id=company_id,
            default_role_name=azure_config.get("default_role_name"),
        )

        if not user.is_active:
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/login?error=Account+is+inactive",
                status_code=status.HTTP_302_FOUND,
            )

        # Issue DMS JWT tokens
        token_pair = create_token_pair(user.id)

        # Redirect to frontend callback page with tokens
        redirect_url = (
            f"{settings.FRONTEND_URL}/auth/callback"
            f"?access_token={token_pair.access_token}"
            f"&refresh_token={token_pair.refresh_token}"
        )
        return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)

    except HTTPException as exc:
        AuditService(session).log_event(
            action=AuditAction.FAILED_LOGIN,
            module=AuditModule.AUTH,
            description=f"Azure auth failed: {exc.detail}",
            ip_address=ip_address,
            is_success=False,
            failure_reason=str(exc.detail),
        )
        logger.error("Azure callback HTTPException: %s", exc.detail)
        error_msg = exc.detail if settings.DEBUG else "Authentication failed"
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error={quote(error_msg)}",
            status_code=status.HTTP_302_FOUND,
        )

    except Exception as exc:
        AuditService(session).log_event(
            action=AuditAction.FAILED_LOGIN,
            module=AuditModule.AUTH,
            description=f"Unexpected error during Azure authentication: {exc}",
            ip_address=ip_address,
            is_success=False,
            failure_reason=str(exc),
        )
        logger.exception("Unexpected error during Azure callback")
        error_msg = str(exc) if settings.DEBUG else "Authentication failed"
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error={quote(error_msg)}",
            status_code=status.HTTP_302_FOUND,
        )


@router.get(
    "/azure/config",
    summary="Check if Azure AD is enabled",
)
def azure_config(session: Session = Depends(get_session)):
    """Return whether Azure AD authentication is available and which companies have it enabled."""
    global_enabled = settings.AZURE_ENABLED

    # Find companies with Azure enabled
    from company_profile.models import Company
    companies = session.exec(
        select(Company).where(Company.azure_enabled == True)  # noqa: E712
    ).all()

    return {
        "global_enabled": global_enabled,
        "companies": [
            {"id": c.id, "name": c.full_name, "short_name": c.short_name}
            for c in companies
        ],
    }


# Need select for azure_config
from sqlmodel import select  # noqa: E402
