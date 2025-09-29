from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from ..database import Base

class MaintenanceRequest(Base):
    __tablename__ = "maintenance_requests"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False, index=True)
    description = Column(Text, nullable=False)  # use Text for longer requests
    status_id = Column(Integer, ForeignKey("maintenance_status.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant", back_populates="maintenance_requests")
    unit = relationship("Unit", back_populates="maintenance_requests")
    status = relationship("MaintenanceStatus", back_populates="requests")


class MaintenanceStatus(Base):
    __tablename__ = "maintenance_status"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)  # e.g. "open", "in_progress", "resolved"

    requests = relationship("MaintenanceRequest", back_populates="status", cascade="all, delete-orphan")
