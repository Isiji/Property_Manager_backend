# app/main.py
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app.routers import (
    bulk_upload,
    landlord_routers,
    tenant_routers,
    property_router,
    unit_router,
    lease_router,
    payment_router,
    maintenance_router,
    service_charges_router,
    admin_router,
    report_router,
    notification_router,
    auth_router,
    payout_router,
    bulk_router,
    tenant_portal_router,
    property_units_lookup,
    payments_mpesa,
    webhooks_daraja,
    reports_property_status_router,
    payment_receipts_router,

)
from app.services import reminder_service  # import the reminder scheduler
from app.core.config import settings
# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Property Management API")

origins = [
    "http://localhost:3000",  # React default
    "http://localhost:63187", # Flutter web dev
    "http://127.0.0.1:8000",
    "http://127.0.0.1:63187",
    "*",
    "https://bruce-nonimaginational-noel.ngrok-free.dev",
]
# ✅ Enable CORS to allow Flutter Web requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",  # In production, specify your frontend URL here (e.g., "https://yourdomain.com"),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def read_root():
    return {"status": "Ok",
            "service": "Property Management API",
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/healthz",
            }
@app.get("/healthz", include_in_schema=False)
def health_check():
    return {"ok": True}

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)

# ✅ Register routers
app.include_router(landlord_routers.router)
app.include_router(tenant_routers.router)
app.include_router(property_router.router)
app.include_router(unit_router.router)
app.include_router(bulk_upload.router)
app.include_router(lease_router.router)
app.include_router(payment_router.router)
app.include_router(maintenance_router.router)
app.include_router(service_charges_router.router)
app.include_router(admin_router.router)
app.include_router(report_router.router)
app.include_router(notification_router.router)
app.include_router(auth_router.router)
app.include_router(payout_router.router)
app.include_router(bulk_router.router)
app.include_router(tenant_portal_router.router)
app.include_router(property_units_lookup.router)
app.include_router(payments_mpesa.router)
app.include_router(webhooks_daraja.router)
app.include_router(reports_property_status_router.router)
app.include_router(payment_receipts_router.router) 


# ✅ Start automatic reminders
reminder_service.start_scheduler()
