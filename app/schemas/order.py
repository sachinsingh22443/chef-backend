from datetime import date, datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# =========================================================
# MEAL TYPE
# =========================================================

MealType = Literal[
    "breakfast",
    "lunch",
    "dinner",
]


# =========================================================
# CREATE
# =========================================================

class OrderItemCreate(BaseModel):

    menu_id: Optional[UUID] = None

    special_id: Optional[UUID] = None

    quantity: int = Field(
        ...,
        gt=0,
    )

    # -----------------------------------------------------
    # NORMAL MENU
    # -----------------------------------------------------

    meal_type: Optional[MealType] = None

    menu_date: Optional[date] = None


class OrderCreate(BaseModel):

    items: List[OrderItemCreate]

    address: str

    payment_method: str

    amount: Optional[float] = None

    is_subscription: bool = False


# =========================================================
# RESPONSE
# =========================================================

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

    # -----------------------------------------------------
    # REFUND
    # -----------------------------------------------------

    refund_status: Optional[str]

    refund_amount: Optional[float]

    refund_date: Optional[datetime]

    items: List[OrderItemResponse]

    class Config:
        from_attributes = True