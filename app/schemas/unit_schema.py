from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import date

class UnitBase(BaseModel):
    number: str
    rent_amount: float
    property_id: int

class UnitCreate(UnitBase):
    pass

class UnitUpdate(BaseModel):
    number: Optional[str] = None
    rent_amount: Optional[float] = None
    property_id: Optional[int] = None
    occupied: Optional[int] = None   # allow updates

class TenantSummary(BaseModel):
    id: int
    name: str
    phone: str
    email: str

    class Config:
        from_attributes = True

# Minimal lease info
class LeaseSummary(BaseModel):
    id: int
    start_date: date
    end_date: Optional[date]
    active: bool

    class Config:
        from_attributes = True

class UnitOut(UnitBase):
    id: int
    occupied: int
    tenant: Optional[TenantSummary] = None
    lease: Optional[LeaseSummary] = None

    class Config:
        from_attributes = True