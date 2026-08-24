import uuid

from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    UniqueConstraint,
    Index,
    DateTime,
)

from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.sql import func

from app.db.base import Base


class SubscriptionPlanMenuCycle(Base):
    __tablename__ = "subscription_plan_menu_cycle"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # =====================================================
    # SUBSCRIPTION PLAN
    # =====================================================

    plan_id = Column(
        String,
        ForeignKey(
            "subscription_plans.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =====================================================
    # CYCLE DAY
    #
    # 1 → 30
    # =====================================================

    day_number = Column(
        Integer,
        nullable=False,
    )

    # =====================================================
    # MEAL TYPE
    #
    # breakfast
    # lunch
    # dinner
    # =====================================================

    meal_type = Column(
        String,
        nullable=False,
    )

    # =====================================================
    # EXISTING MENU
    #
    # IMPORTANT:
    # No new menu is created.
    # This references the existing Menu.
    # =====================================================

    menu_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "menus.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # =====================================================
    # CONSTRAINTS + INDEXES
    # =====================================================

    __table_args__ = (
        # One meal per type for each day of a plan
        UniqueConstraint(
            "plan_id",
            "day_number",
            "meal_type",
            name="uq_subscription_plan_cycle_day_meal",
        ),

        # Faster plan/day lookup
        Index(
            "idx_subscription_plan_cycle_plan_day",
            "plan_id",
            "day_number",
        ),

        # Faster menu lookup
        Index(
            "idx_subscription_plan_cycle_menu",
            "menu_id",
        ),
    )