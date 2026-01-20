from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base


class Landlord(Base):
    __tablename__ = "landlords"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=True, index=True)
    password = Column(String, nullable=False)  # store hashed password
    id_number = Column(String, nullable=True, index=True)

    properties = relationship(
        "Property",
        back_populates="landlord",
        cascade="all, delete-orphan"
    )
    payouts = relationship("LandlordPayout", back_populates="landlord", cascade="all, delete-orphan")


class PropertyManager(Base):
    """
    This is now the "Manager Org":
    - type = individual | agency
    - can be assigned to many properties
    - can have multiple staff accounts (ManagerUser)
    """
    __tablename__ = "property_managers"

    id = Column(Integer, primary_key=True, index=True)

    # Keep existing "name/phone/email" as general contact/default display
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=True, index=True)

    # IMPORTANT: password is now moved to ManagerUser
    # Keep column for backward compatibility with existing DB,
    # but it will be set nullable by migration.
    password = Column(String, nullable=True)

    id_number = Column(String, nullable=True, index=True)

    # New org fields
    type = Column(String, nullable=False, default="individual")  # "individual" | "agency"
    company_name = Column(String, nullable=True)
    contact_person = Column(String, nullable=True)
    office_phone = Column(String, nullable=True)
    office_email = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)

    # Relationships
    properties = relationship("Property", back_populates="manager")
    staff = relationship("ManagerUser", back_populates="manager", cascade="all, delete-orphan")


class ManagerUser(Base):
    """
    Staff user under a manager org (agency or individual).
    This is what logs in for role="manager".
    """
    __tablename__ = "manager_users"

    id = Column(Integer, primary_key=True, index=True)
    manager_id = Column(Integer, ForeignKey("property_managers.id"), nullable=False, index=True)

    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=True, index=True)
    password_hash = Column(String, nullable=False)

    # optional staff id number
    id_number = Column(String, nullable=True, index=True)

    # optional role within manager org
    # (keep it simple now: "manager_staff" or "manager_admin")
    staff_role = Column(String, nullable=False, default="manager_staff")

    manager = relationship("PropertyManager", back_populates="staff")


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    password = Column(String, nullable=True)  # optional
    id_number = Column(String, nullable=True, index=True)

    leases = relationship("Lease", back_populates="tenant", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="tenant", cascade="all, delete-orphan")
    service_charges = relationship("ServiceCharge", back_populates="tenant", cascade="all, delete-orphan")
    maintenance_requests = relationship("MaintenanceRequest", back_populates="tenant", cascade="all, delete-orphan")


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    phone = Column(String, unique=True, nullable=True, index=True)
    password = Column(String, nullable=False)  # hashed password
    id_number = Column(String, nullable=True, index=True)
