import uuid

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Date,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class TomorrowSpecial(Base):
    __tablename__ = "tomorrow_specials"

    __table_args__ = (
        Index(
            "idx_special_chef_active",
            "chef_id",
            "is_active",
        ),
        Index(
            "idx_special_food_active",
            "food_type",
            "is_active",
        ),
        Index(
            "idx_special_created",
            "created_at",
        ),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    chef_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    # 🍽️ Dish
    dish_name = Column(
        String,
        nullable=False,
        index=True,
    )

    description = Column(String)

    # 💰 Pricing
    price = Column(Float, nullable=False)
    original_price = Column(Float, nullable=True)
    calories = Column(Integer, nullable=True)
    protein = Column(Float, nullable=True)
    carbs = Column(Float, nullable=True)
    fats = Column(Float, nullable=True)
    preparation_time = Column(Integer, nullable=True)
    ingredients = Column(String, nullable=True)
    max_plates = Column(Integer, nullable=False)
    pre_orders = Column(
        Integer,
        default=0,
    )
    special_date = Column(
     Date,
     nullable=False,
     index=True,
    )

    # ⏰ Timing
    cutoff_time = Column(String)

    # 🖼️ Image
    image_url = Column(String, nullable=True)

    # 📊 Status
    is_active = Column(
        Integer,
        default=1,
        index=True,
    )

    # 🌱 Food Type
    food_type = Column(
        String,
        default="veg",
        index=True,
    )

    # 🕒 Created
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    # 🔗 Relationship
    chef = relationship(
        "User",
        lazy="selectin",
    )