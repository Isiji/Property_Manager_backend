from app.models import user_models, maintenance_models

def test_maintenance_requests(db_session):
    tenant = user_models.Tenant(name="Bob Tenant", phone="0734567890", email="bob@example.com")
    db_session.add(tenant)
    db_session.commit()

    request = maintenance_models.MaintenanceRequest(
        tenant_id=tenant.id,
        description="Leaky faucet"
    )
    db_session.add(request)
    db_session.commit()
    assert request.id is not None

    # Cascade delete
    db_session.delete(tenant)
    db_session.commit()
    assert db_session.query(maintenance_models.MaintenanceRequest).filter_by(tenant_id=tenant.id).first() is None
