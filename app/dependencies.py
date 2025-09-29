# app/dependencies.py
from .database import SessionLocal
from fastapi import Depends
from sqlalchemy.orm import Session

# Existing DB dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------
# Dummy current user dependency
# -------------------------
def get_current_user():
    """
    Returns a dummy current user for testing.
    Replace with JWT or real authentication later.
    """
    # Example: a tenant user
    return {"id": 1, "role": "tenant"}
    
    # Example: landlord user
    # return {"id": 2, "role": "landlord"}
