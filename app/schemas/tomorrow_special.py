from pydantic import BaseModel
from uuid import UUID

class TomorrowSpecialCreate(BaseModel):
    dish_name: str
    description: str
    price: float
    max_plates: int
    cutoff_time: str


from pydantic import BaseModel
from uuid import UUID
from typing import Optional

class TomorrowSpecialResponse(BaseModel):
    id: UUID

    dish_name: str
    description: Optional[str]

    price: float

    max_plates: int
    pre_orders: int
    remaining: int

    cutoff_time: str

    image_url: Optional[str]

    chef_id: UUID
    chef_name: str

    is_active: int

    class Config:
        from_attributes = True
        
        
from pydantic import BaseModel
from uuid import UUID

class PreOrderCreate(BaseModel):
    special_id: UUID
    quantity: int = 1