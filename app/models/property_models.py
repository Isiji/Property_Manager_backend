from sqlalchemy import Column, Numeric, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime
import uuid


class Property(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Name of the property
    address = Column(String, nullable=False)

    # ✅ Unique property code generated automatically
    property_code = Column(
        String, unique=True, nullable=False, index=True,
        default=lambda: str(uuid.uuid4())[:8].upper()
    )

    landlord_id = Column(Integer, ForeignKey("landlords.id", ondelete="CASCADE"), nullable=False)
    manager_id = Column(Integer, ForeignKey("property_managers.id"), nullable=True)

    landlord = relationship("Landlord", back_populates="properties")
    manager = relationship("PropertyManager", back_populates="properties")

    units = relationship("Unit", back_populates="property", cascade="all, delete-orphan")


class Unit(Base):
    __tablename__ = "units"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String, nullable=False)
    rent_amount = Column(Numeric(10, 2), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    occupied = Column(Integer, default=0)  # 0 = vacant, 1 = occupied

    # Relationships
    property = relationship("Property", back_populates="units")
    lease = relationship("Lease", back_populates="unit", uselist=False)
    payments = relationship(
        "Payment",
        back_populates="unit",
        cascade="all, delete-orphan"
    )
    service_charges = relationship(
        "ServiceCharge",
        back_populates="unit",
        cascade="all, delete-orphan"
    )
    maintenance_requests = relationship(
        "MaintenanceRequest",
        back_populates="unit",
        cascade="all, delete-orphan"
    )


class Lease(Base):
    __tablename__ = "leases"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)
    rent_amount = Column(Numeric(10,2), nullable=False)
    active = Column(Integer, default=1)   # 1 = active, 0 = inactive

    # Relationships
    tenant = relationship("Tenant", back_populates="leases")
    unit = relationship("Unit", back_populates="lease")
    payments = relationship(
        "Payment",
        back_populates="lease",
        cascade="all, delete-orphan"
    )
