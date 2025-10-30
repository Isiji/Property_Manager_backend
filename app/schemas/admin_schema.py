from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional

class AdminBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    id_number: Optional[str] = None  # NEW

class AdminCreate(AdminBase):
    password: str  # plaintext for now (later hash)

class AdminUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: Optional[str] = None
    id_number: Optional[str] = None  # NEW

class AdminOut(AdminBase):
    id: int
    class Config:
        model_config = ConfigDict(from_attributes=True)
