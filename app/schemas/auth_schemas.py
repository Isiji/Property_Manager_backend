from typing import Optional
from pydantic import BaseModel, EmailStr


class RegisterUser(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    role: str
    id_number: Optional[str] = None

    # tenant
    property_code: Optional[str] = None
    unit_number: Optional[str] = None
    unit_id: Optional[int] = None

    # manager
    manager_type: Optional[str] = None
    company_name: Optional[str] = None
    contact_person: Optional[str] = None
    office_phone: Optional[str] = None
    office_email: Optional[EmailStr] = None


class LoginUser(BaseModel):
    phone: str
    password: Optional[str] = None
    role: str


class ForgotPasswordRequest(BaseModel):
    role: str
    email: EmailStr


class VerifyResetOTPRequest(BaseModel):
    role: str
    email: EmailStr
    otp_code: str


class ResetPasswordRequest(BaseModel):
    role: str
    email: EmailStr
    otp_code: str
    new_password: str


class ResendResetOTPRequest(BaseModel):
    role: str
    email: EmailStr