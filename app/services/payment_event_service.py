# app/services/payment_event_service.py
from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.services.payment_handler import handle_payment_success as _handle_payment_success


def handle_payment_success(db: Session, payment: models.Payment):
    return _handle_payment_success(db, payment)