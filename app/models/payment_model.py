from sqlalchemy import Column, Integer, String, ForeignKey, Numeric, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from ..database import Base

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    service_type = Column(String, nullable=False)  # rent, water, garbage, etc.
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String, default="paid")  # paid, pending, overdue
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="payments")
    unit = relationship("Unit", back_populates="payments")

class ServiceCharge(Base):
    __tablename__ = "service_charges"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    description = Column(String, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    due_date = Column(DateTime, nullable=False)
    status = Column(String, default="unpaid")  # unpaid, paid, overdue
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="service_charges")
    unit = relationship("Unit", back_populates="service_charges")