# app/routers/tenant.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.dependencies import get_db
from app.schemas.tenant_schema import TenantCreate, TenantOut, TenantUpdate
from app.crud import tenant as crud_tenant

router = APIRouter(prefix="/tenants", tags=["Tenants"])

@router.post("/", response_model=TenantOut)
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)):
    return crud_tenant.create_tenant(db, payload)

@router.get("/", response_model=List[TenantOut])
def list_tenants(db: Session = Depends(get_db)):
    return crud_tenant.get_tenants(db)

@router.get("/{tenant_id}", response_model=TenantOut)
def get_tenant(tenant_id: int, db: Session = Depends(get_db)):
    return crud_tenant.get_tenant(db, tenant_id)

@router.put("/{tenant_id}", response_model=TenantOut)
def update_tenant(tenant_id: int, payload: TenantUpdate, db: Session = Depends(get_db)):
    return crud_tenant.update_tenant(db, tenant_id, payload)

@router.delete("/{tenant_id}")
def delete_tenant(tenant_id: int, db: Session = Depends(get_db)):
    return crud_tenant.delete_tenant(db, tenant_id)
