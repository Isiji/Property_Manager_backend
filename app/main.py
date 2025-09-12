# app/main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from . import models
from .database import engine, SessionLocal, Base
from pydantic import BaseModel
from typing import List

# create tables (first-time run)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Property Management API")

# DB dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Schemas
class TenantCreate(BaseModel):
    name: str
    email: str
    phone: str

class TenantOut(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    class Config:
        orm_mode = True

# Simple tenant endpoints
@app.post("/tenants/", response_model=TenantOut)
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)):
    # check duplicates
    exists = db.query(models.Tenant).filter(
        (models.Tenant.email == payload.email) | (models.Tenant.phone == payload.phone)
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="Tenant with email or phone already exists")
    t = models.Tenant(name=payload.name, email=payload.email, phone=payload.phone)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t

@app.get("/tenants/", response_model=List[TenantOut])
def list_tenants(db: Session = Depends(get_db)):
    return db.query(models.Tenant).all()
