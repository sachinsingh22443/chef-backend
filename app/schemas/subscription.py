from pydantic import BaseModel
from typing import List
from uuid import UUID
from datetime import datetime


# =========================================================
# CREATE SUBSCRIPTION
# frontend → backend
# =========================================================

class SubscriptionCreate(BaseModel):
    chef_id: UUID
    menu_id: UUID

    plan_id: str

    meals_per_day: int

    # =====================================================
    # BREAKFAST ADD-ON
    # =====================================================

    breakfast_enabled: bool = False
    breakfast_price: float = 0.0

    # =====================================================
    # DELIVERY
    # =====================================================

    delivery_days: List[str]
    delivery_time: str
    address: str

    # =====================================================
    # DATES
    # =====================================================

    start_date: datetime
    end_date: datetime


# =========================================================
# RESPONSE
# backend → frontend
# =========================================================

class SubscriptionOut(BaseModel):
    id: UUID

    plan_id: str
    price: float

    meals_per_day: int
    dish_name: str

    # BREAKFAST
    breakfast_enabled: bool = False
    breakfast_price: float = 0.0

    # DELIVERY
    delivery_days: List[str]
    delivery_time: str
    address: str

    # DATES
    start_date: datetime
    end_date: datetime

    # STATUS
    status: str

    class Config:
        from_attributes = True