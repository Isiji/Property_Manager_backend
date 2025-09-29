# app/services/reminder_service.py
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from fastapi import Depends
from app.database import SessionLocal
from app import crud, models
import logging

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Notification stubs ---
def send_email(to_email: str, subject: str, body: str):
    # Implement actual email sending (e.g., SMTP or SendGrid)
    logger.info(f"Email sent to {to_email} | {subject} | {body}")

def send_sms(to_phone: str, message: str):
    # Implement actual SMS sending (e.g., Twilio, Africa’s Talking)
    logger.info(f"SMS sent to {to_phone} | {message}")

# --- Reminder Jobs ---
def rent_due_reminder():
    db: Session = next(get_db())
    today = datetime.utcnow().date()
    leases = db.query(models.Lease).filter(
        models.Lease.end_date >= today,
        models.Lease.active == 1
    ).all()

    for lease in leases:
        # Example: remind 3 days before rent due
        if lease.next_rent_due_date and (lease.next_rent_due_date - today).days <= 3:
            tenant = lease.tenant
            message = f"Hello {tenant.name}, your rent for unit {lease.unit_id} is due on {lease.next_rent_due_date}."
            send_sms(tenant.phone, message)
            if tenant.email:
                send_email(tenant.email, "Rent Due Reminder", message)

def lease_expiry_reminder():
    db: Session = next(get_db())
    today = datetime.utcnow().date()
    leases = db.query(models.Lease).filter(
        models.Lease.end_date >= today,
        models.Lease.active == 1
    ).all()

    for lease in leases:
        # Example: remind 7 days before lease expires
        if (lease.end_date - today).days <= 7:
            tenant = lease.tenant
            message = f"Hello {tenant.name}, your lease for unit {lease.unit_id} expires on {lease.end_date}. Please contact your landlord to renew."
            send_sms(tenant.phone, message)
            if tenant.email:
                send_email(tenant.email, "Lease Expiry Reminder", message)

def maintenance_status_reminder():
    db: Session = next(get_db())
    open_requests = db.query(models.MaintenanceRequest).join(models.MaintenanceStatus).filter(
        models.MaintenanceStatus.name != "resolved"
    ).all()

    for req in open_requests:
        tenant = req.tenant
        message = f"Hello {tenant.name}, your maintenance request for unit {req.unit_id} is still {req.status.name}. We are working on it."
        send_sms(tenant.phone, message)
        if tenant.email:
            send_email(tenant.email, "Maintenance Update", message)

def overdue_balance_reminder():
    db: Session = next(get_db())
    today = datetime.utcnow().date()
    tenants = db.query(models.Tenant).all()

    for tenant in tenants:
        total_due = sum([payment.amount for payment in tenant.payments if payment.date.date() < today])
        if total_due > 0:
            message = f"Hello {tenant.name}, your outstanding balance is {total_due}. Please pay to avoid penalties."
            send_sms(tenant.phone, message)
            if tenant.email:
                send_email(tenant.email, "Outstanding Balance Reminder", message)

# --- Start Scheduler ---
def start_scheduler():
    # Run every day at 8 AM UTC
    scheduler.add_job(rent_due_reminder, "cron", hour=8, minute=0)
    scheduler.add_job(lease_expiry_reminder, "cron", hour=8, minute=0)
    scheduler.add_job(maintenance_status_reminder, "cron", hour=8, minute=0)
    scheduler.add_job(overdue_balance_reminder, "cron", hour=8, minute=0)

    scheduler.start()
    logger.info("Reminder scheduler started.")
