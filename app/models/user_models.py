# app/models/user_model.py
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base

class Landlord(Base):
    __tablename__ = "landlords"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=True)

    # Relationship with properties
    properties = relationship(
        "Property",
        back_populates="landlord",
        cascade="all, delete-orphan"   # ✅ cascade delete
    )

class PropertyManager(Base):
    __tablename__ = "property_managers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, index=True, nullable=True)

    # A manager can oversee many properties
    properties = relationship("Property", back_populates="manager")


class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, index=True, nullable=True)

    leases = relationship("Lease", back_populates="tenant", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="tenant", cascade="all, delete-orphan")
    service_charges = relationship("ServiceCharge", back_populates="tenant", cascade="all, delete-orphan")
    maintenance_requests = relationship("MaintenanceRequest", back_populates="tenant", cascade="all, delete-orphan")


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, unique=True, index=True, nullable=True)
    password = Column(String, nullable=False)  # hashed password later