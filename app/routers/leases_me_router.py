# app/routers/leases_me_router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.routers.tenant_portal_router import get_current_tenant

router = APIRouter(tags=["Tenant Portal"])

@router.get("/leases/me")
def leases_me(current: models.Tenant = Depends(get_current_tenant), db: Session = Depends(get_db)):
    active = next((l for l in current.leases if int(l.active or 0) == 1), None)
    if not active:
        raise HTTPException(status_code=404, detail="No active lease")
    return {
        "id": active.id,
        "tenant_id": active.tenant_id,
        "unit_id": active.unit_id,
        "rent_amount": float(active.rent_amount or 0),
        "start_date": active.start_date.date().isoformat() if active.start_date else None,
        "end_date": active.end_date.date().isoformat() if active.end_date else None,
        "active": int(active.active or 0),
    }
