from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.dependencies import get_db
from app.schemas.report_schemas import (
    RentCollectionSummary,
    ServiceChargeSummary,
    OccupancySummary,
)
from app.crud import report_crud as crud
from app.models.user_models import Tenant, Landlord
from app.models.payment_model import Payment
from app.dependencies import get_current_user
from app.routers.payment_router import router as payment_router
from app.schemas.report_schemas import TenantPaymentReport, LandlordIncomeReport, MonthlyIncome
from app.models.property_models import Property
from sqlalchemy import func
from app.models.property_models import Unit
from typing import Optional, List
from datetime import datetime
from app.reports.payment_history import get_tenant_payment_history
from app.schemas.payment_schema import PaymentOut

router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
)

@router.get("/rent", response_model=List[RentCollectionSummary])
def rent_collection_summary(db: Session = Depends(get_db)):
    return crud.get_rent_collection_summary(db)

@router.get("/service-charges", response_model=List[ServiceChargeSummary])
def service_charge_summary(db: Session = Depends(get_db)):
    return crud.get_service_charge_summary(db)

@router.get("/occupancy", response_model=List[OccupancySummary])
def occupancy_summary(db: Session = Depends(get_db)):
    return crud.get_occupancy_summary(db)

@router.get("/tenant", response_model=list[TenantPaymentReport])
def get_tenant_payment_history(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)  # e.g., {"id": 1, "role": "tenant"}
):
    if current_user["role"] != "tenant":
        return {"error": "Only tenants can access this report"}

    payments = (
        db.query(Payment)
        .filter(Payment.tenant_id == current_user["id"])
        .order_by(Payment.created_at.desc())
        .all()
    )
    return payments

@router.get("/landlord", response_model=list[LandlordIncomeReport])
def get_landlord_income_report(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "landlord":
        return {"error": "Only landlords can access this report"}

    # Query payments grouped by property and month
    results = (
        db.query(
            Property.id.label("property_id"),
            Property.name.label("property_name"),
            func.extract("year", Payment.date).label("year"),
            func.extract("month", Payment.date).label("month"),
            func.coalesce(func.sum(Payment.amount), 0).label("total_income")
        )
        .join(Property.units)  # property -> units
        .join(Payment, Payment.unit_id == Unit.id, isouter=True)  # unit -> payments
        .filter(Property.landlord_id == current_user["id"])
        .group_by(Property.id, Property.name, "year", "month")
        .order_by(Property.id, "year", "month")
        .all()
    )

    # Get expected rent grouped by property & month
    expected_rent = (
        db.query(
            Property.id.label("property_id"),
            func.extract("year", Payment.date).label("year"),
            func.extract("month", Payment.date).label("month"),
            func.sum(Unit.rent_amount).label("expected_rent")
        )
        .join(Property.units)
        .join(Payment, Payment.unit_id == Unit.id, isouter=True)
        .filter(Property.landlord_id == current_user["id"])
        .group_by(Property.id, "year", "month")
        .all()
    )

    # Map expected rent for easy lookup
    expected_map = {
        (row.property_id, int(row.year), int(row.month)): row.expected_rent or 0
        for row in expected_rent
    }

    # Organize into structured report
    report_data = {}
    for row in results:
        key = row.property_id
        year, month = int(row.year), int(row.month)
        month_str = f"{year:04d}-{month:02d}"

        expected = expected_map.get((row.property_id, year, month), 0)
        outstanding = expected - row.total_income

        if key not in report_data:
            report_data[key] = {
                "property_id": row.property_id,
                "property_name": row.property_name,
                "monthly_income": []
            }

        report_data[key]["monthly_income"].append(
            MonthlyIncome(
                month=month_str,
                total_income=row.total_income,
                outstanding_balance=outstanding
            )
        )

    return list(report_data.values())

@router.get("/tenants/{tenant_id}/payment-history", response_model=List[PaymentOut])
def tenant_payment_history(
    tenant_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    payments = get_tenant_payment_history(db, tenant_id, start_date, end_date)
    if not payments:
        raise HTTPException(status_code=404, detail="No payment history found for this tenant")
    return payments