# app/models/payment_models.py
from sqlalchemy import Column, Integer, String, ForeignKey, Numeric, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from ..database import Base

# --------------------------
# Enum for payment status
# --------------------------
class PaymentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    overdue = "overdue"

class ChargeStatus(str, enum.Enum):
    unpaid = "unpaid"
    paid = "paid"
    overdue = "overdue"


# ==========================
# Payment Model
# ==========================
class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    lease_id = Column(Integer, ForeignKey("leases.id"), nullable=True)  # 🔑 link to lease
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.pending)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="payments")
    unit = relationship("Unit", back_populates="payments")
    lease = relationship("Lease", back_populates="payments")


# ==========================
# Service Charges
# ==========================
class ServiceCharge(Base):
    __tablename__ = "service_charges"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    description = Column(String, nullable=False)  # e.g. water, garbage, security
    amount = Column(Numeric(10, 2), nullable=False)
    due_date = Column(DateTime, nullable=False)
    status = Column(Enum(ChargeStatus), default=ChargeStatus.unpaid)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="service_charges")
    unit = relationship("Unit", back_populates="service_charges")
