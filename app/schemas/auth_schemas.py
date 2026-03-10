from pydantic import BaseModel


class RegisterUser(BaseModel):
    """
    Public registration payload.

    Allowed public roles:
      - landlord
      - manager
      - tenant

    Blocked from self-registration:
      - admin
      - super_admin
    """
    name: str
    phone: str
    email: str | None = None
    password: str | None = None
    role: str  # "landlord" | "manager" | "tenant"

    # Tenant-only fields
    property_code: str | None = None
    unit_id: int | None = None
    unit_number: str | None = None

    # Common optional
    id_number: str | None = None

    # Manager-only fields
    manager_type: str | None = None  # "individual" | "agency"
    company_name: str | None = None
    contact_person: str | None = None
    office_phone: str | None = None
    office_email: str | None = None


class LoginUser(BaseModel):
    phone: str
    password: str | None = None
    role: str  # "super_admin" | "admin" | "landlord" | "manager" | "tenant"