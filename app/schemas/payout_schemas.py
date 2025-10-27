# app/schemas/payout_schemas.py
from __future__ import annotations

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from app.models.payout_models import PayoutType


class PayoutBase(BaseModel):
    landlord_id: int
    payout_type: PayoutType
    label: str = Field(..., min_length=2, max_length=60)

    # Mpesa
    paybill: Optional[str] = None
    paybill_account: Optional[str] = None
    till_number: Optional[str] = None
    mpesa_phone: Optional[str] = None

    # Bank
    bank_name: Optional[str] = None
    bank_branch: Optional[str] = None
    bank_account_name: Optional[str] = None
    bank_account_number: Optional[str] = None

    is_default: bool = False

    model_config = ConfigDict(from_attributes=True)


class PayoutCreate(PayoutBase):
    pass


class PayoutUpdate(BaseModel):
    label: Optional[str] = None
    # Mpesa
    paybill: Optional[str] = None
    paybill_account: Optional[str] = None
    till_number: Optional[str] = None
    mpesa_phone: Optional[str] = None
    # Bank
    bank_name: Optional[str] = None
    bank_branch: Optional[str] = None
    bank_account_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    is_default: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class PayoutOut(PayoutBase):
    id: int
    created_at: datetime
