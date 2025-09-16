# app/schemas/unit.py
from pydantic import BaseModel, ConfigDict
from typing import Optional
from decimal import Decimal

# Input schema
class UnitCreate(BaseModel):
    number: str
    rent_amount: Decimal
    property_id: int

class UnitUpdate(BaseModel):
    number: Optional[str] = None
    rent_amount: Optional[Decimal] = None

# Output schema
class UnitOut(BaseModel):
    id: int
    number: str
    rent_amount: Decimal
    property_id: int

    class Config:
        model_config = ConfigDict(from_attributes=True)