from pydantic import BaseModel


class LoginRequest(BaseModel):
    # Plain str intentionally — login must accept any stored email value
    # (including non-public domains like .local, .internal, .test).
    # Format validation belongs on UserCreate, not on the login form.
    email:    str
    password: str


class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password:     str