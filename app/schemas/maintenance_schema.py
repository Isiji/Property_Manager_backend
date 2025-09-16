from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class MaintenanceRequestBase(BaseModel):
    tenant_id: int
    unit_id: int
    description: str
    status_id: int  # references MaintenanceStatus

class MaintenanceRequestCreate(MaintenanceRequestBase):
    pass

class MaintenanceRequestUpdate(BaseModel):
    description: Optional[str] = None
    status_id: Optional[int] = None

class MaintenanceRequestOut(MaintenanceRequestBase):
    id: int
    created_at: datetime

    class Config:
        model_config = ConfigDict(from_attributes=True)


class MaintenanceStatusBase(BaseModel):
    name: str  # e.g., open, in_progress, resolved

class MaintenanceStatusCreate(MaintenanceStatusBase):
    pass

class MaintenanceStatusOut(MaintenanceStatusBase):
    id: int

    class Config:
        model_config = ConfigDict(from_attributes=True)
