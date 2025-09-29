from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List
from app.schemas.property_schema import PropertyOut  # so we can show properties

class PropertyManagerBase(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None

class PropertyManagerCreate(PropertyManagerBase):
    pass

class PropertyManagerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None

class PropertyManagerOut(PropertyManagerBase):
    id: int
    properties: List[PropertyOut] = []   # include all managed properties

    class Config:
        model_config = ConfigDict(from_attributes=True)
