import uuid

from sqlalchemy import (
    Column,
    String,
    Date,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.base import Base


class SubscriptionMealSchedule(Base):
    __tablename__ = "subscription_meal_schedule"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    subscription_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "subscriptions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    date = Column(
        Date,
        nullable=False,
        index=True,
    )

    meal_type = Column(
        String,
        nullable=False,
    )

    status = Column(
        String,
        nullable=False,
        default="on",
    )
    
    cutoff_at = Column(
      DateTime(timezone=True),
      nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            "date",
            "meal_type",
            name="uq_subscription_meal_date",
        ),

        Index(
            "idx_subscription_meal_date",
            "subscription_id",
            "date",
        ),
    )