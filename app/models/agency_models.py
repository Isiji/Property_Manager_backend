from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class AgencyAgentLink(Base):
    """
    Links an AGENCY org (property_managers.type='agency') to an already-registered manager org
    (usually type='individual', but could be another org if you allow).
    """
    __tablename__ = "agency_agent_links"

    id = Column(Integer, primary_key=True, index=True)

    agency_manager_id = Column(Integer, ForeignKey("property_managers.id"), nullable=False, index=True)
    agent_manager_id = Column(Integer, ForeignKey("property_managers.id"), nullable=False, index=True)

    status = Column(String, nullable=False, default="active")  # active | inactive
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("agency_manager_id", "agent_manager_id", name="uq_agency_agent_link"),
    )


class PropertyAgentAssignment(Base):
    """
    Assigns a staff user (ManagerUser) to a property for accountability/workload.

    This is separate from property.manager_id (which stays as the org that manages the property).
    """
    __tablename__ = "property_agent_assignments"

    id = Column(Integer, primary_key=True, index=True)

    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)
    assignee_user_id = Column(Integer, ForeignKey("manager_users.id"), nullable=False, index=True)
    assigned_by_user_id = Column(Integer, ForeignKey("manager_users.id"), nullable=False, index=True)

    active = Column(Boolean, nullable=False, default=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("property_id", "assignee_user_id", "active", name="uq_property_assignment_active"),
    )
