from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.payment_model import Payment, ServiceCharge
from app.models.property_models import Property, Unit


# ---------------- RENT COLLECTION ----------------
def get_rent_collection_summary(db: Session):
    results = (
        db.query(
            Property.id.label("property_id"),
            Property.name.label("property_name"),
            func.coalesce(func.sum(Payment.amount), 0).label("total_rent_collected"),
        )
        .join(Unit, Unit.property_id == Property.id)
        .join(Payment, Payment.unit_id == Unit.id, isouter=True)
        .group_by(Property.id, Property.name)
        .all()
    )
    return results


# ---------------- SERVICE CHARGES ----------------
def get_service_charge_summary(db: Session):
    results = (
        db.query(
            Property.id.label("property_id"),
            Property.name.label("property_name"),
            ServiceCharge.service_type,
            func.coalesce(func.sum(ServiceCharge.amount), 0).label("total_amount"),
        )
        .join(Unit, Unit.property_id == Property.id)
        .join(ServiceCharge, ServiceCharge.unit_id == Unit.id, isouter=True)
        .group_by(Property.id, Property.name, ServiceCharge.service_type)
        .all()
    )
    return results


# ---------------- OCCUPANCY ----------------
def get_occupancy_summary(db: Session):
    results = (
        db.query(
            Property.id.label("property_id"),
            Property.name.label("property_name"),
            func.count(Unit.id).label("total_units"),
            func.sum(func.case([(Unit.is_occupied == True, 1)], else_=0)).label("occupied_units"),
            func.sum(func.case([(Unit.is_occupied == False, 1)], else_=0)).label("vacant_units"),
        )
        .join(Unit, Unit.property_id == Property.id)
        .group_by(Property.id, Property.name)
        .all()
    )

    summaries = []
    for r in results:
        occupancy_rate = (r.occupied_units / r.total_units * 100) if r.total_units > 0 else 0
        summaries.append({
            "property_id": r.property_id,
            "property_name": r.property_name,
            "total_units": r.total_units,
            "occupied_units": r.occupied_units,
            "vacant_units": r.vacant_units,
            "occupancy_rate": round(occupancy_rate, 2),
        })
    return summaries
