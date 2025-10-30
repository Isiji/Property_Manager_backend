from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List
from app.schemas.property_schema import PropertyOut

# ----- Property Manager -----

class PropertyManagerBase(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None
    id_number: Optional[str] = None  # NEW

class PropertyManagerCreate(PropertyManagerBase):
    pass

class PropertyManagerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    id_number: Optional[str] = None  # NEW

class PropertyManagerOut(PropertyManagerBase):
    id: int
    properties: List[PropertyOut] = []
    class Config:
        model_config = ConfigDict(from_attributes=True)

# ----- Landlord -----

class LandlordBase(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None
    id_number: Optional[str] = None  # NEW

class LandlordCreate(LandlordBase):
    pass

class LandlordUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    id_number: Optional[str] = None  # NEW

class LandlordOut(LandlordBase):
    id: int
    properties: List[PropertyOut] = []
    class Config:
        model_config = ConfigDict(from_attributes=True)
