
from datetime import date, datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# =========================================================
# MEAL TYPE
# =========================================================

MealType = Literal[
    "breakfast",
    "lunch",
    "dinner",
]


# =========================================================
# CREATE ORDER ITEM
# =========================================================

class OrderItemCreate(BaseModel):
    menu_id: Optional[UUID] = None
    special_id: Optional[UUID] = None
    product_id: Optional[UUID] = None

    quantity: int = Field(
        ...,
        gt=0,
    )

    # Normal menu fields
    meal_type: Optional[MealType] = None
    menu_date: Optional[date] = None

    @model_validator(mode="after")
    def validate_item_type(self):
        """
        Exactly one item ID must be supplied:
        menu_id, special_id or product_id.
        """

        selected_ids = [
            self.menu_id,
            self.special_id,
            self.product_id,
        ]

        selected_count = sum(
            value is not None
            for value in selected_ids
        )

        if selected_count != 1:
            raise ValueError(
                "Exactly one of menu_id, special_id "
                "or product_id must be provided."
            )

        # Meal fields are only valid for normal menu items.
        if self.menu_id is None and (
            self.meal_type is not None
            or self.menu_date is not None
        ):
            raise ValueError(
                "meal_type and menu_date can only be "
                "provided for normal menu items."
            )

        return self


# =========================================================
# CREATE ORDER
# =========================================================

class OrderCreate(BaseModel):
    items: List[OrderItemCreate] = Field(
        ...,
        min_length=1,
    )

    # Customer selected saved address
    address_id: UUID

    # Backward compatibility
    address: Optional[str] = None

    payment_method: str

    amount: Optional[float] = None

    is_subscription: bool = False


# =========================================================
# ORDER ITEM RESPONSE
# =========================================================

class OrderItemResponse(BaseModel):
    name: str
    quantity: int
    price: float
    image: Optional[str] = None


# =========================================================
# ORDER RESPONSE
# =========================================================

class OrderResponse(BaseModel):
    id: UUID
    status: str
    total_price: float

    customer_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    created_at: Optional[datetime] = None

    payment_method: str
    payment_status: str

    # Refund details
    refund_status: Optional[str] = None
    refund_amount: Optional[float] = None
    refund_date: Optional[datetime] = None

    items: List[OrderItemResponse]

    class Config:
        from_attributes = True
