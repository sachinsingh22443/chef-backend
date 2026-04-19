# schemas/address.py
from pydantic import BaseModel

class AddressCreate(BaseModel):
    name: str
    phone: str

    flatNo: str
    area: str
    landmark: str | None = None

    city: str
    state: str
    pincode: str

    addressType: str