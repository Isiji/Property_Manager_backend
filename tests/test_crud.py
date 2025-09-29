# tests/test_crud.py
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.user_models import Landlord, Tenant, PropertyManager, Admin
from app.models.property_models import Property, Unit, Lease
from app.database import TestingSessionLocal
from sqlalchemy.orm import Session
from app.models.maintenance_models import MaintenanceRequest
from app.models.payment_model import Payment, ServiceCharge


client = TestClient(app)

def test_create_landlord():
    payload = {"name": "Alice Smith", "phone": "0798765432", "email": "alice@example.com"}
    response = client.post("/landlords/", json=payload)
    print("CREATE LANDLORD RESPONSE:", response.json())
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["phone"] == payload["phone"]
    assert data["email"] == payload["email"]

def test_get_landlords():
    response = client.get("/landlords/")
    print("LIST LANDLORDS RESPONSE:", response.json())
    assert response.status_code == 200
    assert len(response.json()) > 0

def test_create_property():
    # Fetch first landlord id
    db = TestingSessionLocal()
    landlord = db.query(Landlord).first()
    db.close()
    payload = {"name": "Green Heights", "address": "Mombasa", "landlord_id": landlord.id}
    response = client.post("/properties/", json=payload)
    print("CREATE PROPERTY RESPONSE:", response.json())
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["landlord_id"] == payload["landlord_id"]

def test_create_unit():
    db = TestingSessionLocal()
    property_ = db.query(Property).first()
    db.close()
    payload = {"number": "B1", "rent_amount": 30000, "property_id": property_.id}
    response = client.post("/units/", json=payload)
    print("CREATE UNIT RESPONSE:", response.json())
    assert response.status_code == 201
    data = response.json()
    assert data["number"] == payload["number"]
    assert data["property_id"] == payload["property_id"]

def test_create_tenant_and_lease():
    db = TestingSessionLocal()
    unit = db.query(Unit).first()
    db.close()
    tenant_payload = {"name": "Bob Tenant", "phone": "0711223344", "email": "bob@example.com"}
    tenant_resp = client.post("/tenants/", json=tenant_payload)
    print("CREATE TENANT RESPONSE:", tenant_resp.json())
    assert tenant_resp.status_code == 201
    tenant_id = tenant_resp.json()["id"]

    lease_payload = {"tenant_id": tenant_id, "unit_id": unit.id, "start_date": "2025-09-01", "end_date": "2025-12-31", "active": True}
    lease_resp = client.post("/leases/", json=lease_payload)
    print("CREATE LEASE RESPONSE:", lease_resp.json())
    assert lease_resp.status_code == 201
    data = lease_resp.json()
    assert data["tenant_id"] == tenant_id
    assert data["unit_id"] == unit.id
