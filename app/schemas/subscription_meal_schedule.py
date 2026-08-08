from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


MealType = Literal[
    "breakfast",
    "lunch",
    "dinner",
]


class SubscriptionMealScheduleOut(BaseModel):
    id: UUID
    subscription_id: UUID
    date: date
    meal_type: MealType
    status: Literal["on", "off"]

    model_config = ConfigDict(
        from_attributes=True
    )


class MealOffResponse(BaseModel):
    message: str
    subscription_id: UUID
    date: date
    meal_type: MealType
    status: Literal["off"]