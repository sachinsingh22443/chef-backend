from pydantic import BaseModel
from typing import List

class SubscriptionPlanOut(BaseModel):
    id: str
    title: str
    price: float

    description: str | None = None
    tagline: str | None = None
    emoji: str | None = None
    color: str | None = None

    features: List[str] = []
    includes: List[str] = []

    # 🔥 ADD
    chef_id: str | None = None
    chef_name: str | None = None
    distance: float | None = None

    menu_id: str | None = None
    menu_name: str | None = None

    class Config:
        from_attributes = True