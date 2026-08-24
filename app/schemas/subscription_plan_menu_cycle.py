from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


MealType = Literal[
    "breakfast",
    "lunch",
    "dinner",
]


class SubscriptionPlanMenuCycleItem(BaseModel):
    """
    Single day + meal mapping.

    Example:
    Day 1 + lunch -> existing menu
    """

    day_number: int = Field(
        ...,
        ge=1,
        le=30,
        description="Subscription cycle day (1-30)",
    )

    meal_type: MealType

    menu_id: UUID


class SubscriptionPlanMenuCycleCreate(
    SubscriptionPlanMenuCycleItem
):
    """
    Used when creating/updating one mapping.
    """

    pass


class SubscriptionPlanMenuCycleOut(
    SubscriptionPlanMenuCycleItem
):
    """
    Backend -> Chef App
    """

    id: UUID

    plan_id: str

    created_at: datetime

    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class SubscriptionPlanMenuCycleBulkSave(BaseModel):
    """
    Used by Chef App to save the complete
    30-day subscription menu mapping.
    """

    items: list[
        SubscriptionPlanMenuCycleItem
    ] = Field(
        default_factory=list,
        max_length=90,
    )