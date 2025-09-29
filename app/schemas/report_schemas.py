from pydantic import BaseModel, ConfigDict
from decimal import Decimal
from typing import List, Optional
from datetime import datetime


# ---------------- RENT COLLECTION ----------------
class RentCollectionSummary(BaseModel):
    property_id: int
    property_name: str
    total_rent_collected: Decimal


# ---------------- SERVICE CHARGES ----------------
class ServiceChargeSummary(BaseModel):
    property_id: int
    property_name: str
    service_type: str
    total_amount: Decimal


# ---------------- OCCUPANCY ----------------
class OccupancySummary(BaseModel):
    property_id: int
    property_name: str
    total_units: int
    occupied_units: int
    vacant_units: int
    occupancy_rate: float  # percentage

class TenantPaymentReport(BaseModel):
    id: int
    unit_id: int
    service_type: str
    amount: Decimal
    status: str
    created_at: datetime

    class Config:
        model_config = ConfigDict(from_attributes=True)

class MonthlyIncome(BaseModel):
    month: str  # e.g. "2025-09"
    total_income: Decimal
    outstanding_balance: Decimal

    class Config:
        model_config = ConfigDict(from_attributes=True)


class LandlordIncomeReport(BaseModel):
    property_id: int
    property_name: str
    monthly_income: List[MonthlyIncome]

    class Config:
        model_config = ConfigDict(from_attributes=True)


