from pydantic import BaseModel, EmailStr
from typing import Optional, List


class ManagerUserCreate(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None
    password: str
    id_number: Optional[str] = None
    staff_role: Optional[str] = "manager_staff"  # manager_admin | manager_staff | finance


class ManagerUserOut(BaseModel):
    id: int
    manager_id: int
    name: str
    phone: str
    email: Optional[str] = None
    id_number: Optional[str] = None
    staff_role: str

    class Config:
        from_attributes = True


class StaffDeactivateOut(BaseModel):
    id: int
    active: bool


class LinkAgentRequest(BaseModel):
    """
    Link an already-registered manager ORG to this agency ORG.
    Provide ONE of:
    - agent_manager_id
    - agent_phone (recommended)
    """
    agent_manager_id: Optional[int] = None
    agent_phone: Optional[str] = None


class LinkAgentOut(BaseModel):
    id: int
    agency_manager_id: int
    agent_manager_id: int
    status: str


class AssignPropertyOut(BaseModel):
    id: int
    property_id: int
    assignee_user_id: int
    assigned_by_user_id: int
    active: bool
