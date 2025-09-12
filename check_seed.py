from datetime import datetime, timezone
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.database import engine
from app.models import (
    Landlord, PropertyManager, Tenant, Property, Unit, Lease,
    ServiceCharge, Payment, MaintenanceRequest, MaintenanceStatus
)
Session = sessionmaker(bind=engine)
session = Session()
# ==============================
# QUICK SANITY CHECK
# ==============================
print("\n🏠 Properties and Units:")
for prop in session.query(Property).all():
    print(f"{prop.name} ({prop.address}) - Landlord: {prop.landlord.name if prop.landlord else 'N/A'}")
    for unit in prop.units:
        print(f"  Unit {unit.number} - Rent: {unit.rent_amount}")

print("\n👤 Tenants and Leases:")
for tenant in session.query(Tenant).all():
    print(f"{tenant.name} ({tenant.email})")
    for lease in tenant.leases:
        print(f"  Leased Unit: {lease.unit.number} at {lease.unit.property.name} - Rent: {lease.rent_amount}")

print("\n💰 Payments:")
for payment in session.query(Payment).all():
    print(f"{payment.tenant.name} paid {payment.amount} for Unit {payment.unit.number} on {payment.date}")

print("\n🛠️ Maintenance Requests:")
for mr in session.query(MaintenanceRequest).all():
    print(f"{mr.tenant.name} reported '{mr.description}' for Unit {mr.unit.number} - Status: {mr.status.name}")
