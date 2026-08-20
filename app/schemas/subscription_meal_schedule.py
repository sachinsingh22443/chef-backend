from datetime import date
from typing import Literal
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict


MealType = Literal[
    "breakfast",
    "lunch",
    "dinner",
]


MealStatus = Literal[
    "on",
    "off",
]


class SubscriptionMealScheduleOut(BaseModel):
    id: UUID
    subscription_id: UUID
    menu_id: UUID

    date: date
    meal_type: MealType

    meal_price: float
    status: Literal["on", "off"]

    cutoff_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class MealOffResponse(BaseModel):
    message: str
    subscription_id: UUID
    date: date
    meal_type: MealType

    status: Literal["off"]