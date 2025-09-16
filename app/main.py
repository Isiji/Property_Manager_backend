# app/main.py
from fastapi import FastAPI
from app.database import Base, engine
from app.routers import bulk_upload, landlord_routers, tenant_routers, property_router, unit_router, lease_router, payment_router, maintenance_router, service_charges_router

# create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Property Management API")

# register routers
app.include_router(landlord_routers.router)
app.include_router(tenant_routers.router)
app.include_router(property_router.router)
app.include_router(unit_router.router)
app.include_router(bulk_upload.router)
app.include_router(lease_router.router)
app.include_router(payment_router.router)
app.include_router(maintenance_router.router)
app.include_router(service_charges_router.router)


