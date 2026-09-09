import re
from datetime import datetime
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlmodel import Session, select

from audit.models import AuditAction, AuditModule
from audit.service import AuditService
from company_profile.models import (
    Company,
    CompanyCreate,
    CompanyRead,
    CompanyUpdate,
)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def _company_to_read(company: Company) -> CompanyRead:
    return CompanyRead(
        id=company.id,
        company_id=company.company_id,
        full_name=company.full_name,
        short_name=company.short_name,
        address=company.address,
        contact_person=company.contact_person,
        contact_no=company.contact_no,
        email_address=company.email_address,
        is_active=company.is_active,
        created_at=company.created_at,
        updated_at=company.updated_at,
    )


class CompanyService:
    def __init__(self, session: Session):
        self.session = session

    def list_companies(
        self,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Tuple[List[CompanyRead], int]:
        query = select(Company)
        if search:
            query = query.where(
                Company.full_name.ilike(f"%{search}%")
                | Company.short_name.ilike(f"%{search}%")
                | Company.company_id.ilike(f"%{search}%")
            )
        if is_active is not None:
            query = query.where(Company.is_active == is_active)

        all_companies = self.session.exec(query).all()
        total = len(all_companies)
        page = self.session.exec(query.offset(skip).limit(limit)).all()
        return [_company_to_read(c) for c in page], total

    def get_company(self, company_id: int) -> CompanyRead:
        company = self.session.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=404, detail=f"Company {company_id} not found")
        return _company_to_read(company)

    def create_company(self, data: CompanyCreate) -> CompanyRead:
        # Validate email format
        if data.email_address and not EMAIL_REGEX.match(data.email_address):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid email address format",
            )

        # Check unique company_id
        existing = self.session.exec(
            select(Company).where(Company.company_id == data.company_id)
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Company ID '{data.company_id}' already exists",
            )

        # Check unique short_name
        existing_short = self.session.exec(
            select(Company).where(Company.short_name == data.short_name)
        ).first()
        if existing_short:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Short name '{data.short_name}' already exists",
            )

        company = Company(
            company_id=data.company_id,
            full_name=data.full_name,
            short_name=data.short_name,
            address=data.address,
            contact_person=data.contact_person,
            contact_no=data.contact_no,
            email_address=data.email_address,
            is_active=data.is_active,
        )
        self.session.add(company)
        self.session.commit()
        self.session.refresh(company)

        AuditService(self.session).log_event(
            action=AuditAction.CREATE_COMPANY,
            module=AuditModule.COMPANIES,
            entity_name="company",
            entity_id=str(company.id),
            new_value={"company_id": data.company_id, "full_name": data.full_name},
            description=f"Created company {data.company_id}",
            is_success=True,
        )

        return _company_to_read(company)

    def update_company(self, company_id: int, data: CompanyUpdate) -> CompanyRead:
        company = self.session.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=404, detail=f"Company {company_id} not found")

        # Validate email format if provided
        if data.email_address is not None and data.email_address and not EMAIL_REGEX.match(data.email_address):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid email address format",
            )

        # Check unique company_id if changed
        if data.company_id is not None and data.company_id != company.company_id:
            existing = self.session.exec(
                select(Company).where(Company.company_id == data.company_id)
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Company ID '{data.company_id}' already exists",
                )

        # Check unique short_name if changed
        if data.short_name is not None and data.short_name != company.short_name:
            existing_short = self.session.exec(
                select(Company).where(Company.short_name == data.short_name)
            ).first()
            if existing_short:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Short name '{data.short_name}' already exists",
                )

        old_values = {
            "company_id": company.company_id,
            "full_name": company.full_name,
            "short_name": company.short_name,
        }

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(company, field, value)

        company.updated_at = datetime.utcnow()
        self.session.add(company)
        self.session.commit()
        self.session.refresh(company)

        new_values = {
            "company_id": company.company_id,
            "full_name": company.full_name,
            "short_name": company.short_name,
        }

        AuditService(self.session).log_event(
            action=AuditAction.UPDATE_COMPANY,
            module=AuditModule.COMPANIES,
            entity_name="company",
            entity_id=str(company_id),
            old_value=old_values,
            new_value=new_values,
            description=f"Updated company {company.company_id}",
            is_success=True,
        )

        return _company_to_read(company)

    def activate_company(self, company_id: int) -> CompanyRead:
        company = self.session.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=404, detail=f"Company {company_id} not found")

        if company.is_active:
            return _company_to_read(company)

        company.is_active = True
        company.updated_at = datetime.utcnow()
        self.session.add(company)
        self.session.commit()
        self.session.refresh(company)

        AuditService(self.session).log_event(
            action=AuditAction.ACTIVATE_COMPANY,
            module=AuditModule.COMPANIES,
            entity_name="company",
            entity_id=str(company_id),
            old_value={"is_active": False},
            new_value={"is_active": True},
            description=f"Activated company {company.company_id}",
            is_success=True,
        )

        return _company_to_read(company)

    def deactivate_company(self, company_id: int) -> CompanyRead:
        company = self.session.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=404, detail=f"Company {company_id} not found")

        if not company.is_active:
            return _company_to_read(company)

        company.is_active = False
        company.updated_at = datetime.utcnow()
        self.session.add(company)
        self.session.commit()
        self.session.refresh(company)

        AuditService(self.session).log_event(
            action=AuditAction.DEACTIVATE_COMPANY,
            module=AuditModule.COMPANIES,
            entity_name="company",
            entity_id=str(company_id),
            old_value={"is_active": True},
            new_value={"is_active": False},
            description=f"Deactivated company {company.company_id}",
            is_success=True,
        )

        return _company_to_read(company)
