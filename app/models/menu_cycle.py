import uuid

from sqlalchemy import (
    Column,
    Date,
    Integer,
    String,
    ForeignKey,
    UniqueConstraint,
    Index,
)

from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class MenuCycle(Base):

    __tablename__ = "menu_cycles"

    __table_args__ = (

        # One meal can exist only once
        # for a particular day of a particular cycle.
        UniqueConstraint(
            "chef_id",
            "cycle_start_date",
            "cycle_day",
            "meal_type",
            name="uq_menu_cycle_chef_start_day_meal",
        ),

        Index(
            "idx_menu_cycle_chef_start_day_meal",
            "chef_id",
            "cycle_start_date",
            "cycle_day",
            "meal_type",
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

    menu_id = Column(
        UUID(as_uuid=True),
        ForeignKey("menus.id"),
        nullable=False,
        index=True,
    )

    cycle_day = Column(
        Integer,
        nullable=False,
    )

    cycle_start_date = Column(
        Date,
        nullable=False,
    )

    # breakfast / lunch / dinner
    meal_type = Column(
        String,
        nullable=False,
        index=True,
    )