from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.db.base import Base

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    chef_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    menu_id = Column(UUID(as_uuid=True), ForeignKey("menus.id"))  # ✅ ADD

    customer_name = Column(String)
    plan_name = Column(String)

    price = Column(Float)
    meals_per_day = Column(Integer)

    dish_name = Column(String)

    delivery_days = Column(ARRAY(String))  # ["Mon", "Tue"]
    delivery_time = Column(String)

    address = Column(String)

    start_date = Column(DateTime)
    end_date = Column(DateTime)

    status = Column(String, default="active")

    created_at = Column(DateTime(timezone=True), server_default=func.now())