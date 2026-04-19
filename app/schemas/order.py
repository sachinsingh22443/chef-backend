from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime

# =========================
# CREATE
# =========================

from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID

class OrderItemCreate(BaseModel):
    menu_id: Optional[UUID] = None
    special_id: Optional[UUID] = None
    quantity: int


class OrderCreate(BaseModel):
    items: List[OrderItemCreate]
    address: str
    payment_method: str


# =========================
# RESPONSE
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

    customer_name: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    created_at: Optional[datetime]

    payment_method: str
    payment_status: str

    # 🔥 NEW REFUND FIELDS
    refund_status: Optional[str]
    refund_amount: Optional[float]
    refund_date: Optional[datetime]

    items: List[OrderItemResponse]

    class Config:
        from_attributes = True