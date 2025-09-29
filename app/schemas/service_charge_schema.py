# app/schemas/service_charges.py
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, Annotated
from decimal import Decimal


class ServiceChargeBase(BaseModel):
    tenant_id: int
    unit_id: int
    service_type: str  # e.g., "water", "garbage", "security"
    amount: Decimal = Field(..., max_digits=10, decimal_places=2)


class ServiceChargeCreate(ServiceChargeBase):
    pass


class ServiceChargeUpdate(BaseModel):
    service_type: Optional[str] = None
    amount: Optional[Decimal] = Field(None, max_digits=10, decimal_places=2)


class ServiceChargeOut(ServiceChargeBase):
    id: int
    date: datetime

    class Config:
        model_config = ConfigDict(from_attributes=True)
