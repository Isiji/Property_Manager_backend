from pydantic import BaseModel
from typing import List, Optional

class PropertyBase(BaseModel):
    name: str
    address: str
    landlord_id: int
    manager_id: Optional[int] = None

class PropertyCreate(PropertyBase):
    pass

class PropertyUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    manager_id: Optional[int] = None

class PropertyOut(PropertyBase):
    id: int
    class Config:
        orm_mode = True
