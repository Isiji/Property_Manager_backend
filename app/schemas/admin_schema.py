# app/schemas/admin_schema.py
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional

class AdminBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None

class AdminCreate(AdminBase):
    password: str  # plaintext for now (later we hash it)

class AdminUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: Optional[str] = None

class AdminOut(AdminBase):
    id: int

    class Config:
        model_config = ConfigDict(from_attributes=True)
