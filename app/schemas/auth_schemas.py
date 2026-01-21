from pydantic import BaseModel


class RegisterUser(BaseModel):
    """
    Registration payload for all roles.

    Tenants:
      - property_code + unit_number (preferred) OR property_code + unit_id (legacy)

    Managers:
      - manager_type: "individual" | "agency"
      - if agency, company_name is required
    """
    name: str
    phone: str
    email: str | None = None
    password: str | None = None
    role: str  # "admin" | "landlord" | "manager" | "tenant"

    # Tenant-only fields
    property_code: str | None = None
    unit_id: int | None = None
    unit_number: str | None = None

    # Common optional
    id_number: str | None = None

    # Manager-only fields (NEW)
    manager_type: str | None = None  # "individual" | "agency"
    company_name: str | None = None
    contact_person: str | None = None
    office_phone: str | None = None
    office_email: str | None = None


class LoginUser(BaseModel):
    phone: str
    password: str | None = None
    role: str  # "admin" | "landlord" | "manager" | "tenant"
