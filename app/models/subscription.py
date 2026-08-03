import uuid

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func

from app.db.base import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    __table_args__ = (
        Index("idx_subscription_user_status", "user_id", "status"),
        Index("idx_subscription_chef_status", "chef_id", "status"),
        Index("idx_subscription_plan_status", "plan_id", "status"),
        Index("idx_subscription_dates", "start_date", "end_date"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # 🔥 RELATIONS
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    chef_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    menu_id = Column(
        UUID(as_uuid=True),
        ForeignKey("menus.id"),
        nullable=False,
        index=True,
    )

    plan_id = Column(
        String,
        ForeignKey("subscription_plans.id"),
        nullable=False,
        index=True,
    )

    # 🔥 BASIC INFO
    customer_name = Column(String)
    dish_name = Column(String)

    # 🔥 PRICE
    price = Column(Float, nullable=False)

    meals_per_day = Column(Integer)

    # 🔥 DELIVERY
    delivery_days = Column(ARRAY(String))
    delivery_time = Column(String)
    address = Column(String)

    # 🔥 DATES
    start_date = Column(DateTime, index=True)
    end_date = Column(DateTime, index=True)

    # 🔥 STATUS
    status = Column(
        String,
        default="active",
        index=True,
    )

    # 🔥 TIMESTAMP
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )