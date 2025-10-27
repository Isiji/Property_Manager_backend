# app/models/payout_models.py
from __future__ import annotations

from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Enum,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class PayoutType(str, enum.Enum):
    mpesa_paybill = "mpesa_paybill"
    mpesa_till = "mpesa_till"
    mpesa_phone = "mpesa_phone"
    bank = "bank"


class LandlordPayout(Base):
    __tablename__ = "landlord_payouts"

    id = Column(Integer, primary_key=True, index=True)

    landlord_id = Column(Integer, ForeignKey("landlords.id", ondelete="CASCADE"), nullable=False)

    # Type of destination
    payout_type = Column(Enum(PayoutType), nullable=False)

    # Common labels
    label = Column(String, nullable=False)  # e.g. "Main Paybill", "Equity Current"

    # M-Pesa fields
    paybill = Column(String, nullable=True)
    paybill_account = Column(String, nullable=True)
    till_number = Column(String, nullable=True)
    mpesa_phone = Column(String, nullable=True)

    # Bank fields
    bank_name = Column(String, nullable=True)
    bank_branch = Column(String, nullable=True)
    bank_account_name = Column(String, nullable=True)
    bank_account_number = Column(String, nullable=True)

    # Flags
    is_default = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    landlord = relationship("Landlord", back_populates="payouts")

    __table_args__ = (
        # A landlord can’t have two *identical* destinations of same type with same core value
        UniqueConstraint(
            "landlord_id",
            "payout_type",
            "paybill",
            "till_number",
            "mpesa_phone",
            "bank_name",
            "bank_account_number",
            name="uq_landlord_payout_unique_combo",
        ),
    )
