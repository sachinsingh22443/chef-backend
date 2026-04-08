from pydantic import BaseModel
from uuid import UUID

class TomorrowSpecialCreate(BaseModel):
    dish_name: str
    description: str
    price: float
    max_plates: int
    cutoff_time: str


class TomorrowSpecialResponse(BaseModel):
    id: UUID
    dish_name: str
    description: str
    price: float
    max_plates: int
    cutoff_time: str

    class Config:
        from_attributes = True