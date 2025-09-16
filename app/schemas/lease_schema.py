from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from decimal import Decimal

# =========================
# Nested Schemas
# =========================
class TenantOut(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None

    class Config:
        orm_mode = True


class UnitOut(BaseModel):
    id: int
    number: str
    rent_amount: Decimal

    class Config:
        orm_mode = True


# =========================
# Lease Schemas
# =========================
class LeaseBase(BaseModel):
    tenant_id: int
    unit_id: int
    rent_amount: Decimal = Field(..., max_digits=10, decimal_places=2)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class LeaseCreate(LeaseBase):
    pass


class LeaseUpdate(BaseModel):
    rent_amount: Optional[Decimal] = Field(None, max_digits=10, decimal_places=2)
    end_date: Optional[datetime] = None
    active: Optional[int] = None


class LeaseOut(LeaseBase):
    id: int
    active: int
    tenant: Optional[TenantOut] = None
    unit: Optional[UnitOut] = None

    class Config:
        orm_mode = True
