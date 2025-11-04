from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict

from app.dependencies import get_db
from app.models.property_models import Property, Unit

router = APIRouter(prefix="/properties/by-code", tags=["Properties"])

@router.get("/{property_code}/units", response_model=List[Dict])
def list_units_for_property_code(property_code: str, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.property_code == property_code).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Invalid property code")

    rows = (
        db.query(Unit)
        .filter(Unit.property_id == prop.id)
        .order_by(Unit.number.asc())
        .all()
    )
    return [{"id": u.id, "label": (u.number or "").strip()} for u in rows]
