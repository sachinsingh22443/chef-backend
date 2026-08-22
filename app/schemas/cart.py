from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class CartItemCreate(BaseModel):
    type: str = Field(
        ...,
        description="menu or special",
    )

    item_id: str

    quantity: int = Field(
        ...,
        gt=0,
    )

    # =====================================================
    # NORMAL MENU CYCLE
    # =====================================================

    # Date customer wants to order for
    menu_date: Optional[date] = None

    # breakfast / lunch / dinner
    meal_type: Optional[str] = None


class CartResponse(BaseModel):
    items: List[dict]