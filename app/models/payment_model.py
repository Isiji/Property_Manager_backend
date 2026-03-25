# app/models/payment_model.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Numeric,
    Date,
    DateTime,
    Enum,
    Index,
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    overdue = "overdue"
    failed = "failed"


class ChargeStatus(str, enum.Enum):
    unpaid = "unpaid"
    paid = "paid"
    overdue = "overdue"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)

    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False, index=True)
    lease_id = Column(Integer, ForeignKey("leases.id"), nullable=True, index=True)

    amount = Column(Numeric(12, 2), nullable=False)

    # Display/start period for this payment
    period = Column(String(7), nullable=False, index=True)

    paid_date = Column(Date, nullable=True)

    reference = Column(String(64), nullable=True, index=True)

    merchant_request_id = Column(String(100), nullable=True, index=True)
    checkout_request_id = Column(String(100), nullable=True, unique=True, index=True)

    payment_method = Column(String(40), nullable=True, default="M-Pesa")

    allocation_mode = Column(String(30), nullable=True, default="manual")
    selected_periods_json = Column(String, nullable=True)

    # stores mpesa metadata json
    notes = Column(String, nullable=True)

    status = Column(Enum(PaymentStatus), default=PaymentStatus.pending, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_payments_reference_not_null", "reference"),
        Index("ix_payments_checkout_request_id_not_null", "checkout_request_id"),
        Index("ix_payments_lease_created", "lease_id", "created_at"),
        Index("ix_payments_tenant_created", "tenant_id", "created_at"),
    )

    tenant = relationship("Tenant", back_populates="payments")
    unit = relationship("Unit", back_populates="payments")
    lease = relationship("Lease", back_populates="payments")
    allocations = relationship(
        "PaymentAllocation",
        back_populates="payment",
        cascade="all, delete-orphan",
        order_by="PaymentAllocation.period",
    )


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"

    id = Column(Integer, primary_key=True, index=True)

    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False, index=True)
    lease_id = Column(Integer, ForeignKey("leases.id"), nullable=True, index=True)

    period = Column(String(7), nullable=False, index=True)
    amount_applied = Column(Numeric(12, 2), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_payment_allocations_payment_period", "payment_id", "period"),
        Index("ix_payment_allocations_lease_period", "lease_id", "period"),
        Index("ix_payment_allocations_tenant_period", "tenant_id", "period"),
    )

    payment = relationship("Payment", back_populates="allocations")
    tenant = relationship("Tenant")
    unit = relationship("Unit")
    lease = relationship("Lease")


class ServiceCharge(Base):
    __tablename__ = "service_charges"

    id = Column(Integer, primary_key=True, index=True)

    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False, index=True)

    description = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    due_date = Column(Date, nullable=False)

    status = Column(Enum(ChargeStatus), default=ChargeStatus.unpaid, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant", back_populates="service_charges")
    unit = relationship("Unit", back_populates="service_charges")