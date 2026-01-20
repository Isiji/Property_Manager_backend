from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import or_
from jose import jwt, JWTError

from app.auth.dependencies import get_db
from app.auth.jwt_utils import SECRET_KEY, ALGORITHM

from app.models.property_models import Property
from app.models.agency_models import PropertyAgentAssignment, PropertyExternalManagerAssignment

router = APIRouter(prefix="/properties", tags=["Properties"])
bearer = HTTPBearer(auto_error=False)

def _decode(creds: HTTPAuthorizationCredentials) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/me")
def properties_visible_to_me(
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials = Depends(bearer),
):
    """
    Returns properties the logged-in manager staff can access.

    Visibility rules:
    A) Properties owned by my org: Property.manager_id == my manager_id
    B) Properties assigned to me (internal staff assignment)
    C) Properties assigned to my org as an external agent (external assignment)
    """
    payload = _decode(creds)
    if payload.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Not a manager session")

    staff_id = int(payload.get("sub"))
    manager_id = int(payload.get("manager_id"))

    # A) org-managed
    q_org = db.query(Property.id).filter(Property.manager_id == manager_id)

    # B) staff assignments
    q_staff = (
        db.query(Property.id)
        .join(PropertyAgentAssignment, PropertyAgentAssignment.property_id == Property.id)
        .filter(PropertyAgentAssignment.assignee_user_id == staff_id, PropertyAgentAssignment.active == True)  # noqa
    )

    # C) external manager assignment (org-level)
    q_ext = (
        db.query(Property.id)
        .join(PropertyExternalManagerAssignment, PropertyExternalManagerAssignment.property_id == Property.id)
        .filter(PropertyExternalManagerAssignment.agent_manager_id == manager_id, PropertyExternalManagerAssignment.active == True)  # noqa
    )

    # union ids
    ids = set([r[0] for r in q_org.all()] + [r[0] for r in q_staff.all()] + [r[0] for r in q_ext.all()])
    if not ids:
        return []

    rows = db.query(Property).filter(Property.id.in_(list(ids))).order_by(Property.id.desc()).all()

    out = []
    for p in rows:
        out.append({
            "id": p.id,
            "name": getattr(p, "name", None),
            "address": getattr(p, "address", None),
            "property_code": getattr(p, "property_code", None),
            "manager_id": getattr(p, "manager_id", None),
            "landlord_id": getattr(p, "landlord_id", None),
        })
    return out
