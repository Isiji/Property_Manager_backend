from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

# -----------------------------
# Base
# -----------------------------
class MaintenanceRequestBase(BaseModel):
    tenant_id: int
    unit_id: int
    description: str
    status_id: int

# -----------------------------
# Create / Update
# -----------------------------
class MaintenanceRequestCreate(MaintenanceRequestBase):
    pass

class MaintenanceRequestUpdate(BaseModel):
    description: Optional[str] = None
    status_id: Optional[int] = None

# -----------------------------
# Output
# -----------------------------
class MaintenanceRequestOut(MaintenanceRequestBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        model_config = ConfigDict(from_attributes=True)

# -----------------------------
# Status
# -----------------------------
class MaintenanceStatusBase(BaseModel):
    name: str

class MaintenanceStatusCreate(MaintenanceStatusBase):
    pass

class MaintenanceStatusOut(MaintenanceStatusBase):
    id: int

    class Config:
        model_config = ConfigDict(from_attributes=True)
