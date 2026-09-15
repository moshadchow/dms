from datetime import datetime
from typing import List, Optional

from sqlmodel import Field, SQLModel


# ──────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────

class CompanyBase(SQLModel):
    company_id: str = Field(max_length=100, index=True, description="Unique company identifier")
    full_name: str = Field(max_length=255, description="Full company name")
    short_name: str = Field(max_length=100, index=True, description="Short company name")
    address: Optional[str] = Field(default=None, max_length=500)
    contact_person: Optional[str] = Field(default=None, max_length=255)
    contact_no: Optional[str] = Field(default=None, max_length=50)
    email_address: Optional[str] = Field(default=None, max_length=255)
    is_active: bool = Field(default=True)
    # ── Azure AD (per-company) ────────────────
    azure_client_id: Optional[str] = Field(default=None, max_length=255)
    azure_client_secret: Optional[str] = Field(default=None, max_length=500)
    azure_tenant_id: Optional[str] = Field(default=None, max_length=255)
    azure_enabled: bool = Field(default=False)
    azure_default_role_name: Optional[str] = Field(default=None, max_length=50)


class Company(CompanyBase, table=True):
    __tablename__ = "companies"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(SQLModel):
    company_id: Optional[str] = None
    full_name: Optional[str] = None
    short_name: Optional[str] = None
    address: Optional[str] = None
    contact_person: Optional[str] = None
    contact_no: Optional[str] = None
    email_address: Optional[str] = None
    is_active: Optional[bool] = None


class AzureConfigUpdate(SQLModel):
    """Request schema for updating a company's Azure AD configuration."""
    azure_client_id: Optional[str] = None
    azure_client_secret: Optional[str] = None
    azure_tenant_id: Optional[str] = None
    azure_enabled: Optional[bool] = None
    azure_default_role_name: Optional[str] = None


class AzureConfigRead(SQLModel):
    """Response schema for a company's Azure AD configuration (never exposes secret)."""
    configured: bool = False
    azure_client_id: Optional[str] = None
    azure_tenant_id: Optional[str] = None
    azure_enabled: bool = False
    azure_default_role_name: Optional[str] = None
    model_config = {"from_attributes": True}


class CompanyRead(CompanyBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
