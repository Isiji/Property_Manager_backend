from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1)
    phone: str = Field(..., min_length=3)
    email: Optional[EmailStr] = None
    property_id: int
    unit_id: int
    password: Optional[str] = None
    id_number: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Name is required")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Phone is required")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if v == "":
            return None
        if len(v) < 4:
            raise ValueError("Password must be at least 4 characters long")
        return v

    @field_validator("id_number")
    @classmethod
    def clean_id_number(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    id_number: Optional[str] = None
    property_id: Optional[int] = None
    unit_id: Optional[int] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if v == "":
            return None
        if len(v) < 4:
            raise ValueError("Password must be at least 4 characters long")
        return v

    @field_validator("id_number")
    @classmethod
    def clean_id_number(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None


class TenantOut(BaseModel):
    id: int
    name: str
    phone: str
    email: Optional[EmailStr] = None
    property_id: int
    unit_id: int
    id_number: Optional[str] = None

    class Config:
        from_attributes = True


class TenantSelfRegister(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None
    property_id: int
    unit_id: int
    password: Optional[str] = None
    id_number: Optional[str] = None