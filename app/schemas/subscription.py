from pydantic import BaseModel
from typing import List
from uuid import UUID
from datetime import datetime


# 🔥 CREATE (frontend → backend)
class SubscriptionCreate(BaseModel):
    chef_id: UUID
    menu_id: UUID

    plan_id: str   # 🔥 IMPORTANT

    meals_per_day: int

    delivery_days: List[str]
    delivery_time: str

    address: str

    start_date: datetime
    end_date: datetime


# 🔥 RESPONSE (backend → frontend)
class SubscriptionOut(BaseModel):
    id: UUID

    plan_id: str
    price: float

    meals_per_day: int
    dish_name: str

    delivery_days: List[str]
    delivery_time: str
    address: str

    start_date: datetime
    end_date: datetime

    status: str

    class Config:
        from_attributes = True