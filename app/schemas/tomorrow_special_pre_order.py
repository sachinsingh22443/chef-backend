from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# =========================================================
# 🍱 CREATE
# =========================================================

class TomorrowSpecialPreOrderCreate(BaseModel):

    special_id: UUID

    order_id: UUID

    quantity: int = Field(
        ...,
        gt=0,
    )

    unit_price: float = Field(
        ...,
        ge=0,
    )

    total_amount: float = Field(
        ...,
        ge=0,
    )


# =========================================================
# 📤 RESPONSE
# =========================================================

class TomorrowSpecialPreOrderResponse(BaseModel):

    id: UUID

    special_id: UUID

    order_id: UUID

    customer_id: UUID

    quantity: int

    unit_price: float

    total_amount: float

    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True