from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date, datetime

class LeaseBase(BaseModel):
    tenant_id: int
    unit_id: int
    # Use date (not datetime) to avoid "date_from_datetime_inexact"
    start_date: date=Field(default_factory=date.today)
    end_date: Optional[date] = None
    # rent could be null for legacy rows; keep it optional in API
    rent_amount: Optional[float] = None
    # Optional in payload; defaults to 1 in CRUD
    active: Optional[int] = 1

    @field_validator("start_date", "end_date", mode="before")
    def parse_dates(cls, v):
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, str) and "T" in v:
            return datetime.fromisoformat(v).date()
        return v

class LeaseCreate(LeaseBase):
    pass

class LeaseUpdate(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    rent_amount: Optional[float] = None
    active: Optional[int] = None

class LeaseOut(BaseModel):
    id: int
    tenant_id: int
    unit_id: int
    start_date: date
    end_date: Optional[date] = None
    rent_amount: Optional[float] = None
    active: int

    class Config:
        from_attributes = True
