# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.main import app
from app.dependencies import get_db
from fastapi.testclient import TestClient
from app.models import Landlord
from app.models import Tenant
from app.models import Property
from app.models import Unit

# Use a separate test database (you can configure PostgreSQL or SQLite for testing)
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"  # ✅ use SQLite in tests
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Override get_db so FastAPI uses the test DB
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    # Recreate all tables
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()

    # Insert sample landlord
    landlord = Landlord(name="John Doe", phone="0712345678", email="john@example.com")
    db.add(landlord)
    db.commit()
    db.refresh(landlord)

    # Insert sample tenant
    tenant = Tenant(name="Jane Tenant", phone="0723456789", email="jane@example.com")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    # Insert sample property
    property_ = Property(name="Sunset Villas", address="Nairobi", landlord_id=landlord.id)
    db.add(property_)
    db.commit()
    db.refresh(property_)

    # Insert sample unit
    unit = Unit(number="A1", rent_amount=25000, property_id=property_.id)
    db.add(unit)
    db.commit()
    db.refresh(unit)

    db.close()
    yield  # tests will run after this

@pytest.fixture()
def client():
    return TestClient(app)
