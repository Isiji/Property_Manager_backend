from fastapi import FastAPI, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import Base, engine, SessionLocal
from app.auth.password_utils import hash_password
from app.utils.phone_utils import normalize_ke_phone
from app.models.user_models import SuperAdmin

from app.routers import (
    bulk_upload,
    landlord_routers,
    tenant_routers,
    unit_router,
    lease_router,
    payment_router,
    maintenance_router,
    service_charges_router,
    admin_router,
    report_router,
    notification_router,
    auth_router,
    bulk_router,
    tenant_portal_router,
    property_units_lookup,
    payments_mpesa,
    webhooks_daraja,
    reports_property_status_router,
    payment_receipts_router,
    admin_jobs_router,
    admin_seed_router,
    property_manager_router,
    agency_router,
    property_router,
    admin_dashboard_router,
    payout_router,
    audit_log_router,
    receipt_routes,
)
from app.services import reminder_service  # import the reminder scheduler
from app.core.config import settings

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Property Management API")

from fastapi import Request

@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(
        f"➡️ {request.method} {request.url.path} | "
        f"Origin={request.headers.get('origin')} | "
        f"Referer={request.headers.get('referer')}"
    )
    response = await call_next(request)
    print(f"⬅️ {response.status_code} {request.method} {request.url.path}")
    return response
def bootstrap_super_admin():
    """
    Create default super admin if none exists.
    """
    db: Session = SessionLocal()
    try:
        existing = db.query(SuperAdmin).first()
        if existing:
            print("✅ Super admin already exists. Bootstrap skipped.")
            return

        default_name = "PropSmart Super Admin"
        default_email = "blairisiji@gmail.com"
        default_phone = normalize_ke_phone("0702805027")
        default_password = "Admin@12345"

        super_admin = SuperAdmin(
            name=default_name,
            email=default_email,
            phone=default_phone,
            password=hash_password(default_password),
            active=True,
            id_number=None,
        )
        db.add(super_admin)
        db.commit()

        print("🚀 Default super admin created.")
        print(f"   phone: {default_phone}")
        print(f"   email: {default_email}")
        print(f"   password: {default_password}")
        print("⚠️ Change this password immediately after first login.")
    except Exception as e:
        db.rollback()
        print(f"❌ Failed to bootstrap super admin: {e}")
    finally:
        db.close()


origins = [
    "http://localhost:3000",  # React default
    "http://localhost:63187", # Flutter web dev
    "http://127.0.0.1:8000",
    "http://127.0.0.1:63187",
    "*",
    "https://bruce-nonimaginational-noel.ngrok-free.dev",
]

# ✅ Enable CORS to allow Flutter Web requests
print("CORS_ORIGINS:", settings.CORS_ORIGINS),

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:63187",
        "http://127.0.0.1:63187",
        "http://127.0.0.1:4040",

        "https://bruce-nonimaginational-noel.ngrok-free.dev",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

@app.on_event("startup")
def startup_event():
    bootstrap_super_admin()


@app.get("/", include_in_schema=False)
def read_root():
    return {
        "status": "Ok",
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
#app.include_router(webhooks_daraja.router)
app.include_router(reports_property_status_router.router)
app.include_router(payment_receipts_router.router)
app.include_router(admin_jobs_router.router)
app.include_router(admin_seed_router.router)
app.include_router(property_manager_router.router)
app.include_router(agency_router.router)
app.include_router(admin_dashboard_router.router)
app.include_router(audit_log_router.router)
app. include_router(receipt_routes.router)
# ✅ Start automatic reminders
reminder_service.start_scheduler()