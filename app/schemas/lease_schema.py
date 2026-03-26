# app/schemas/lease_schema.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LeaseCreate(BaseModel):
    tenant_id: int
    unit_id: int
    start_date: datetime
    end_date: Optional[datetime] = None
    rent_amount: float = Field(..., gt=0)
    active: Optional[int] = 1
    terms_text: Optional[str] = None
    terms_accepted: Optional[int] = 0
    terms_accepted_at: Optional[datetime] = None


class LeaseUpdate(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    rent_amount: Optional[float] = Field(default=None, gt=0)
    active: Optional[int] = None
    terms_text: Optional[str] = None
    terms_accepted: Optional[int] = None
    terms_accepted_at: Optional[datetime] = None


class LeaseOut(BaseModel):
    id: int
    tenant_id: int
    unit_id: int
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    rent_amount: float
    active: int
    terms_text: Optional[str] = None
    terms_accepted: int
    terms_accepted_at: Optional[datetime] = None

    class Config:
        from_attributes = True