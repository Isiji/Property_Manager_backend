from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session

from app import models


def allocate_payment(
    db: Session,
    *,
    payment: models.Payment,
    lease: models.Lease,
    periods: list[str],
):
    rent = Decimal(str(lease.rent_amount or 0))
    remaining = Decimal(str(payment.amount))

    allocations = []

    for period in periods:
        if remaining <= 0:
            break

        # total already allocated for this period
        existing = (
            db.query(models.PaymentAllocation)
            .filter(models.PaymentAllocation.lease_id == lease.id)
            .filter(models.PaymentAllocation.period == period)
            .all()
        )

        already_paid = sum([Decimal(str(x.amount_applied)) for x in existing])
        balance = rent - already_paid

        if balance <= 0:
            continue

        apply_amt = min(balance, remaining)

        alloc = models.PaymentAllocation(
            payment_id=payment.id,
            tenant_id=payment.tenant_id,
            unit_id=payment.unit_id,
            lease_id=payment.lease_id,
            period=period,
            amount_applied=apply_amt,
        )

        db.add(alloc)
        allocations.append(alloc)

        remaining -= apply_amt

    return allocations