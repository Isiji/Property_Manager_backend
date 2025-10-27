# app/crud/payout_crud.py
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.payout_models import LandlordPayout, PayoutType
from app.schemas.payout_schemas import PayoutCreate, PayoutUpdate


def _clear_other_defaults(db: Session, landlord_id: int):
    db.query(LandlordPayout).filter(
        LandlordPayout.landlord_id == landlord_id,
        LandlordPayout.is_default == True,  # noqa: E712
    ).update({LandlordPayout.is_default: False})
    db.flush()


def create_payout(db: Session, payload: PayoutCreate) -> LandlordPayout:
    p = LandlordPayout(**payload.model_dump())
    db.add(p)
    if payload.is_default:
        _clear_other_defaults(db, payload.landlord_id)
        p.is_default = True
    db.commit()
    db.refresh(p)
    return p


def get_payout(db: Session, payout_id: int) -> LandlordPayout | None:
    return db.query(LandlordPayout).filter(LandlordPayout.id == payout_id).first()


def list_payouts_for_landlord(db: Session, landlord_id: int) -> list[LandlordPayout]:
    return (
        db.query(LandlordPayout)
        .filter(LandlordPayout.landlord_id == landlord_id)
        .order_by(LandlordPayout.is_default.desc(), LandlordPayout.created_at.desc())
        .all()
    )


def update_payout(db: Session, payout_id: int, payload: PayoutUpdate) -> LandlordPayout | None:
    p = get_payout(db, payout_id)
    if not p:
        return None

    data = payload.model_dump(exclude_unset=True)
    if "is_default" in data and data["is_default"]:
        _clear_other_defaults(db, p.landlord_id)

    for k, v in data.items():
        setattr(p, k, v)

    db.commit()
    db.refresh(p)
    return p


def delete_payout(db: Session, payout_id: int) -> bool:
    p = get_payout(db, payout_id)
    if not p:
        return False
    db.delete(p)
    db.commit()
    return True
