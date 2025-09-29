from app.models import user_models

def test_create_landlord(db_session):
    landlord = user_models.Landlord(name="John Doe", phone="0712345678", email="john@example.com")
    db_session.add(landlord)
    db_session.commit()
    assert landlord.id is not None

def test_create_property_manager(db_session):
    manager = user_models.PropertyManager(name="Alice Smith", phone="0723456789", email="alice@example.com")
    db_session.add(manager)
    db_session.commit()
    assert manager.id is not None

def test_create_tenant(db_session):
    tenant = user_models.Tenant(name="Bob Tenant", phone="0734567890", email="bob@example.com")
    db_session.add(tenant)
    db_session.commit()
    assert tenant.id is not None

def test_create_admin(db_session):
    admin = user_models.Admin(name="Super Admin", phone="0700000000", email="admin@example.com", password="hashed")
    db_session.add(admin)
    db_session.commit()
    assert admin.id is not None
