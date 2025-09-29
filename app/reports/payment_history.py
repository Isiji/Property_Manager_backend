from sqlalchemy.orm import Session, joinedload
from typing import List
from datetime import datetime

from app.models.payment_model import Payment
from app.schemas.payment_schema import PaymentOut


def get_tenant_payment_history(db: Session, tenant_id: int, start_date: datetime = None, end_date: datetime = None) -> List[PaymentOut]:
    """
    Returns the full payment history for a tenant.
    Can be filtered by date range (optional).
    """
    query = (
        db.query(Payment)
        .options(
            joinedload(Payment.unit),   # eager load unit
            joinedload(Payment.lease),  # eager load lease
        )
        .filter(Payment.tenant_id == tenant_id)
    )

    if start_date:
        query = query.filter(Payment.date >= start_date)
    if end_date:
        query = query.filter(Payment.date <= end_date)

    payments = query.order_by(Payment.date.desc()).all()
    return payments
