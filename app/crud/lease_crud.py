from sqlalchemy.orm import Session
from .. import models, schemas
from fastapi import HTTPException

def create_lease(db: Session, lease: schemas.LeaseCreate):
    # Check if unit already has an active lease
    active_lease = db.query(models.Lease).filter(
        models.Lease.unit_id == lease.unit_id,
        models.Lease.active == 1
    ).first()
    if active_lease:
        raise HTTPException(status_code=400, detail="Unit already has an active lease")

    db_lease = models.Lease(**lease.dict())
    db.add(db_lease)
    db.commit()
    db.refresh(db_lease)
    return db_lease

def get_leases(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Lease).offset(skip).limit(limit).all()

def get_lease(db: Session, lease_id: int):
    lease = db.query(models.Lease).filter(models.Lease.id == lease_id).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    return lease

def update_lease(db: Session, lease_id: int, lease_update: schemas.LeaseUpdate):
    lease = get_lease(db, lease_id)
    for key, value in lease_update.dict(exclude_unset=True).items():
        setattr(lease, key, value)
    db.commit()
    db.refresh(lease)
    return lease

def delete_lease(db: Session, lease_id: int):
    lease = get_lease(db, lease_id)
    db.delete(lease)
    db.commit()
    return {"detail": "Lease deleted successfully"}
