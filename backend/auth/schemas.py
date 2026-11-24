from typing import List, Optional

from pydantic import BaseModel


class CompanyOption(BaseModel):
    id:   int
    name: str


class LoginRequest(BaseModel):
    email:      str
    password:   str
    company_id: Optional[int] = None


class LoginResponse(BaseModel):
    access_token:              Optional[str] = None
    refresh_token:             Optional[str] = None
    token_type:                str = "bearer"
    requires_company_selection: bool = False
    selection_token:           Optional[str] = None
    companies:                 Optional[List[CompanyOption]] = None


class SelectCompanyRequest(BaseModel):
    selection_token: str
    company_id:      int


class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password:     str
