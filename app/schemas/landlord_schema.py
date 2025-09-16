# app/schemas/landlords.py
from pydantic import BaseModel, EmailStr
from typing import Optional

class LandlordBase(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None

class LandlordCreate(LandlordBase):
    pass

class LandlordUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None

class LandlordOut(LandlordBase):
    id: int

    class Config:
        orm_mode = True
