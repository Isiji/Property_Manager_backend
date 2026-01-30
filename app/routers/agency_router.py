from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.auth.dependencies import get_db
from app.auth.password_utils import hash_password
from app.auth.jwt_utils import SECRET_KEY, ALGORITHM
from app.utils.phone_utils import normalize_ke_phone

from app.models.user_models import PropertyManager, ManagerUser
from app.models.property_models import Property
from app.models.agency_models import (
    AgencyAgentLink,
    PropertyAgentAssignment,
    PropertyExternalManagerAssignment,
)

from app.schemas.agency_schemas import (
    ManagerUserCreate,
    ManagerUserOut,
    StaffDeactivateOut,
    LinkAgentRequest,
    LinkAgentOut,
    AssignPropertyOut,
)

router = APIRouter(prefix="/agency", tags=["Agency"])
bearer = HTTPBearer(auto_error=False)


# ---------------------------
# Auth helpers
# ---------------------------
def _decode(creds: HTTPAuthorizationCredentials) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def _require_manager(payload: dict) -> None:
    if payload.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Not a manager session")


def _require_admin(payload: dict) -> None:
    staff_role = (payload.get("staff_role") or "").strip().lower()
    if staff_role not in ("manager_admin", "owner", "admin"):
        raise HTTPException(status_code=403, detail="Admin permission required")


def _get_ids(payload: dict) -> tuple[int, int]:
    staff_id_raw = payload.get("sub")
    manager_id_raw = payload.get("manager_id")

    if staff_id_raw is None or manager_id_raw is None:
        raise HTTPException(status_code=401, detail="Token missing sub/manager_id")

    staff_id = int(staff_id_raw)
    manager_id = int(manager_id_raw)
    return staff_id, manager_id


def _require_agency_org(db: Session, manager_id: int) -> PropertyManager:
    org = db.query(PropertyManager).filter(PropertyManager.id == manager_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Manager org not found")
    if (org.type or "").strip().lower() != "agency":
        raise HTTPException(status_code=403, detail="Only agencies can perform this action")
    return org


def _require_property_belongs_to_agency(db: Session, property_id: int, agency_manager_id: int) -> Property:
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if int(getattr(prop, "manager_id", 0) or 0) != int(agency_manager_id):
        raise HTTPException(status_code=403, detail="Property is not managed by your agency")
    return prop


# ---------------------------
# Staff management
# ---------------------------

# allow ALL agency staff to view staff list
@router.get("/staff", response_model=list[ManagerUserOut])
def list_staff(
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials = Depends(bearer),
):
    payload = _decode(creds)
    _require_manager(payload)

    _, manager_id = _get_ids(payload)
    _require_agency_org(db, manager_id)

    staff = (
        db.query(ManagerUser)
        .filter(ManagerUser.manager_id == manager_id)
        .order_by(ManagerUser.active.desc(), ManagerUser.id.desc())
        .all()
    )
    return staff


# admin-only create staff
@router.post("/staff", response_model=ManagerUserOut)
def create_staff(
    body: ManagerUserCreate,
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials = Depends(bearer),
):
    payload = _decode(creds)
    _require_manager(payload)
    _require_admin(payload)

    _, manager_id = _get_ids(payload)
    _require_agency_org(db, manager_id)

    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    phone = normalize_ke_phone(body.phone)
    email = (body.email or "").strip().lower() or None

    if db.query(ManagerUser).filter(ManagerUser.phone == phone).first():
        raise HTTPException(status_code=409, detail="Phone already registered for a staff user")
    if email and db.query(ManagerUser).filter(ManagerUser.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered for a staff user")

    role = (body.staff_role or "manager_staff").strip().lower()
    if role not in ("manager_admin", "manager_staff", "finance"):
        raise HTTPException(status_code=400, detail="Invalid staff_role")

    staff = ManagerUser(
        manager_id=manager_id,
        name=name,
        phone=phone,
        email=email,
        password_hash=hash_password(body.password),
        id_number=body.id_number,
        staff_role=role,
        active=True,
    )
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff


@router.patch("/staff/{staff_id}/deactivate", response_model=StaffDeactivateOut)
def deactivate_staff(
    staff_id: int,
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials = Depends(bearer),
):
    payload = _decode(creds)
    _require_manager(payload)
    _require_admin(payload)

    _, manager_id = _get_ids(payload)
    _require_agency_org(db, manager_id)

    staff = (
        db.query(ManagerUser)
        .filter(ManagerUser.id == staff_id, ManagerUser.manager_id == manager_id)
        .first()
    )
    if not staff:
        raise HTTPException(status_code=404, detail="Staff user not found")

    staff.active = False
    db.commit()
    db.refresh(staff)
    return {"id": staff.id, "active": bool(staff.active)}


# ---------------------------
# Link external managers (agents)
# ---------------------------

@router.post("/agents/link", response_model=LinkAgentOut)
def link_agent(
    body: LinkAgentRequest,
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials = Depends(bearer),
):
    payload = _decode(creds)
    _require_manager(payload)
    _require_admin(payload)

    _, agency_manager_id = _get_ids(payload)
    _require_agency_org(db, agency_manager_id)

    agent_manager = None
    if body.agent_manager_id is not None:
        agent_manager = db.query(PropertyManager).filter(PropertyManager.id == body.agent_manager_id).first()
    elif body.agent_phone:
        phone = normalize_ke_phone(body.agent_phone)
        agent_manager = db.query(PropertyManager).filter(PropertyManager.phone == phone).first()
    else:
        raise HTTPException(status_code=400, detail="Provide agent_manager_id or agent_phone")

    if not agent_manager:
        raise HTTPException(status_code=404, detail="Agent manager org not found")

    if agent_manager.id == agency_manager_id:
        raise HTTPException(status_code=400, detail="Cannot link agency to itself")

    link = (
        db.query(AgencyAgentLink)
        .filter(
            AgencyAgentLink.agency_manager_id == agency_manager_id,
            AgencyAgentLink.agent_manager_id == agent_manager.id,
        )
        .first()
    )
    if link:
        link.status = "active"
        db.commit()
        db.refresh(link)
        return {
            "id": link.id,
            "agency_manager_id": link.agency_manager_id,
            "agent_manager_id": link.agent_manager_id,
            "status": link.status,
        }

    link = AgencyAgentLink(
        agency_manager_id=agency_manager_id,
        agent_manager_id=agent_manager.id,
        status="active",
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return {
        "id": link.id,
        "agency_manager_id": link.agency_manager_id,
        "agent_manager_id": link.agent_manager_id,
        "status": link.status,
    }


# allow ALL agency staff to view linked agents
@router.get("/agents", response_model=list[LinkAgentOut])
def list_linked_agents(
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials = Depends(bearer),
):
    payload = _decode(creds)
    _require_manager(payload)

    _, agency_manager_id = _get_ids(payload)
    _require_agency_org(db, agency_manager_id)

    links = (
        db.query(AgencyAgentLink)
        .filter(AgencyAgentLink.agency_manager_id == agency_manager_id)
        .order_by(AgencyAgentLink.id.desc())
        .all()
    )
    return [
        {
            "id": x.id,
            "agency_manager_id": x.agency_manager_id,
            "agent_manager_id": x.agent_manager_id,
            "status": x.status,
        }
        for x in links
    ]


@router.patch("/agents/{agent_manager_id}/unlink", response_model=LinkAgentOut)
def unlink_agent(
    agent_manager_id: int,
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials = Depends(bearer),
):
    payload = _decode(creds)
    _require_manager(payload)
    _require_admin(payload)

    _, agency_manager_id = _get_ids(payload)
    _require_agency_org(db, agency_manager_id)

    link = (
        db.query(AgencyAgentLink)
        .filter(
            AgencyAgentLink.agency_manager_id == agency_manager_id,
            AgencyAgentLink.agent_manager_id == agent_manager_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    link.status = "inactive"
    db.commit()
    db.refresh(link)
    return {
        "id": link.id,
        "agency_manager_id": link.agency_manager_id,
        "agent_manager_id": link.agent_manager_id,
        "status": link.status,
    }


# ---------------------------
# Assign properties to INTERNAL staff users (admin-only)
# ---------------------------

@router.post("/properties/{property_id}/assign/{assignee_user_id}", response_model=AssignPropertyOut)
def assign_property_to_staff(
    property_id: int,
    assignee_user_id: int,
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials = Depends(bearer),
):
    payload = _decode(creds)
    _require_manager(payload)
    _require_admin(payload)

    assigned_by_user_id, agency_manager_id = _get_ids(payload)
    _require_agency_org(db, agency_manager_id)

    _require_property_belongs_to_agency(db, property_id, agency_manager_id)

    assignee = db.query(ManagerUser).filter(ManagerUser.id == assignee_user_id).first()
    if not assignee:
        raise HTTPException(status_code=404, detail="Assignee staff not found")
    if assignee.manager_id != agency_manager_id:
        raise HTTPException(status_code=403, detail="Assignee must be a staff member under your agency")
    if not bool(getattr(assignee, "active", True)):
        raise HTTPException(status_code=400, detail="Assignee is inactive")

    # one-active policy per property
    (
        db.query(PropertyAgentAssignment)
        .filter(PropertyAgentAssignment.property_id == property_id, PropertyAgentAssignment.active.is_(True))
        .update({"active": False}, synchronize_session=False)
    )

    assignment = PropertyAgentAssignment(
        property_id=property_id,
        assignee_user_id=assignee_user_id,
        assigned_by_user_id=assigned_by_user_id,
        active=True,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return {
        "id": assignment.id,
        "property_id": assignment.property_id,
        "assignee_user_id": assignment.assignee_user_id,
        "assigned_by_user_id": assignment.assigned_by_user_id,
        "active": bool(assignment.active),
    }


@router.patch("/properties/{property_id}/unassign-staff")
def unassign_property_from_staff(
    property_id: int,
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials = Depends(bearer),
):
    """
    Unassign the currently active INTERNAL staff assignment for this property.
    Admin-only. Property must belong to this agency.
    """
    payload = _decode(creds)
    _require_manager(payload)
    _require_admin(payload)

    _, agency_manager_id = _get_ids(payload)
    _require_agency_org(db, agency_manager_id)

    _require_property_belongs_to_agency(db, property_id, agency_manager_id)

    row = (
        db.query(PropertyAgentAssignment)
        .filter(
            PropertyAgentAssignment.property_id == property_id,
            PropertyAgentAssignment.active.is_(True),
        )
        .order_by(PropertyAgentAssignment.id.desc())
        .first()
    )
    if not row:
        # returning 200 is also okay, but keeping it strict helps you notice mistakes
        raise HTTPException(status_code=404, detail="No active staff assignment for this property")

    row.active = False
    db.commit()
    db.refresh(row)

    return {
        "property_id": row.property_id,
        "assignee_user_id": row.assignee_user_id,
        "active": bool(row.active),
    }


# ---------------------------
# Assign properties to EXTERNAL manager orgs (linked agents)
# ---------------------------

@router.post("/properties/{property_id}/assign-external/{agent_manager_id}", response_model=AssignPropertyOut)
def assign_property_to_external_manager(
    property_id: int,
    agent_manager_id: int,
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials = Depends(bearer),
):
    payload = _decode(creds)
    _require_manager(payload)
    _require_admin(payload)

    assigned_by_user_id, agency_manager_id = _get_ids(payload)
    _require_agency_org(db, agency_manager_id)

    _require_property_belongs_to_agency(db, property_id, agency_manager_id)

    # agent must be linked and active
    link = (
        db.query(AgencyAgentLink)
        .filter(
            AgencyAgentLink.agency_manager_id == agency_manager_id,
            AgencyAgentLink.agent_manager_id == agent_manager_id,
            AgencyAgentLink.status == "active",
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=403, detail="That manager is not linked to your agency (or is inactive)")

    # one-active policy per property
    (
        db.query(PropertyExternalManagerAssignment)
        .filter(
            PropertyExternalManagerAssignment.property_id == property_id,
            PropertyExternalManagerAssignment.active.is_(True),
        )
        .update({"active": False}, synchronize_session=False)
    )

    row = PropertyExternalManagerAssignment(
        property_id=property_id,
        agent_manager_id=agent_manager_id,
        assigned_by_user_id=assigned_by_user_id,
        active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "id": row.id,
        "property_id": row.property_id,
        "assignee_user_id": None,  # keep schema compatibility
        "assigned_by_user_id": row.assigned_by_user_id,
        "active": bool(row.active),
    }


@router.patch("/properties/{property_id}/unassign-external")
def unassign_property_from_external_agent(
    property_id: int,
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials = Depends(bearer),
):
    """
    Unassign the currently active EXTERNAL agent assignment for this property.
    Admin-only. Property must belong to this agency.
    """
    payload = _decode(creds)
    _require_manager(payload)
    _require_admin(payload)

    _, agency_manager_id = _get_ids(payload)
    _require_agency_org(db, agency_manager_id)

    _require_property_belongs_to_agency(db, property_id, agency_manager_id)

    row = (
        db.query(PropertyExternalManagerAssignment)
        .filter(
            PropertyExternalManagerAssignment.property_id == property_id,
            PropertyExternalManagerAssignment.active.is_(True),
        )
        .order_by(PropertyExternalManagerAssignment.id.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="No active external assignment for this property")

    row.active = False
    db.commit()
    db.refresh(row)

    return {
        "property_id": row.property_id,
        "agent_manager_id": row.agent_manager_id,
        "active": bool(row.active),
    }


# ---------------------------
# Assignments list endpoints (for UI display)
# ---------------------------

@router.get("/assignments/staff")
def list_staff_assignments(
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials = Depends(bearer),
):
    payload = _decode(creds)
    _require_manager(payload)
    _require_admin(payload)

    _, agency_manager_id = _get_ids(payload)
    _require_agency_org(db, agency_manager_id)

    rows = (
        db.query(PropertyAgentAssignment)
        .join(Property, Property.id == PropertyAgentAssignment.property_id)
        .filter(
            Property.manager_id == agency_manager_id,
            PropertyAgentAssignment.active.is_(True),
        )
        .order_by(PropertyAgentAssignment.id.desc())
        .all()
    )

    return [
        {
            "id": r.id,
            "property_id": r.property_id,
            "assignee_user_id": r.assignee_user_id,
            "assigned_by_user_id": r.assigned_by_user_id,
            "active": bool(r.active),
            "assigned_at": str(r.assigned_at),
        }
        for r in rows
    ]


@router.get("/assignments/external")
def list_external_assignments(
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials = Depends(bearer),
):
    payload = _decode(creds)
    _require_manager(payload)
    _require_admin(payload)

    _, agency_manager_id = _get_ids(payload)
    _require_agency_org(db, agency_manager_id)

    rows = (
        db.query(PropertyExternalManagerAssignment)
        .join(Property, Property.id == PropertyExternalManagerAssignment.property_id)
        .filter(
            Property.manager_id == agency_manager_id,
            PropertyExternalManagerAssignment.active.is_(True),
        )
        .order_by(PropertyExternalManagerAssignment.id.desc())
        .all()
    )

    return [
        {
            "id": r.id,
            "property_id": r.property_id,
            "agent_manager_id": r.agent_manager_id,
            "assigned_by_user_id": r.assigned_by_user_id,
            "active": bool(r.active),
            "assigned_at": str(r.assigned_at),
        }
        for r in rows
    ]
