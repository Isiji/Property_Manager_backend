from pydantic import BaseModel

class RegisterUser(BaseModel):
    name: str
    phone: str
    email: str | None = None
    password: str | None = None
    role: str   # admin, landlord, manager, tenant
    property_code: str | None = None
    unit_id: int | None = None


class LoginUser(BaseModel):
    phone: str
    password: str | None = None
    role: str   # admin, landlord, manager, tenant
