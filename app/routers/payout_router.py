# app/routers/payout_router.py
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user, role_required
from app.schemas.payout_schemas import PayoutCreate, PayoutUpdate, PayoutOut
from app.crud import payout_crud
from app import models

from app.services import audit_log_service


router = APIRouter(prefix="/payouts", tags=["Payouts"])


def _actor(current: dict) -> tuple[str, Optional[int]]:
    role = (current or {}).get("role") or "system"
    try:
        sub = int((current or {}).get("sub", 0) or 0)
    except Exception:
        sub = 0
    return role, (sub if sub > 0 else None)


def _manager_org_id(current: dict) -> Optional[int]:
    """
    Managers in your system:
      - sub: manager staff id
      - manager_id: org id (agency/individual org)
    We use manager_id to match Property.manager_id.
    """
    try:
        mid = int((current or {}).get("manager_id", 0) or 0)
        return mid if mid > 0 else None
    except Exception:
        return None


def _manager_can_view_landlord(db: Session, manager_org_id: int, landlord_id: int) -> bool:
    """
    Manager can view landlord payouts if they manage at least one property for that landlord.
    Uses Property.manager_id (org id).
    """
    exists = (
        db.query(models.Property.id)
        .filter(models.Property.manager_id == manager_org_id)
        .filter(models.Property.landlord_id == landlord_id)
        .first()
    )
    return bool(exists)


def _authorize_landlord_view(current: dict, landlord_id: int) -> None:
    role = (current or {}).get("role")
    if role != "landlord":
        return
    try:
        sub = int((current or {}).get("sub", 0) or 0)
    except Exception:
        sub = 0
    if sub != landlord_id:
        raise HTTPException(status_code=403, detail="Forbidden (landlord can only view own payouts)")


def _authorize_payout_view(db: Session, current: dict, landlord_id: int) -> None:
    role = (current or {}).get("role")

    if role == "admin":
        return

    if role == "landlord":
        _authorize_landlord_view(current, landlord_id)
        return

    if role in ("manager", "property_manager"):
        org_id = _manager_org_id(current)
        if not org_id:
            raise HTTPException(status_code=403, detail="Forbidden (missing manager_id in token)")
        if not _manager_can_view_landlord(db, org_id, landlord_id):
            raise HTTPException(status_code=403, detail="Forbidden (manager not assigned to this landlord)")
        return

    raise HTTPException(status_code=403, detail="Forbidden")


@router.post(
    "/",
    response_model=PayoutOut,
    dependencies=[Depends(role_required(["admin"]))],  # keep payouts creation controlled
)
def create_payout(
    payload: PayoutCreate,
    request: Request,
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    try:
        p = payout_crud.create_payout(db, payload)
        role, actor_id = _actor(current)
        audit_log_service.log(
            db,
            actor_role=role,
            actor_id=actor_id,
            action="payout.create",
            entity_type="payout",
            entity_id=getattr(p, "id", None),
            message="Created payout",
            meta={"landlord_id": getattr(p, "landlord_id", None), "amount": getattr(p, "amount", None)},
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return p
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{payout_id}", response_model=PayoutOut)
def read_payout(
    payout_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    p = payout_crud.get_payout(db, payout_id)
    if not p:
        raise HTTPException(status_code=404, detail="Payout not found")

    landlord_id = int(getattr(p, "landlord_id", 0) or 0)
    _authorize_payout_view(db, current, landlord_id)

    role, actor_id = _actor(current)
    audit_log_service.log(
        db,
        actor_role=role,
        actor_id=actor_id,
        action="payout.view",
        entity_type="payout",
        entity_id=payout_id,
        message="Viewed payout",
        meta={"landlord_id": landlord_id},
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return p


@router.get("/landlord/{landlord_id}", response_model=List[PayoutOut])
def list_payouts(
    landlord_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    _authorize_payout_view(db, current, landlord_id)

    rows = payout_crud.list_payouts_for_landlord(db, landlord_id)

    role, actor_id = _actor(current)
    audit_log_service.log(
        db,
        actor_role=role,
        actor_id=actor_id,
        action="payout.list",
        entity_type="landlord",
        entity_id=landlord_id,
        message="Listed landlord payouts",
        meta={"count": len(rows)},
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return rows


@router.put(
    "/{payout_id}",
    response_model=PayoutOut,
    dependencies=[Depends(role_required(["admin"]))],
)
def update_payout(
    payout_id: int,
    payload: PayoutUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    p = payout_crud.update_payout(db, payout_id, payload)
    if not p:
        raise HTTPException(status_code=404, detail="Payout not found")

    role, actor_id = _actor(current)
    audit_log_service.log(
        db,
        actor_role=role,
        actor_id=actor_id,
        action="payout.update",
        entity_type="payout",
        entity_id=payout_id,
        message="Updated payout",
        meta=payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return p


@router.delete(
    "/{payout_id}",
    response_model=dict,
    dependencies=[Depends(role_required(["admin"]))],
)
def delete_payout(
    payout_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    ok = payout_crud.delete_payout(db, payout_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Payout not found")

    role, actor_id = _actor(current)
    audit_log_service.log(
        db,
        actor_role=role,
        actor_id=actor_id,
        action="payout.delete",
        entity_type="payout",
        entity_id=payout_id,
        message="Deleted payout",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return {"ok": True}