# app/routers/lease_router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.dependencies import get_db
from app.schemas.lease_schema import LeaseCreate, LeaseUpdate, LeaseOut
from app.crud import lease_crud

router = APIRouter(prefix="/leases", tags=["Leases"])


@router.post("/", response_model=LeaseOut)
def create_lease(payload: LeaseCreate, db: Session = Depends(get_db)):
    if payload.rent_amount is None:
        raise HTTPException(status_code=400, detail="rent_amount is required")
    lease = lease_crud.create_lease(db, payload)
    return lease


@router.get("/{lease_id}", response_model=LeaseOut)
def read_lease(lease_id: int, db: Session = Depends(get_db)):
    lease = lease_crud.get_lease(db, lease_id)
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    return lease


@router.get("/", response_model=List[LeaseOut])
def list_leases(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return lease_crud.list_leases(db, skip, limit)


@router.put("/{lease_id}", response_model=LeaseOut)
def update_lease(lease_id: int, payload: LeaseUpdate, db: Session = Depends(get_db)):
    lease = lease_crud.update_lease(db, lease_id, payload)
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    return lease


@router.patch("/{lease_id}/end", response_model=LeaseOut)
def end_lease(lease_id: int, db: Session = Depends(get_db)):
    lease = lease_crud.end_lease(db, lease_id)
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    return lease


@router.get("/active/by-unit/{unit_id}", response_model=Optional[LeaseOut])
def active_by_unit(unit_id: int, db: Session = Depends(get_db)):
    return lease_crud.active_lease_for_unit(db, unit_id)


@router.get("/active/by-tenant/{tenant_id}", response_model=Optional[LeaseOut])
def active_by_tenant(tenant_id: int, db: Session = Depends(get_db)):
    return lease_crud.active_lease_for_tenant(db, tenant_id)
