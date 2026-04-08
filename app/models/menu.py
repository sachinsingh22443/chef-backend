from sqlalchemy import Column, String, Float, Boolean, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import ARRAY
import uuid

from app.db.base import Base

class Menu(Base):
    __tablename__ = "menus"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chef_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    name = Column(String, nullable=False)
    description = Column(String)
    price = Column(Float, nullable=False)

    prep_time = Column(Integer)
    quantity = Column(Integer, default=1)

    category = Column(String)
    food_type = Column(String)

    calories = Column(Integer)
    protein = Column(Float)
    carbs = Column(Float)
    fats = Column(Float)

    ingredients = Column(ARRAY(String))
    image_urls = Column(ARRAY(String))

    is_available = Column(Boolean, default=True)