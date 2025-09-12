from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime

class MaintenanceRequest(Base):
    __tablename__ = "maintenance_requests"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    description = Column(String, nullable=False)
    status_id = Column(Integer, ForeignKey("maintenance_status.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="maintenance_requests")
    unit = relationship("Unit", back_populates="maintenance_requests")
    status = relationship("MaintenanceStatus", back_populates="requests")


class MaintenanceStatus(Base):
    __tablename__ = "maintenance_status"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # e.g., open, in_progress, resolved

    requests = relationship("MaintenanceRequest", back_populates="status", cascade="all, delete-orphan")
