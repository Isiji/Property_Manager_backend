from pydantic import BaseModel
from typing import List, Optional
from app.schemas.unit_schema import UnitOut  # to show units in property details

class PropertyBase(BaseModel):
    name: str
    address: str
    landlord_id: Optional[int] = None
    manager_id: Optional[int] = None

class PropertyCreate(PropertyBase):
    pass

class PropertyUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    manager_id: Optional[int] = None

class PropertyOut(PropertyBase):
    id: int
    units: List[UnitOut] = []
    class Config:
        from_attributes = True