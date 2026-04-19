from pydantic import BaseModel
from typing import List

class CartItemCreate(BaseModel):
    type: str        # "menu" | "special"
    item_id: str
    quantity: int


class CartResponse(BaseModel):
    items: List[dict]