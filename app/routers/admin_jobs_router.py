# app/routers/admin_jobs_router.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from app.dependencies import get_db
from app import models
from app.schemas.notification_schema import NotificationCreate
from app.services import notification_service

router = APIRouter(prefix="/admin/jobs", tags=["Admin/Jobs"])

@router.post("/rent_reminders")
def rent_reminders(db: Session = Depends(get_db)):
    """
    Finds active leases with balance > 0 for the current month and notifies tenants.
    Call daily via scheduler. Adjust day window as you like.
    """
    today = datetime.utcnow()
    period = f"{today.year}-{str(today.month).zfill(2)}"

    q = db.query(models.Lease).filter(models.Lease.active == 1)
    leases = q.all()

    sent = 0
    for lease in leases:
        expected = float(lease.rent_amount or 0)
        if expected <= 0:
            continue
        paid = sum(float(p.amount or 0) for p in (lease.payments or []) if p.period == period)
        balance = expected - paid
        if balance > 0 and lease.tenant_id:
            notification_service.send_notification(
                db,
                NotificationCreate(
                    user_id=lease.tenant_id,
                    user_type="tenant",
                    title="Rent reminder",
                    message=f"Your rent for {period} is due. Balance: KES {balance:,.0f}",
                    channel="inapp",
                ),
            )
            sent += 1

    return {"ok": True, "period": period, "sent": sent}
