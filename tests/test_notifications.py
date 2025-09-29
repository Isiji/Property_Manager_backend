from app.models import user_models, notification_model

def create_user(session, user_type="landlord"):
    if user_type == "landlord":
        user = user_models.Landlord(name="John Doe", phone="0712345678", email="john@example.com")
    elif user_type == "property_manager":
        user = user_models.PropertyManager(name="Alice Smith", phone="0723456789", email="alice@example.com")
    elif user_type == "tenant":
        user = user_models.Tenant(name="Bob Tenant", phone="0734567890", email="bob@example.com")
    else:
        user = user_models.Admin(name="Super Admin", phone="0700000000", email="admin@example.com", password="hashed")
    session.add(user)
    session.commit()
    return user

def test_notification_for_all_users(db_session):
    for user_type in ["landlord", "property_manager", "tenant", "admin"]:
        user = create_user(db_session, user_type)
        notification = notification_model.Notification(
            user_id=user.id,
            title=f"{user_type.title()} Notification",
            message=f"Test message for {user_type}"
        )
        db_session.add(notification)
        db_session.commit()
        db_session.refresh(notification)
        assert notification.id is not None
        assert notification.user_id == user.id
