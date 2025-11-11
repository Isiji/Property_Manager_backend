from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class MaintenanceStatusOut(BaseModel):
    id: int
    name: str
    class Config:
        model_config = ConfigDict(from_attributes=True)

# existing request models (keep yours; below is a minimal shape)
class MaintenanceRequestCreate(BaseModel):
    tenant_id: int
    unit_id: int
    description: str
    status_id: int

class MaintenanceRequestUpdate(BaseModel):
    description: Optional[str] = None
    status_id: Optional[int] = None

class MaintenanceRequestOut(BaseModel):
    id: int
    tenant_id: int
    unit_id: int
    description: str
    status_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        model_config = ConfigDict(from_attributes=True)
