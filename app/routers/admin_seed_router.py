# app/routers/admin_seed_router.py (optional utility)
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.dependencies import get_db
from app import models

router = APIRouter(prefix="/admin/seed", tags=["Admin/Seed"])

@router.post("/maintenance_statuses")
def seed_statuses(db: Session = Depends(get_db)):
    needed = ["open", "in_progress", "resolved", "closed"]
    created = 0
    for name in needed:
        exists = db.query(models.MaintenanceStatus).filter(models.MaintenanceStatus.name == name).first()
        if not exists:
            db.add(models.MaintenanceStatus(name=name))
            created += 1
    if created:
        db.commit()
    return {"created": created, "ok": True}
