# seed_data.py
from datetime import datetime, timedelta, timezone
from decimal import Decimal
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
# CLEAR EXISTING DATA
# ==============================
session.execute(text("TRUNCATE TABLE payments RESTART IDENTITY CASCADE"))
session.execute(text("TRUNCATE TABLE maintenance_requests RESTART IDENTITY CASCADE"))
session.execute(text("TRUNCATE TABLE service_charges RESTART IDENTITY CASCADE"))
session.execute(text("TRUNCATE TABLE leases RESTART IDENTITY CASCADE"))
session.execute(text("TRUNCATE TABLE units RESTART IDENTITY CASCADE"))
session.execute(text("TRUNCATE TABLE properties RESTART IDENTITY CASCADE"))
session.execute(text("TRUNCATE TABLE tenants RESTART IDENTITY CASCADE"))
session.execute(text("TRUNCATE TABLE property_managers RESTART IDENTITY CASCADE"))
session.execute(text("TRUNCATE TABLE landlords RESTART IDENTITY CASCADE"))
session.commit()

# ==============================
# LANDLORDS
# ==============================
landlords = [
    Landlord(name="John Doe", phone="0712345678", email="john@example.com"),
    Landlord(name="Jane Smith", phone="0723456789", email="jane@example.com"),
]
session.add_all(landlords)
session.commit()

# ==============================
# PROPERTY MANAGERS
# ==============================
managers = [
    PropertyManager(name="Alice Manager", phone="0734567890", email="alice@example.com")
]
session.add_all(managers)
session.commit()

# ==============================
# TENANTS
# ==============================
tenants = [
    Tenant(name="Tom Tenant", phone="0745678901", email="tom@example.com"),
    Tenant(name="Lucy Tenant", phone="0756789012", email="lucy@example.com"),
]
session.add_all(tenants)
session.commit()

# ==============================
# PROPERTIES & UNITS
# ==============================
prop1 = Property(name="Sunset Apartments", address="Nairobi", landlord=landlords[0], manager=managers[0])
prop2 = Property(name="Green Villas", address="Mombasa", landlord=landlords[1])
session.add_all([prop1, prop2])
session.commit()

unit1 = Unit(number="101", rent_amount=Decimal("5000"), property=prop1)
unit2 = Unit(number="102", rent_amount=Decimal("5500"), property=prop1)
unit3 = Unit(number="201", rent_amount=Decimal("6000"), property=prop2)
session.add_all([unit1, unit2, unit3])
session.commit()

# ==============================
# LEASES
# ==============================
lease1 = Lease(
    tenant=tenants[0],
    unit=unit1,
    start_date=datetime.now(timezone.utc),
    end_date=datetime.now(timezone.utc) + timedelta(days=365),
    rent_amount=unit1.rent_amount,  # <-- added rent_amount
    active=True
)

lease2 = Lease(
    tenant=tenants[1],
    unit=unit2,
    start_date=datetime.now(timezone.utc),
    end_date=datetime.now(timezone.utc) + timedelta(days=365),
    rent_amount=unit2.rent_amount,  # <-- added rent_amount
    active=True
)

session.add_all([lease1, lease2])
session.commit()

# ==============================
# SERVICE CHARGES
# ==============================
sc1 = ServiceCharge(service_type="Water", amount=Decimal("500"), unit=unit1, tenant=tenants[0])
sc2 = ServiceCharge(service_type="Security", amount=Decimal("200"), unit=unit1, tenant=tenants[0])
session.add_all([sc1, sc2])
session.commit()

# ==============================
# PAYMENTS
# ==============================
payment1 = Payment(
    lease=lease1,
    tenant=tenants[0],
    unit=unit1,
    amount=Decimal("5800"),
    date=datetime.utcnow(),
    description="Rent + Water + Security"
)
session.add(payment1)
session.commit()

# ==============================
# MAINTENANCE STATUS
# ==============================
status_open = MaintenanceStatus(name="open")
status_in_progress = MaintenanceStatus(name="in_progress")
status_resolved = MaintenanceStatus(name="resolved")

session.add_all([status_open, status_in_progress, status_resolved])
session.commit()

# ==============================
# MAINTENANCE REQUESTS
# ==============================
mr1 = MaintenanceRequest(
    unit=unit1,
    tenant=tenants[0],
    description="Leaky faucet",
    status=status_open,
    created_at=datetime.now(timezone.utc)
)
session.add(mr1)
session.commit()

print("✅ Seed data successfully inserted!")
