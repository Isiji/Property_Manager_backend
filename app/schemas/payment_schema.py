# app/schemas/payment_schemas.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.models.payment_model import PaymentStatus


class PaymentAllocationOut(BaseModel):
    period: str
    amount_applied: Decimal

    model_config = ConfigDict(from_attributes=True)

    @field_validator("period")
    @classmethod
    def check_period_format(cls, v: str) -> str:
        if len(v) != 7 or v[4] != "-":
            raise ValueError("period must be in 'YYYY-MM' format")
        yyyy, mm = v.split("-")
        if not (yyyy.isdigit() and mm.isdigit() and 1 <= int(mm) <= 12):
            raise ValueError("period must be in 'YYYY-MM' format with valid month")
        return v


class PaymentBase(BaseModel):
    tenant_id: int
    unit_id: int
    lease_id: Optional[int] = None

    amount: Decimal = Field(..., max_digits=12, decimal_places=2)

    period: str = Field(..., min_length=7, max_length=7)

    status: PaymentStatus = PaymentStatus.pending
    paid_date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("period")
    @classmethod
    def check_period_format(cls, v: str) -> str:
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
    reference: Optional[str] = None
    merchant_request_id: Optional[str] = None
    checkout_request_id: Optional[str] = None
    payment_method: Optional[str] = None
    allocation_mode: Optional[str] = None
    selected_periods_json: Optional[str] = None
    notes: Optional[str] = None

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

    reference: Optional[str] = None
    merchant_request_id: Optional[str] = None
    checkout_request_id: Optional[str] = None
    payment_method: Optional[str] = None
    allocation_mode: Optional[str] = None
    selected_periods_json: Optional[str] = None
    notes: Optional[str] = None

    created_at: datetime
    allocations: List[PaymentAllocationOut] = []

    model_config = ConfigDict(from_attributes=True)