from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.dependencies import get_db
from app.schemas.lease_schema import LeaseCreate, LeaseUpdate, LeaseOut
from app.crud import lease_crud

router = APIRouter(prefix="/leases", tags=["Leases"])

@router.post("/", response_model=LeaseOut)
def create_lease(payload: LeaseCreate, db: Session = Depends(get_db)):
    try:
        lease = lease_crud.create_lease(db, payload)
        return lease
    except Exception as e:
        print("❌ create_lease error:", e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{lease_id}", response_model=LeaseOut)
def read_lease(lease_id: int, db: Session = Depends(get_db)):
    lease = lease_crud.get_lease(db, lease_id)
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    return lease

@router.put("/{lease_id}", response_model=LeaseOut)
def update_lease(lease_id: int, payload: LeaseUpdate, db: Session = Depends(get_db)):
    lease = lease_crud.update_lease(db, lease_id, payload)
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    return lease

@router.delete("/{lease_id}", response_model=dict)
def delete_lease(lease_id: int, db: Session = Depends(get_db)):
    ok = lease_crud.delete_lease(db, lease_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Lease not found")
    return {"ok": True}
