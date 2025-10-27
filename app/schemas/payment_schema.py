# app/schemas/payment_schemas.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.models.payment_model import PaymentStatus


class PaymentBase(BaseModel):
    tenant_id: int
    unit_id: int
    lease_id: Optional[int] = None

    amount: Decimal = Field(..., max_digits=12, decimal_places=2)

    # Monthly tag: "YYYY-MM" (e.g., "2025-10")
    period: str = Field(..., min_length=7, max_length=7)

    # Optional – set if known when creating or after payment is received
    status: PaymentStatus = PaymentStatus.pending
    paid_date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("period")
    @classmethod
    def check_period_format(cls, v: str) -> str:
        # Very light check; DB constraints/logic should enforce uniqueness
        # Accepts "YYYY-MM" where YYYY=4 digits, MM=01..12
        if len(v) != 7 or v[4] != "-":
            raise ValueError("period must be in 'YYYY-MM' format")
        yyyy, mm = v.split("-")
        if not (yyyy.isdigit() and mm.isdigit() and 1 <= int(mm) <= 12):
            raise ValueError("period must be in 'YYYY-MM' format with valid month")
        return v


class PaymentCreate(PaymentBase):
    pass


class PaymentUpdate(BaseModel):
    amount: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2)
    status: Optional[PaymentStatus] = None
    paid_date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)


class PaymentOut(BaseModel):
    id: int
    tenant_id: int
    unit_id: int
    lease_id: Optional[int] = None

    amount: Decimal
    period: str
    status: PaymentStatus
    paid_date: Optional[date] = None

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
