# app/routers/admin_dashboard_router.py
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.dependencies import get_db, role_required
from app import models
from app.schemas.admin_dashboard_schema import (
    AdminOverviewOut,
    AdminCounts,
    AdminCollections,
    PropertySummaryRow,
    FinancePropertyRow,
)

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])


def _period_today() -> str:
    d = date.today()
    return f"{d.year}-{str(d.month).zfill(2)}"


@router.get(
    "/overview",
    response_model=AdminOverviewOut,
    dependencies=[Depends(role_required(["admin"]))],
)
def admin_overview(
    db: Session = Depends(get_db),
    period: str = Query(default_factory=_period_today, description="YYYY-MM"),
    top_properties: int = Query(6, ge=1, le=30),
):
    # ---------- counts ----------
    properties = db.query(func.count(models.Property.id)).scalar() or 0
    units = db.query(func.count(models.Unit.id)).scalar() or 0
    occupied_units = db.query(func.count(models.Unit.id)).filter(models.Unit.occupied == 1).scalar() or 0
    vacant_units = max(0, int(units) - int(occupied_units))

    tenants = db.query(func.count(models.Tenant.id)).scalar() or 0
    active_leases = db.query(func.count(models.Lease.id)).filter(models.Lease.active == 1).scalar() or 0

    # maintenance buckets
    # We treat missing statuses as 0 (in case seed isn't done)
    status_map = {name: sid for (sid, name) in db.query(models.MaintenanceStatus.id, models.MaintenanceStatus.name).all()}
    open_id = status_map.get("open")
    in_prog_id = status_map.get("in_progress")
    resolved_id = status_map.get("resolved")

    def _count_status(sid: Optional[int]) -> int:
        if not sid:
            return 0
        return (
            db.query(func.count(models.MaintenanceRequest.id))
            .filter(models.MaintenanceRequest.status_id == sid)
            .scalar()
            or 0
        )

    maintenance_open = _count_status(open_id)
    maintenance_in_progress = _count_status(in_prog_id)
    maintenance_resolved = _count_status(resolved_id)

    counts = AdminCounts(
        properties=int(properties),
        units=int(units),
        occupied_units=int(occupied_units),
        vacant_units=int(vacant_units),
        tenants=int(tenants),
        active_leases=int(active_leases),
        maintenance_open=int(maintenance_open),
        maintenance_in_progress=int(maintenance_in_progress),
        maintenance_resolved=int(maintenance_resolved),
    )

    # ---------- collections (period) ----------
    # Total received (paid) in the period
    received_total = (
        db.query(func.coalesce(func.sum(models.Payment.amount), 0))
        .filter(models.Payment.period == period)
        .filter(models.Payment.status == models.PaymentStatus.paid)
        .scalar()
        or 0
    )
    paid_count = (
        db.query(func.count(models.Payment.id))
        .filter(models.Payment.period == period)
        .filter(models.Payment.status == models.PaymentStatus.paid)
        .scalar()
        or 0
    )

    # unpaid leases for period = active leases with no PAID payment for that period
    paid_lease_ids_subq = (
        db.query(models.Payment.lease_id)
        .filter(models.Payment.period == period)
        .filter(models.Payment.status == models.PaymentStatus.paid)
        .filter(models.Payment.lease_id.isnot(None))
        .subquery()
    )

    unpaid_count = (
        db.query(func.count(models.Lease.id))
        .filter(models.Lease.active == 1)
        .filter(~models.Lease.id.in_(paid_lease_ids_subq))
        .scalar()
        or 0
    )

    collections = AdminCollections(
        period=period,
        collected_total=float(received_total or 0),
        paid_count=int(paid_count),
        unpaid_count=int(unpaid_count),
    )

    # ---------- top properties (simple: latest properties) ----------
    props = (
        db.query(models.Property)
        .order_by(models.Property.id.desc())
        .limit(int(top_properties))
        .all()
    )

    props_out: List[PropertySummaryRow] = []
    for p in props:
        # unit counts per property
        t_units = (
            db.query(func.count(models.Unit.id))
            .filter(models.Unit.property_id == p.id)
            .scalar()
            or 0
        )
        t_occ = (
            db.query(func.count(models.Unit.id))
            .filter(models.Unit.property_id == p.id)
            .filter(models.Unit.occupied == 1)
            .scalar()
            or 0
        )
        props_out.append(
            PropertySummaryRow(
                id=p.id,
                name=p.name,
                address=p.address,
                property_code=p.property_code,
                landlord_id=p.landlord_id,
                manager_id=p.manager_id,
                units=int(t_units),
                occupied_units=int(t_occ),
                vacant_units=max(0, int(t_units) - int(t_occ)),
            )
        )

    return AdminOverviewOut(counts=counts, collections=collections, properties_top=props_out)


@router.get(
    "/properties",
    response_model=List[PropertySummaryRow],
    dependencies=[Depends(role_required(["admin", "super_admin"]))],
)
def admin_properties_summary(db: Session = Depends(get_db), limit: int = Query(200, ge=1, le=2000)):
    props = db.query(models.Property).order_by(models.Property.id.desc()).limit(int(limit)).all()
    out: List[PropertySummaryRow] = []
    for p in props:
        t_units = db.query(func.count(models.Unit.id)).filter(models.Unit.property_id == p.id).scalar() or 0
        t_occ = (
            db.query(func.count(models.Unit.id))
            .filter(models.Unit.property_id == p.id)
            .filter(models.Unit.occupied == 1)
            .scalar()
            or 0
        )
        out.append(
            PropertySummaryRow(
                id=p.id,
                name=p.name,
                address=p.address,
                property_code=p.property_code,
                landlord_id=p.landlord_id,
                manager_id=p.manager_id,
                units=int(t_units),
                occupied_units=int(t_occ),
                vacant_units=max(0, int(t_units) - int(t_occ)),
            )
        )
    return out


@router.get(
    "/finance/summary",
    response_model=List[FinancePropertyRow],
    dependencies=[Depends(role_required(["admin", "super_admin"]))],
)
def admin_finance_summary(
    db: Session = Depends(get_db),
    period: str = Query(default_factory=_period_today, description="YYYY-MM"),
    limit: int = Query(200, ge=1, le=2000),
):
    """
    Per-property finance summary:
    - expected rent = sum(active lease rent_amount for leases in that property)
    - received rent = sum(paid payments for that property+period)
    - balance = expected - received
    - paid_leases / unpaid_leases counts
    """
    props = db.query(models.Property).order_by(models.Property.id.desc()).limit(int(limit)).all()
    out: List[FinancePropertyRow] = []

    for p in props:
        # Active leases under this property
        leases_q = (
            db.query(models.Lease)
            .join(models.Unit, models.Unit.id == models.Lease.unit_id)
            .filter(models.Unit.property_id == p.id)
            .filter(models.Lease.active == 1)
        )

        lease_ids = [l.id for l in leases_q.all()]
        expected = float(sum(float(l.rent_amount or 0) for l in leases_q.all()) or 0)

        if not lease_ids:
            out.append(
                FinancePropertyRow(
                    property_id=p.id,
                    property_name=p.name,
                    property_code=p.property_code,
                    period=period,
                    expected_rent=0.0,
                    received_rent=0.0,
                    balance=0.0,
                    paid_leases=0,
                    unpaid_leases=0,
                )
            )
            continue

        received = (
            db.query(func.coalesce(func.sum(models.Payment.amount), 0))
            .filter(models.Payment.period == period)
            .filter(models.Payment.status == models.PaymentStatus.paid)
            .filter(models.Payment.lease_id.in_(lease_ids))
            .scalar()
            or 0
        )
        received_f = float(received or 0)

        paid_leases = (
            db.query(func.count(func.distinct(models.Payment.lease_id)))
            .filter(models.Payment.period == period)
            .filter(models.Payment.status == models.PaymentStatus.paid)
            .filter(models.Payment.lease_id.in_(lease_ids))
            .scalar()
            or 0
        )

        unpaid_leases = max(0, len(lease_ids) - int(paid_leases))

        out.append(
            FinancePropertyRow(
                property_id=p.id,
                property_name=p.name,
                property_code=p.property_code,
                period=period,
                expected_rent=float(expected),
                received_rent=received_f,
                balance=round(float(expected) - received_f, 2),
                paid_leases=int(paid_leases),
                unpaid_leases=int(unpaid_leases),
            )
        )

    return out


@router.get(
    "/maintenance/summary",
    dependencies=[Depends(role_required(["admin", "super_admin"]))],
)
def admin_maintenance_summary(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Returns counts grouped by MaintenanceStatus.name
    """
    rows = (
        db.query(models.MaintenanceStatus.name, func.count(models.MaintenanceRequest.id))
        .join(models.MaintenanceRequest, models.MaintenanceRequest.status_id == models.MaintenanceStatus.id)
        .group_by(models.MaintenanceStatus.name)
        .all()
    )
    return {"counts": [{"status": s, "count": int(c)} for s, c in rows]}