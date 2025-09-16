# app/schemas/tenant.py
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional

# Shared properties
class TenantBase(BaseModel):
    name: str
    email: EmailStr
    phone: str

# Create payload
class TenantCreate(TenantBase):
    pass

# Update payload (all fields optional)
class TenantUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

# Response model
class TenantOut(TenantBase):
    id: int

    class Config:
        model_config = ConfigDict(from_attributes=True)
