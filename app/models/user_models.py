# models.py (or wherever these live)
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
    id_number = Column(String, nullable=True, index=True)  # <— NEW

    properties = relationship(
        "Property",
        back_populates="landlord",
        cascade="all, delete-orphan"
    )
    payouts = relationship("LandlordPayout", back_populates="landlord", cascade="all, delete-orphan")

class PropertyManager(Base):
    __tablename__ = "property_managers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=True, index=True)
    password = Column(String, nullable=False)  # hashed password
    id_number = Column(String, nullable=True, index=True)  # <— NEW

    properties = relationship("Property", back_populates="manager")

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    password = Column(String, nullable=True)  # optional
    id_number = Column(String, nullable=True, index=True)  # <— NEW

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
    id_number = Column(String, nullable=True, index=True)  # <— NEW
