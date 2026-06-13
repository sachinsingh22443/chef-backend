from sqlalchemy import Column, String, Float, Boolean,Integer
from sqlalchemy.dialects.postgresql import ARRAY
from app.db.base import Base

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import ForeignKey
import uuid

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(String, primary_key=True)

    # 🔥 ADD THIS (MOST IMPORTANT)
    chef_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    title = Column(String, nullable=False)
    price = Column(Float, nullable=False)

    description = Column(String)
    
    goal = Column(String)

    diet_type = Column(String)

    meal_type = Column(ARRAY(String))

    calories_per_day = Column(Integer)

    duration_days = Column(Integer)
    tagline = Column(String)

    emoji = Column(String)
    color = Column(String)

    features = Column(ARRAY(String))
    includes = Column(ARRAY(String))

    is_active = Column(Boolean, default=True)