# app/routers/report_router.py
from fastapi import APIRouter, Depends, HTTPException, Response, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from app.dependencies import get_db
from app.crud import report_crud

router = APIRouter(prefix="/reports", tags=["Reports"])

def _ym(year: Optional[int], month: Optional[int]):
    today = date.today()
    return (year or today.year, month or today.month)

@router.get("/landlord/{landlord_id}/monthly-summary")
def landlord_monthly_summary(landlord_id: int, year: Optional[int] = None, month: Optional[int] = None, db: Session = Depends(get_db)):
    y, m = _ym(year, month)
    try:
        return report_crud.landlord_monthly_summary(db, landlord_id, y, m)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/property/{property_id}/monthly-summary")
def property_monthly_summary(property_id: int, year: Optional[int] = None, month: Optional[int] = None, db: Session = Depends(get_db)):
    y, m = _ym(year, month)
    try:
        return report_crud.property_monthly_summary(db, property_id, y, m)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/landlord/{landlord_id}/monthly-summary.csv")
def landlord_monthly_csv(landlord_id: int, year: Optional[int] = None, month: Optional[int] = None, db: Session = Depends(get_db)):
    y, m = _ym(year, month)
    try:
        csv_text = report_crud.landlord_monthly_csv(db, landlord_id, y, m)
        filename = f"monthly_summary_{landlord_id}_{y}_{m}.csv"
        return Response(
            content=csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/landlord/{landlord_id}/send-reminders")
def landlord_send_reminders(
    landlord_id: int,
    year: Optional[int] = None,
    month: Optional[int] = None,
    dry_run: bool = Query(False, description="If true, do not actually send; just return recipients"),
    db: Session = Depends(get_db),
):
    y, m = _ym(year, month)
    try:
        recipients = report_crud.landlord_reminder_recipients(db, landlord_id, y, m)
        # Hook your SMS gateway here
        sent = []
        if not dry_run:
            for r in recipients:
                phone = r.get("phone")
                if not phone:
                    continue
                # TODO: integrate real SMS: mpesa/sms provider
                # For now we just simulate
                # send_sms(phone, f"Rent reminder: Balance {r['balance']} due for {m}/{y}.")
                sent.append({"tenant_id": r["tenant_id"], "phone": phone})
        return {"year": y, "month": m, "count": len(recipients), "dry_run": dry_run, "recipients": recipients, "sent": sent}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
