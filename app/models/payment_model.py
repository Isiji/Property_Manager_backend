# app/models/payment_models.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Numeric,
    Date,
    DateTime,
    Enum,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


# --------------------------
# Enums
# --------------------------
class PaymentStatus(str, enum.Enum):
    pending = "pending"   # created / initiated, awaiting confirmation
    paid = "paid"         # fully paid / confirmed
    overdue = "overdue"   # not used by STK itself, but useful for monthly tagging


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

    # Links
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False, index=True)
    lease_id = Column(Integer, ForeignKey("leases.id"), nullable=True, index=True)  # optional, but recommended

    # Accounting
    amount = Column(Numeric(12, 2), nullable=False)

    # Monthly tagging (used by UI to know if a month's rent is paid)
    # Example: "2025-10"
    period = Column(String(7), nullable=False, index=True)  # YYYY-MM
    paid_date = Column(Date, nullable=True)  # actual paid day (YYYY-MM-DD)

    # Provider reference / receipt (M-Pesa receipt, bank ref, etc.)
    reference = Column(String(64), nullable=True, index=True)

    # Status and timestamps
    status = Column(Enum(PaymentStatus), default=PaymentStatus.pending, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        # prevent duplicate payment rows for the same lease+month
        UniqueConstraint("lease_id", "period", name="uq_payments_lease_period"),
        Index("ix_payments_reference_not_null", "reference"),
    )

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

    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False, index=True)

    description = Column(String, nullable=False)  # e.g. water, garbage, security
    amount = Column(Numeric(12, 2), nullable=False)

    # Due date for the charge (not the payment date)
    due_date = Column(Date, nullable=False)

    status = Column(Enum(ChargeStatus), default=ChargeStatus.unpaid, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    tenant = relationship("Tenant", back_populates="service_charges")
    unit = relationship("Unit", back_populates="service_charges")
