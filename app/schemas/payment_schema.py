# app/schemas/payments.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from decimal import Decimal


class PaymentBase(BaseModel):
    tenant_id: int
    unit_id: int
    lease_id: Optional[int] = None
    amount: Decimal = Field(..., max_digits=10, decimal_places=2)
    description: Optional[str] = None


class PaymentCreate(PaymentBase):
    pass


class PaymentUpdate(BaseModel):
    amount: Optional[Decimal] = Field(None, max_digits=10, decimal_places=2)
    description: Optional[str] = None


class PaymentOut(PaymentBase):
    id: int
    date: datetime

    class Config:
        from_attributes = True  # replaces orm_mode=True in Pydantic v2
