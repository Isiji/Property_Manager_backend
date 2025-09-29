from app.models import user_models, property_models

def test_property_and_units(db_session):
    landlord = user_models.Landlord(name="John Doe", phone="0712345678", email="john@example.com")
    manager = user_models.PropertyManager(name="Alice Smith", phone="0723456789", email="alice@example.com")
    db_session.add_all([landlord, manager])
    db_session.commit()

    prop = property_models.Property(name="Sunset Apartments", landlord_id=landlord.id, manager_id=manager.id)
    db_session.add(prop)
    db_session.commit()
    assert prop.id is not None

    unit1 = property_models.Unit(name="Unit 101", property_id=prop.id)
    unit2 = property_models.Unit(name="Unit 102", property_id=prop.id)
    db_session.add_all([unit1, unit2])
    db_session.commit()

    assert len(prop.units) == 2

    # Test cascade delete
    db_session.delete(prop)
    db_session.commit()
    remaining_units = db_session.query(property_models.Unit).filter_by(property_id=prop.id).all()
    assert len(remaining_units) == 0
