# app/routers/report_router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from app.dependencies import get_db
from app.crud import report_crud

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.get("/landlord/{landlord_id}/monthly-summary")
def landlord_monthly_summary(
    landlord_id: int,
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    Returns monthly Expected / Received / Pending + per-property breakdown + arrears list.
    If year/month omitted, uses current server date.
    """
    from datetime import date
    today = date.today()
    y = year or today.year
    m = month or today.month
    try:
        return report_crud.landlord_monthly_summary(db, landlord_id, y, m)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
