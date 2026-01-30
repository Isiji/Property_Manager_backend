from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.database import Base


class AgencyAgentLink(Base):
    """
    Links an AGENCY org (property_managers.type='agency') to an already-registered manager org.
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

    IMPORTANT:
    We allow history (many rows), but we enforce ONLY ONE ACTIVE assignment per property.
    That should be done using a PARTIAL UNIQUE INDEX: unique(property_id) WHERE active IS TRUE
    """
    __tablename__ = "property_agent_assignments"

    id = Column(Integer, primary_key=True, index=True)

    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)
    assignee_user_id = Column(Integer, ForeignKey("manager_users.id"), nullable=False, index=True)
    assigned_by_user_id = Column(Integer, ForeignKey("manager_users.id"), nullable=False, index=True)

    active = Column(Boolean, nullable=False, default=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        # ✅ Only one active row per property, but allow unlimited inactive history.
        Index(
            "ux_property_agent_assignment_one_active_per_property",
            "property_id",
            unique=True,
            postgresql_where=(active.is_(True)),
        ),
    )


class PropertyExternalManagerAssignment(Base):
    """
    Assign an EXTERNAL manager org (PropertyManager) to an agency-managed property.
    We allow history, but enforce ONLY ONE ACTIVE assignment per property.
    """
    __tablename__ = "property_external_manager_assignments"

    id = Column(Integer, primary_key=True, index=True)

    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)
    agent_manager_id = Column(Integer, ForeignKey("property_managers.id"), nullable=False, index=True)

    assigned_by_user_id = Column(Integer, ForeignKey("manager_users.id"), nullable=False, index=True)

    active = Column(Boolean, nullable=False, default=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        # ✅ Only one active row per property (external), allow history.
        Index(
            "ux_property_external_assignment_one_active_per_property",
            "property_id",
            unique=True,
            postgresql_where=(active.is_(True)),
        ),
    )
