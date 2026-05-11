from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    department: Optional[str] = "General"
    role: Optional[str] = "User"
    formulary: Optional[str] = "commercial"
    alerts: Optional[bool] = True


class UserCreate(UserBase):
    password: str = Field(min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(UserBase):
    id: int
    is_active: bool
    is_verified: bool


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[EmailStr] = None
    type: Optional[str] = None


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    password: str = Field(min_length=6)


class PasswordChangeRequest(BaseModel):
    email: EmailStr
    current_password: str
    new_password: str = Field(min_length=6)


class VerifyTokenRequest(BaseModel):
    token: str
