from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from core.database import get_session
from core.dependencies import SuperAdminUser
from company_profile.models import (
    CompanyCreate,
    CompanyRead,
    CompanyUpdate,
)
from company_profile.service import CompanyService

router = APIRouter()


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
