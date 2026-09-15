from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from core.database import get_session
from core.dependencies import AdminUser, CurrentUser, SuperAdminUser
from company_profile.models import (
    AzureConfigRead,
    AzureConfigUpdate,
    CompanyCreate,
    CompanyRead,
    CompanyUpdate,
)
from company_profile.service import CompanyService

router = APIRouter()


# ─────────────────────────────────────────────────
# Azure AD configuration (per-company)
# ─────────────────────────────────────────────────

@router.get(
    "/{company_id}/azure-config",
    response_model=AzureConfigRead,
    summary="Get Azure AD config for a company",
)
def get_azure_config(
    company_id: int,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    """SuperAdmin can view any company config; Admin can view own company only."""
    from fastapi import HTTPException
    from users.models import RoleName
    # SuperAdmin can view any company
    is_superadmin = any(r.name == RoleName.SUPERADMIN for r in current_user.roles)
    if not is_superadmin:
        # Admin: only own company
        if not current_user.is_admin() or current_user.company_id != company_id:
            raise HTTPException(status_code=403, detail="Admin or SuperAdmin access required")
    return CompanyService(session).get_azure_config(company_id)


@router.put(
    "/{company_id}/azure-config",
    response_model=AzureConfigRead,
    summary="Set Azure AD config for a company (SuperAdmin only)",
)
def update_azure_config(
    company_id: int,
    payload: AzureConfigUpdate,
    _: SuperAdminUser = None,
    session: Session = Depends(get_session),
):
    return CompanyService(session).update_azure_config(company_id, payload)


@router.delete(
    "/{company_id}/azure-config",
    response_model=AzureConfigRead,
    summary="Remove Azure AD config from a company (SuperAdmin only)",
)
def delete_azure_config(
    company_id: int,
    _: SuperAdminUser = None,
    session: Session = Depends(get_session),
):
    return CompanyService(session).delete_azure_config(company_id)


# ─────────────────────────────────────────────────
# Company CRUD (SuperAdmin only)
# ─────────────────────────────────────────────────


@router.get("", response_model=dict, summary="List all companies (Super Admin only)")
def list_companies(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None, description="Filter by name or company ID"),
    is_active: Optional[bool] = Query(None),
    _: SuperAdminUser = None,
    session: Session = Depends(get_session),
):
    companies, total = CompanyService(session).list_companies(skip, limit, search, is_active)
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [CompanyRead.model_validate(c) for c in companies],
    }


@router.get(
    "/{company_id}",
    response_model=CompanyRead,
    summary="Get company by ID (Super Admin only)",
)
def get_company(
    company_id: int,
    _: SuperAdminUser = None,
    session: Session = Depends(get_session),
):
    return CompanyService(session).get_company(company_id)


@router.post(
    "",
    response_model=CompanyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new company (Super Admin only)",
)
def create_company(
    payload: CompanyCreate,
    _: SuperAdminUser = None,
    session: Session = Depends(get_session),
):
    return CompanyService(session).create_company(payload)


@router.patch(
    "/{company_id}",
    response_model=CompanyRead,
    summary="Update company (Super Admin only)",
)
def update_company(
    company_id: int,
    payload: CompanyUpdate,
    _: SuperAdminUser = None,
    session: Session = Depends(get_session),
):
    return CompanyService(session).update_company(company_id, payload)


@router.patch(
    "/{company_id}/activate",
    response_model=CompanyRead,
    summary="Activate company (Super Admin only)",
)
def activate_company(
    company_id: int,
    _: SuperAdminUser = None,
    session: Session = Depends(get_session),
):
    return CompanyService(session).activate_company(company_id)


@router.patch(
    "/{company_id}/deactivate",
    response_model=CompanyRead,
    summary="Deactivate company (Super Admin only)",
)
def deactivate_company(
    company_id: int,
    _: SuperAdminUser = None,
    session: Session = Depends(get_session),
):
    return CompanyService(session).deactivate_company(company_id)
