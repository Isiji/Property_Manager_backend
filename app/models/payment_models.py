from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Numeric, Boolean
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    amount = Column(Numeric(10,2), nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    description = Column(String, nullable=True)

    tenant = relationship("Tenant", back_populates="payments")
    unit = relationship("Unit", back_populates="payments")
    lease_id = Column(Integer, ForeignKey("leases.id"), nullable=True)
    lease = relationship("Lease", back_populates="payments")


class ServiceCharge(Base):
    __tablename__ = "service_charges"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    service_type = Column(String, nullable=False)  # water, garbage, security
    amount = Column(Numeric(10,2), nullable=False)
    date = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="service_charges")
    unit = relationship("Unit", back_populates="service_charges")
