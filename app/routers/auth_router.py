from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth.password_utils import hash_password, verify_password
from app.auth.jwt_utils import create_access_token
from app.auth.dependencies import get_db
from app.schemas.auth_schemas import (
    RegisterUser,
    LoginUser,
    ForgotPasswordRequest,
    VerifyResetOTPRequest,
    ResetPasswordRequest,
    ResendResetOTPRequest,
)
from app.utils.phone_utils import normalize_ke_phone

from app.models.user_models import (
    Landlord,
    PropertyManager,
    ManagerUser,
    Tenant,
    Admin,
    SuperAdmin,
)
from app.models.property_models import Property, Unit, Lease

from app.services.auth_lookup_service import get_user_by_role_and_email, set_user_password
from app.services.otp_service import (
    create_password_reset_otp,
    get_valid_password_reset_otp,
    mark_otp_used,
)
from app.services.notification_service import notify_email

router = APIRouter(prefix="/auth", tags=["Authentication"])


def clean_email(email: str | None) -> str | None:
    e = (email or "").strip().lower()
    return e or None


def clean_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    return normalize_ke_phone(phone)


def exists_by_email_or_phone(db: Session, model, email: str | None, phone: str | None) -> bool:
    conds = []
    if hasattr(model, "email") and email:
        conds.append(model.email == email)
    if hasattr(model, "phone") and phone:
        conds.append(model.phone == phone)
    if not conds:
        return False
    return db.query(db.query(model.id).filter(or_(*conds)).exists()).scalar()


@router.post("/register")
def register_user(data: RegisterUser, db: Session = Depends(get_db)):
    try:
        email = clean_email(data.email)
        phone = clean_phone(data.phone)

        if not phone:
            raise HTTPException(
                status_code=400,
                detail="Invalid Kenyan phone number. Use 07/01 or +254/254 format.",
            )

        role = (data.role or "").strip().lower()

        if role in {"admin", "super_admin"}:
            raise HTTPException(
                status_code=403,
                detail=f"{role} self-registration is disabled. Only super_admin can create admins.",
            )

        # ---------------- LANDLORD ----------------
        if role == "landlord":
            if not data.password:
                raise HTTPException(status_code=400, detail="Password is required for landlord")

            if exists_by_email_or_phone(db, Landlord, email, phone):
                raise HTTPException(
                    status_code=409,
                    detail="Email or phone already registered for a landlord",
                )

            user = Landlord(
                name=data.name.strip(),
                phone=phone,
                email=email,
                password=hash_password(data.password),
                id_number=data.id_number,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return {"message": "Landlord registered successfully", "id": user.id}

        # ---------------- MANAGER ----------------
        if role == "manager":
            if not data.password:
                raise HTTPException(status_code=400, detail="Password is required for manager")

            if exists_by_email_or_phone(db, ManagerUser, email, phone):
                raise HTTPException(
                    status_code=409,
                    detail="Email or phone already registered for a manager staff",
                )

            manager_type = (data.manager_type or "individual").strip().lower()
            if manager_type not in ("individual", "agency"):
                raise HTTPException(
                    status_code=400,
                    detail="manager_type must be 'individual' or 'agency'",
                )

            company_name = (data.company_name or "").strip() or None
            contact_person = (data.contact_person or "").strip() or None
            office_phone = (data.office_phone or "").strip() or None
            office_email = clean_email(data.office_email)

            if manager_type == "agency" and not company_name:
                raise HTTPException(
                    status_code=400,
                    detail="company_name is required when manager_type='agency'",
                )

            org_name = company_name if (manager_type == "agency" and company_name) else data.name.strip()

            org = PropertyManager(
                name=org_name,
                phone=phone,
                email=email,
                password=None,
                id_number=data.id_number,
                type=manager_type,
                company_name=company_name,
                contact_person=contact_person if manager_type == "agency" else None,
                office_phone=office_phone if manager_type == "agency" else None,
                office_email=office_email if manager_type == "agency" else None,
                logo_url=None,
            )
            db.add(org)
            db.flush()

            staff_display_name = (
                contact_person if (manager_type == "agency" and contact_person) else data.name.strip()
            )

            staff = ManagerUser(
                manager_id=org.id,
                name=staff_display_name,
                phone=phone,
                email=email,
                password_hash=hash_password(data.password),
                id_number=data.id_number,
                staff_role="manager_admin",
                active=True,
            )
            db.add(staff)

            db.commit()
            db.refresh(org)
            db.refresh(staff)

            return {
                "message": "Manager registered successfully",
                "manager_id": org.id,
                "staff_id": staff.id,
                "manager_type": org.type,
                "manager_name": org.company_name or org.name,
            }

        # ---------------- TENANT ----------------
        if role == "tenant":
            if not data.property_code:
                raise HTTPException(status_code=400, detail="Property code is required for tenant registration")

            unit_number_in = (data.unit_number or "").strip() if getattr(data, "unit_number", None) else ""
            unit_id_in = getattr(data, "unit_id", None)

            if not unit_number_in and unit_id_in is None:
                raise HTTPException(
                    status_code=400,
                    detail="Unit is required (enter unit name/number or select a unit).",
                )

            if exists_by_email_or_phone(db, Tenant, email, phone):
                raise HTTPException(
                    status_code=409,
                    detail="Email or phone already registered for a tenant",
                )

            prop_code = (data.property_code or "").strip()
            prop = (
                db.query(Property)
                .filter(func.upper(func.trim(Property.property_code)) == func.upper(func.trim(prop_code)))
                .first()
            )
            if not prop:
                raise HTTPException(status_code=404, detail="Invalid property code")

            if unit_number_in:
                unit = (
                    db.query(Unit)
                    .filter(
                        Unit.property_id == prop.id,
                        func.lower(func.trim(Unit.number)) == func.lower(func.trim(unit_number_in)),
                    )
                    .first()
                )
                if not unit:
                    raise HTTPException(
                        status_code=404,
                        detail=f'Unit "{unit_number_in}" not found for this property',
                    )
            else:
                unit = (
                    db.query(Unit)
                    .filter(Unit.id == unit_id_in, Unit.property_id == prop.id)
                    .first()
                )
                if not unit:
                    raise HTTPException(status_code=404, detail="Unit not found for this property")

            if int(getattr(unit, "occupied", 0) or 0) == 1:
                raise HTTPException(status_code=409, detail="Unit already occupied")

            tenant_password = hash_password(data.password) if data.password else None

            user = Tenant(
                name=data.name.strip(),
                phone=phone,
                email=email,
                property_id=prop.id,
                unit_id=unit.id,
                password=tenant_password,
                id_number=data.id_number,
            )
            db.add(user)
            db.flush()

            rent_amount = float(getattr(unit, "rent_amount", 0) or 0)
            lease = Lease(
                tenant_id=user.id,
                unit_id=unit.id,
                start_date=date.today(),
                end_date=None,
                rent_amount=rent_amount,
                active=1,
            )
            db.add(lease)
            unit.occupied = 1

            db.commit()
            db.refresh(user)
            db.refresh(lease)

            return {
                "message": "Tenant registered successfully",
                "id": user.id,
                "lease_id": lease.id,
                "unit_id": unit.id,
                "property_id": prop.id,
            }

        raise HTTPException(status_code=400, detail="Invalid role")

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
def login_user(data: LoginUser, db: Session = Depends(get_db)):
    role = (data.role or "").strip().lower()

    phone = clean_phone(data.phone)
    if not phone:
        raise HTTPException(
            status_code=400,
            detail="Invalid Kenyan phone number. Use 07/01 or +254/254 format.",
        )

    if role == "manager":
        staff = db.query(ManagerUser).filter(
            ManagerUser.phone == phone,
            ManagerUser.active == True,  # noqa: E712
        ).first()

        if not staff:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not data.password or not verify_password(data.password, staff.password_hash):
            raise HTTPException(status_code=401, detail="Invalid password")

        token = create_access_token(
            {
                "sub": str(staff.id),
                "role": "manager",
                "manager_id": staff.manager_id,
                "staff_role": staff.staff_role,
            }
        )

        return {
            "access_token": token,
            "token_type": "bearer",
            "id": staff.id,
            "manager_id": staff.manager_id,
            "role": "manager",
        }

    model_map = {
        "landlord": Landlord,
        "tenant": Tenant,
        "admin": Admin,
        "super_admin": SuperAdmin,
    }
    model = model_map.get(role)
    if not model:
        raise HTTPException(status_code=400, detail="Invalid role")

    user = db.query(model).filter(model.phone == phone).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if hasattr(user, "active") and getattr(user, "active") is False:
        raise HTTPException(status_code=403, detail="Account is inactive")

    if not getattr(user, "password", None):
        raise HTTPException(status_code=401, detail="Account has no password set")

    if not data.password or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid password")

    token = create_access_token({"sub": str(user.id), "role": role})
    return {"access_token": token, "token_type": "bearer", "id": user.id, "role": role}


# ==========================================================
# FORGOT PASSWORD / OTP RESET
# ==========================================================

@router.post("/request-password-reset")
def request_password_reset(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    try:
        role = (data.role or "").strip().lower()
        email = clean_email(data.email)

        if not email:
            raise HTTPException(status_code=400, detail="Valid email is required")

        _, user = get_user_by_role_and_email(db, role, email)

        # Always return same message for security
        if not user:
            return {"message": "If an account with that email exists, an OTP has been sent."}

        otp = create_password_reset_otp(db, email=email)

        subject = "PropSmart Password Reset OTP"
        message = (
            f"Hello,\n\n"
            f"Your PropSmart password reset OTP is: {otp.otp_code}\n"
            f"It expires in 10 minutes.\n\n"
            f"If you did not request this, ignore this email."
        )

        log = notify_email(
            db=db,
            to_email=email,
            subject=subject,
            message=message,
            event_type="PASSWORD_RESET_OTP",
        )

        print("EMAIL STATUS:", log.status)
        print("EMAIL ERROR:", log.error_message)

        db.commit()
        return {"message": "If an account with that email exists, an OTP has been sent."}

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify-reset-otp")
def verify_reset_otp(data: VerifyResetOTPRequest, db: Session = Depends(get_db)):
    try:
        role = (data.role or "").strip().lower()
        email = clean_email(data.email)
        otp_code = (data.otp_code or "").strip()

        _, user = get_user_by_role_and_email(db, role, email)
        if not user:
            raise HTTPException(status_code=404, detail="Account not found")

        otp = get_valid_password_reset_otp(db, email=email, otp_code=otp_code)
        if not otp:
            raise HTTPException(status_code=400, detail="Invalid or expired OTP")

        return {"message": "OTP verified successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        role = (data.role or "").strip().lower()
        email = clean_email(data.email)
        otp_code = (data.otp_code or "").strip()
        new_password = (data.new_password or "").strip()

        if len(new_password) < 6:
            raise HTTPException(
                status_code=400,
                detail="Password must be at least 6 characters long",
            )

        _, user = get_user_by_role_and_email(db, role, email)
        if not user:
            raise HTTPException(status_code=404, detail="Account not found")

        otp = get_valid_password_reset_otp(db, email=email, otp_code=otp_code)
        if not otp:
            raise HTTPException(status_code=400, detail="Invalid or expired OTP")

        hashed_password = hash_password(new_password)
        set_user_password(user, hashed_password, role)
        mark_otp_used(db, otp)

        db.add(user)
        db.commit()

        return {"message": "Password reset successfully"}

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resend-reset-otp")
def resend_reset_otp(data: ResendResetOTPRequest, db: Session = Depends(get_db)):
    try:
        role = (data.role or "").strip().lower()
        email = clean_email(data.email)

        _, user = get_user_by_role_and_email(db, role, email)

        if not user:
            return {"message": "If an account with that email exists, an OTP has been sent."}

        otp = create_password_reset_otp(db, email=email)

        subject = "PropSmart Password Reset OTP (Resent)"
        message = (
            f"Hello,\n\n"
            f"Your new PropSmart password reset OTP is: {otp.otp_code}\n"
            f"It expires in 10 minutes.\n\n"
            f"If you did not request this, ignore this email."
        )

        log = notify_email(
            db=db,
            to_email=email,
            subject=subject,
            message=message,
            event_type="PASSWORD_RESET_OTP_RESENT",
        )

        print("EMAIL STATUS:", log.status)
        print("EMAIL ERROR:", log.error_message)

        db.commit()
        return {"message": "If an account with that email exists, an OTP has been sent."}

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))