from pydantic import BaseModel


class RegisterUser(BaseModel):
    """
    Registration payload for all roles.
    - Tenants can register using property_code + unit_number (preferred) OR property_code + unit_id (legacy).
    """
    name: str
    phone: str
    email: str | None = None
    password: str | None = None
    role: str   # "admin" | "landlord" | "manager" | "tenant"

    # Tenant-only fields
    property_code: str | None = None
    unit_id: int | None = None          # legacy path (still supported)
    unit_number: str | None = None      # NEW: e.g. "A3"
    id_number: str | None = None        # optional national ID (snake_case)


class LoginUser(BaseModel):
    phone: str
    password: str | None = None
    role: str   # "admin" | "landlord" | "manager" | "tenant"
