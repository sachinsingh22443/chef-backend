from pydantic import BaseModel
from typing import List, Optional

class SubscriptionPlanOut(BaseModel):
    id: str
    title: str
    price: float

    # 🔥 NEW
    goal: Optional[str] = None
    diet_type: Optional[str] = None

    meal_type: List[str] = []
    breakfast_available: bool = False
    breakfast_price: float | None = None

    calories_per_day: Optional[int] = None
    duration_days: Optional[int] = None

    description: str | None = None
    tagline: str | None = None
    emoji: str | None = None
    color: str | None = None

    features: List[str] = []
    includes: List[str] = []

    chef_id: str | None = None
    chef_name: str | None = None
    distance: float | None = None

    menu_id: str | None = None
    menu_name: str | None = None

    class Config:
        from_attributes = True