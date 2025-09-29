# app/schemas/__init__.py
from .property_schema import PropertyCreate, PropertyUpdate, PropertyOut
from .unit_schema import UnitCreate, UnitUpdate, UnitOut
from .tenant_schema import TenantCreate, TenantUpdate, TenantOut
from .landlord_schema import LandlordCreate, LandlordUpdate, LandlordOut
from .lease_schema import LeaseCreate, LeaseUpdate, LeaseOut
from .payment_schema import PaymentCreate, PaymentUpdate, PaymentOut
from .service_charge_schema import ServiceChargeCreate, ServiceChargeUpdate, ServiceChargeOut
from .maintenance_schema import MaintenanceRequestCreate, MaintenanceRequestUpdate, MaintenanceRequestOut