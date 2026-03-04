# app/schemas/admin_dashboard_schema.py
from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict


class AdminCounts(BaseModel):
    properties: int
    units: int
    occupied_units: int
    vacant_units: int
    tenants: int
    active_leases: int
    maintenance_open: int
    maintenance_in_progress: int
    maintenance_resolved: int

    model_config = ConfigDict(from_attributes=True)


class AdminCollections(BaseModel):
    period: str  # YYYY-MM
    collected_total: float
    paid_count: int
    unpaid_count: int

    model_config = ConfigDict(from_attributes=True)


class PropertySummaryRow(BaseModel):
    id: int
    name: str
    address: str
    property_code: str
    landlord_id: int
    manager_id: Optional[int] = None

    units: int
    occupied_units: int
    vacant_units: int

    model_config = ConfigDict(from_attributes=True)


class FinancePropertyRow(BaseModel):
    property_id: int
    property_name: str
    property_code: str

    period: str
    expected_rent: float
    received_rent: float
    balance: float

    paid_leases: int
    unpaid_leases: int

    model_config = ConfigDict(from_attributes=True)


class AdminOverviewOut(BaseModel):
    counts: AdminCounts
    collections: AdminCollections
    properties_top: List[PropertySummaryRow]  # latest few / most recent

    model_config = ConfigDict(from_attributes=True)