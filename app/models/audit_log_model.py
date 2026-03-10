from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Scope anchor
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=True, index=True)

    action = Column(String(80), nullable=False)          # e.g. "CREATE_PAYMENT"
    entity_type = Column(String(50), nullable=False)     # e.g. "payment", "tenant"
    entity_id = Column(Integer, nullable=True)
    message = Column(Text, nullable=True)

    # Who did it
    actor_role = Column(String(30), nullable=True)       # super_admin/admin/landlord/manager/tenant
    actor_id = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    property = relationship("Property", lazy="joined")

    __table_args__ = (
        Index("ix_audit_logs_property_created", "property_id", "created_at"),
    )