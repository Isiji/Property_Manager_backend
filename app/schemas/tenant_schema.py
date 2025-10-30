from pydantic import BaseModel, EmailStr, Field
from typing import Optional

# ---------- Create / Update ----------

class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1)
    phone: str = Field(..., min_length=3)
    email: Optional[EmailStr] = None  # optional to match nullable=True
    property_id: int
    unit_id: int
    password: Optional[str] = None  # optional during assignment
    id_number: Optional[str] = None  # <— NEW optional National ID

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    id_number: Optional[str] = None  # <— NEW

# ---------- Read / Out ----------

class TenantOut(BaseModel):
    id: int
    name: str
    phone: str
    email: Optional[EmailStr] = None
    property_id: int
    unit_id: int
    id_number: Optional[str] = None  # <— NEW

    class Config:
        from_attributes = True

# ---------- Self-register flow (if you use it) ----------

class TenantSelfRegister(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None
    property_id: int
    unit_id: int
    password: Optional[str] = None
    id_number: Optional[str] = None  # <— NEW
