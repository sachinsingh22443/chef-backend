from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base


class TomorrowSpecial(Base):
    __tablename__ = "tomorrow_specials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    chef_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # 🍽️ Dish
    dish_name = Column(String)
    description = Column(String)

    # 💰 Pricing
    price = Column(Float)

    # 📦 Quantity
    max_plates = Column(Integer)
    pre_orders = Column(Integer, default=0)   # 🔥 NEW

    # ⏰ Timing
    cutoff_time = Column(String)  # HH:MM

    # 🖼️ Image
    image_url = Column(String, nullable=True)

    # 📊 Status
    is_active = Column(Integer, default=1)  # 1 = active, 0 = sold out  🔥 NEW

    # 🕒 Created
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 🔗 Relationship
    chef = relationship("User")
    food_type = Column(String, default="veg")  # veg / non_veg