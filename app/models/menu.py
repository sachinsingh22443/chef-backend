from sqlalchemy import Column, String, Float, Boolean, ForeignKey, Integer, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import ARRAY
import uuid

from app.db.base import Base


class Menu(Base):
    __tablename__ = "menus"

    __table_args__ = (
       Index("idx_menu_chef_available", "chef_id", "is_available"),
       Index("idx_menu_category_available", "category", "is_available"),
       Index("idx_menu_foodtype_available", "food_type", "is_available"),

       Index(
         "idx_menu_chef_deleted_available",
         "chef_id",
         "is_deleted",
         "is_available",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    chef_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    name = Column(String, nullable=False, index=True)
    description = Column(String)

    price = Column(Float, nullable=False, index=True)

    prep_time = Column(Integer)
    quantity = Column(Integer, default=1)

    category = Column(String, index=True)
    food_type = Column(String, index=True)

    calories = Column(Integer)
    protein = Column(Float)
    carbs = Column(Float)
    fats = Column(Float)

    ingredients = Column(ARRAY(String))
    image_urls = Column(ARRAY(String))

    is_available = Column(Boolean, default=True, index=True)
    is_deleted = Column(Boolean, default=False, index=True)