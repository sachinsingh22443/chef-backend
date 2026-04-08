from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import List, Optional


class SubscriptionCreate(BaseModel):
    chef_id: UUID
    menu_id: UUID
    plan_name: str
    price: float
    meals_per_day: int

    customer_name: str
    dish_name: str

    delivery_days: List[str]
    delivery_time: str
    address: str

    start_date: datetime
    end_date: datetime


class SubscriptionResponse(BaseModel):
    id: UUID
    customer: str
    plan: str
    dish: str
    quantity: int
    startDate: str
    days: List[str]
    time: str
    amount: float
    status: str

    class Config:
        from_attributes = True