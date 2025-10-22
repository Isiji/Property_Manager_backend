from pydantic import BaseModel, EmailStr, Field
from typing import Optional


# ---------- Create / Update ----------

class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1)
    phone: str = Field(..., min_length=3)
    # Make email OPTIONAL to match your model (nullable=True) and your UX
    email: Optional[EmailStr] = None
    property_id: int
    unit_id: int
    # Optional password for cases where you want to set one during assignment
    password: Optional[str] = None


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    # You can also allow property_id / unit_id updates if your business rules permit it:
    # property_id: Optional[int] = None
    # unit_id: Optional[int] = None
    password: Optional[str] = None


# ---------- Read / Out ----------

class TenantOut(BaseModel):
    id: int
    name: str
    phone: str
    email: Optional[EmailStr] = None
    property_id: int
    unit_id: int

    class Config:
        from_attributes = True


# ---------- Self-register flow (if you use it) ----------

class TenantSelfRegister(BaseModel):
    name: str
    phone: str
    # Keep this optional as well to align with the rest
    email: Optional[EmailStr] = None
    # If your self-register uses property_code+unit_number instead of ids:
    # property_code: str
    # unit_number: str
    # Or if you already mapped ids on the client, keep ids:
    property_id: int
    unit_id: int
    password: Optional[str] = None
