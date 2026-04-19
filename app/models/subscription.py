from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
import uuid

from app.db.base import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 🔥 RELATIONS
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    chef_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    menu_id = Column(UUID(as_uuid=True), ForeignKey("menus.id"), index=True)

    # 🔥 PLAN RELATION (IMPORTANT CHANGE)
    plan_id = Column(String, ForeignKey("subscription_plans.id"), index=True)

    # 🔥 BASIC INFO
    customer_name = Column(String)
    dish_name = Column(String)

    # 🔥 PRICE (ALWAYS FROM BACKEND)
    price = Column(Float)
    meals_per_day = Column(Integer)

    # 🔥 DELIVERY
    delivery_days = Column(ARRAY(String))  # ["Mon", "Tue"]
    delivery_time = Column(String)
    address = Column(String)

    # 🔥 DATES
    start_date = Column(DateTime)
    end_date = Column(DateTime)

    # 🔥 STATUS
    status = Column(String, default="active")  # active, paused, cancelled, expired

    # 🔥 TIMESTAMP
    created_at = Column(DateTime(timezone=True), server_default=func.now())