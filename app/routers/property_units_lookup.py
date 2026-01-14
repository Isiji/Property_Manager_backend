# app/routers/property_units_lookup.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict

from app.dependencies import get_db
from app.models.property_models import Property, Unit

router = APIRouter(prefix="/properties/by-code", tags=["Properties"])

@router.get("/{property_code}/units", response_model=List[Dict])
def list_units_for_property_code(
    property_code: str,
    q: str | None = Query(default=None, description="Optional search text for unit number (autocomplete)"),
    only_vacant: bool = Query(default=False, description="Return only vacant units"),
    db: Session = Depends(get_db),
):
    """
    Returns units for a property code.
    - Case-insensitive property_code match
    - Optional q for autocomplete suggestions (case-insensitive startswith/contains)
    - Returns BOTH 'number' and 'label' keys for compatibility with Flutter UI
    """
    code = (property_code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="Property code is required")

    # Case-insensitive match for property code
    prop = (
        db.query(Property)
        .filter(func.upper(func.trim(Property.property_code)) == func.upper(func.trim(code)))
        .first()
    )
    if not prop:
        raise HTTPException(status_code=404, detail="Invalid property code")

    query = db.query(Unit).filter(Unit.property_id == prop.id)

    if only_vacant:
        query = query.filter(func.coalesce(Unit.occupied, 0) == 0)

    if q:
        needle = (q or "").strip()
        if needle:
            # Case-insensitive match against unit.number
            query = query.filter(
                func.lower(func.trim(Unit.number)).like(func.lower(func.trim(needle)) + "%")
            )

    rows = query.order_by(func.lower(func.trim(Unit.number)).asc()).all()

    # Return both keys so your Flutter can read either `label` or `number`
    return [
        {
            "id": u.id,
            "number": (u.number or "").strip(),
            "label": (u.number or "").strip(),
            "occupied": int(getattr(u, "occupied", 0) or 0),
        }
        for u in rows
    ]
