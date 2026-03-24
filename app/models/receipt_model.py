from sqlalchemy import Column, Integer, String, ForeignKey, Numeric, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class PaymentReceipt(Base):
    __tablename__ = "payment_receipts"

    id = Column(Integer, primary_key=True, index=True)

    receipt_number = Column(String, unique=True, index=True)

    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False, index=True)

    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)

    landlord_id = Column(Integer, ForeignKey("landlords.id"), nullable=True)
    manager_id = Column(Integer, ForeignKey("property_managers.id"), nullable=True)

    amount = Column(Numeric(12, 2), nullable=False)

    # legacy display period
    period = Column(String(7), nullable=True)

    # breakdown for multi-month / partial receipts
    allocations_json = Column(String, nullable=True)

    payment_reference = Column(String, nullable=True)
    payment_method = Column(String, default="M-Pesa")

    pdf_path = Column(String, nullable=True)

    issued_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    payment = relationship("Payment")
    tenant = relationship("Tenant")
    unit = relationship("Unit")
    property = relationship("Property")