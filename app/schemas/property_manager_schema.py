from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List
from app.schemas.property_schema import PropertyOut  # so we can show properties

class PropertyManagerBase(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None
    id_number: Optional[str] = None
 # org fields (optional for existing flows)
    type: Optional[str] = "individual"  # "individual" | "agency"
    company_name: Optional[str] = None
    contact_person: Optional[str] = None
    office_phone: Optional[str] = None
    office_email: Optional[str] = None
    logo_url: Optional[str] = None


class PropertyManagerCreate(PropertyManagerBase):
    password: str  # required for creation

class PropertyManagerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    id_number: Optional[str] = None

    type: Optional[str] = None
    company_name: Optional[str] = None
    contact_person: Optional[str] = None
    office_phone: Optional[str] = None
    office_email: Optional[str] = None
    logo_url: Optional[str] = None



class PropertyManagerOut(PropertyManagerBase):
    id: int
    properties: List[PropertyOut] = []   # include all managed properties

    class Config:
        model_config = ConfigDict(from_attributes=True)
