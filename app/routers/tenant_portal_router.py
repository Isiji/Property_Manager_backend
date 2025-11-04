# app/routers/tenant_portal.py
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, joinedload
import jwt  # PyJWT

from app.database import get_db
from app import models

# ───────────────────────────────────────────────────────────────────────────────
# Auth helpers: decode JWT and fetch current tenant
# Adjust imports if your settings live elsewhere.
# You need: settings.SECRET_KEY, settings.ALGORITHM
# ───────────────────────────────────────────────────────────────────────────────
try:
    from app.core.config import settings
    SECRET_KEY = settings.SECRET_KEY
    ALGORITHM = getattr(settings, "ALGORITHM", "HS256")
except Exception:
    # Fallback: ONLY for local/dev if you don't have settings wired.
    # Replace with your real secret/algorithm if needed.
    SECRET_KEY = "CHANGE_ME_SECRET"
    ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def _decode_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "sub": payload.get("sub"),
            "role": payload.get("role"),
            "exp": payload.get("exp"),
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

def get_current_tenant(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> models.Tenant:
    info = _decode_token(token)
    if info.get("role") != "tenant":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant role required")
    tenant_id = info.get("sub")
    if tenant_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token: no sub")
    t = (
        db.query(models.Tenant)
        .options(
            joinedload(models.Tenant.leases).joinedload(models.Lease.unit).joinedload(models.Unit.property),
            joinedload(models.Tenant.payments),
        )
        .filter(models.Tenant.id == int(tenant_id))
        .first()
    )
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return t

# ───────────────────────────────────────────────────────────────────────────────
# Router
# ───────────────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/tenants/me", tags=["Tenant Portal"])

def _yyyymm(dt: date | datetime) -> str:
    return f"{dt.year}-{str(dt.month).zfill(2)}"

@router.get("/overview")
def tenant_overview(current: models.Tenant = Depends(get_current_tenant), db: Session = Depends(get_db)) -> Dict[str, Any]:
    # Active lease (if any)
    active_lease: Optional[models.Lease] = None
    for l in current.leases:
        if l.active == 1:
            active_lease = l
            break

    unit_info: Dict[str, Any] = {}
    lease_info: Dict[str, Any] = {}
    this_month: Dict[str, Any] = {"expected": 0, "received": 0, "balance": 0, "paid": False}

    if active_lease:
        unit = active_lease.unit
        unit_info = {
            "id": unit.id if unit else None,
            "number": getattr(unit, "number", None),
            "property_id": getattr(unit, "property_id", None),
            "property_name": getattr(unit.property, "name", None) if unit and unit.property else None,
        }
        lease_info = {
            "id": active_lease.id,
            "rent_amount": float(active_lease.rent_amount) if active_lease.rent_amount is not None else None,
            "start_date": active_lease.start_date.isoformat() if active_lease.start_date else None,
            "end_date": active_lease.end_date.isoformat() if active_lease.end_date else None,
            "active": int(active_lease.active),
        }

        # Payments for current period (YYYY-MM)
        period = _yyyymm(date.today())
        q = (
            db.query(models.Payment)
            .filter(models.Payment.lease_id == active_lease.id)
            .filter(models.Payment.period == period)
        )
        received = sum(float(p.amount or 0) for p in q.all())
        expected = float(active_lease.rent_amount or 0)
        balance = round(expected - received, 2)
        this_month = {
            "period": period,
            "expected": expected,
            "received": received,
            "balance": balance,
            "paid": received >= expected and expected > 0,
        }

    return {
        "tenant": {
            "id": current.id,
            "name": current.name,
            "phone": current.phone,
            "email": current.email,
            "id_number": getattr(current, "id_number", None),
        },
        "unit": unit_info,
        "lease": lease_info,
        "this_month": this_month,
    }

@router.get("/payments")
def tenant_payments(current: models.Tenant = Depends(get_current_tenant), db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    # Gather all payments for all leases of this tenant (usually just the active)
    lease_ids = [l.id for l in current.leases]
    if not lease_ids:
        return []
    rows = (
        db.query(models.Payment)
        .filter(models.Payment.tenant_id == current.id)  # if your Payment carries tenant_id
        .order_by(models.Payment.paid_date.desc().nullslast())
        .all()
    )
    # Fallback if tenant_id not present on Payment: filter by lease_ids
    if not rows:
        rows = (
            db.query(models.Payment)
            .filter(models.Payment.lease_id.in_(lease_ids))
            .order_by(models.Payment.paid_date.desc().nullslast())
            .all()
        )

    out = []
    for p in rows:
        out.append({
            "id": p.id,
            "lease_id": p.lease_id,
            "period": p.period,
            "amount": float(p.amount or 0),
            "paid_date": p.paid_date.isoformat() if p.paid_date else None,
            "reference": getattr(p, "reference", None),
        })
    return out

@router.get("/maintenance")
def tenant_maintenance(current: models.Tenant = Depends(get_current_tenant), db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    rows = (
        db.query(models.MaintenanceRequest)
        .filter(models.MaintenanceRequest.tenant_id == current.id)
        .order_by(models.MaintenanceRequest.created_at.desc().nullslast())
        .all()
    )
    out = []
    for m in rows:
        out.append({
            "id": m.id,
            "title": m.title,
            "description": m.description,
            "status": m.status,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        })
    return out

@router.post("/maintenance", status_code=201)
def create_maintenance(payload: Dict[str, Any], current: models.Tenant = Depends(get_current_tenant), db: Session = Depends(get_db)) -> Dict[str, Any]:
    title = (payload.get("title") or "").strip()
    description = (payload.get("description") or "").strip() or None
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")

    req = models.MaintenanceRequest(
        tenant_id=current.id,
        property_id=getattr(current, "property_id", None),
        unit_id=getattr(current, "unit_id", None),
        title=title,
        description=description,
        status="open",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return {
        "id": req.id,
        "title": req.title,
        "description": req.description,
        "status": req.status,
        "created_at": req.created_at.isoformat() if req.created_at else None,
    }

@router.get("/profile")
def tenant_profile(current: models.Tenant = Depends(get_current_tenant)) -> Dict[str, Any]:
    return {
        "id": current.id,
        "name": current.name,
        "phone": current.phone,
        "email": current.email,
        "property_id": current.property_id,
        "unit_id": current.unit_id,
        "id_number": getattr(current, "id_number", None),
    }

@router.post("/pay")
def pay_this_month(current: models.Tenant = Depends(get_current_tenant)) -> Dict[str, Any]:
    # Stub: integrate with your PSP here.
    return {"message": "Payment initiation stubbed. Integrate with your PSP here."}
