import uuid

from sqlalchemy import (
    Column,
    String,
    Float,
    Boolean,
    Integer,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from app.db.base import Base


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    __table_args__ = (
        Index(
            "idx_plan_chef_active",
            "chef_id",
            "is_active",
        ),
        Index(
            "idx_plan_goal_active",
            "goal",
            "is_active",
        ),
        Index(
            "idx_plan_diet_active",
            "diet_type",
            "is_active",
        ),
    )

    id = Column(
        String,
        primary_key=True,
    )

    chef_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    title = Column(
        String,
        nullable=False,
        index=True,
    )

    price = Column(
        Float,
        nullable=False,
    )

    description = Column(String)

    goal = Column(
        String,
        index=True,
    )

    diet_type = Column(
        String,
        index=True,
    )

    meal_type = Column(ARRAY(String))
    breakfast_available = Column(
      Boolean,
      default=False,
      nullable=False,
      )

    breakfast_price = Column(
     Float,
     nullable=True,
    )

    plan_type = Column(String)

    calories_per_day = Column(Integer)

    duration_days = Column(Integer)

    tagline = Column(String)

    emoji = Column(String)

    color = Column(String)

    features = Column(ARRAY(String))

    includes = Column(ARRAY(String))

    is_active = Column(
        Boolean,
        default=True,
        index=True,
    )