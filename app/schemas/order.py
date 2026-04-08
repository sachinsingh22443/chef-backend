from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime

# =========================
# 🧾 CREATE SCHEMAS
# =========================

class OrderItemCreate(BaseModel):
    menu_id: UUID
    quantity: int


class OrderCreate(BaseModel):
    items: List[OrderItemCreate]

    # 🔥 NEW FIELD (IMPORTANT)
    address: str


# =========================
# 📦 RESPONSE SCHEMAS
# =========================

class OrderItemResponse(BaseModel):
    name: str
    quantity: int
    price: float
    image: Optional[str] = None


class OrderResponse(BaseModel):
    id: UUID
    status: str
    total_price: float

    # 🔥 NEW FIELDS
    customer_name: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    created_at: Optional[datetime]

    items: List[OrderItemResponse]

    class Config:
        from_attributes = True