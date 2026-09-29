# app/models/delivery_batch.py

import uuid

from datetime import datetime, date

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Date,
    DateTime,
    ForeignKey,
    Index,
)

from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class DeliveryBatch(Base):

    __tablename__ = "delivery_batches"

    # =========================================================
    # 🆔 PRIMARY KEY
    # =========================================================

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # =========================================================
    # 🚚 DELIVERY PARTNER
    # =========================================================

    delivery_partner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    # =========================================================
    # 📅 DELIVERY DATE
    # =========================================================

    delivery_date = Column(
        Date,
        nullable=False,
        index=True,
    )

    # =========================================================
    # 🍱 MEAL TYPE
    # =========================================================

    meal_type = Column(
        String,
        nullable=False,
        index=True,
    )

    # Examples:
    # breakfast
    # lunch
    # dinner
    # anytime
    # special

    # =========================================================
    # 🚦 BATCH STATUS
    # =========================================================

    status = Column(
        String,
        nullable=False,
        default="created",
        index=True,
    )

    # Possible:
    #
    # created
    # assigned
    # accepted
    # picking_up
    # picked_up
    # out_for_delivery
    # completed
    # cancelled

    # =========================================================
    # 📦 BATCH SUMMARY
    # =========================================================

    total_orders = Column(
        Integer,
        nullable=False,
        default=0,
    )

    total_tiffins = Column(
        Integer,
        nullable=False,
        default=0,
    )

    # =========================================================
    # 📍 START LOCATION
    # =========================================================

    start_latitude = Column(
        Float,
        nullable=True,
    )

    start_longitude = Column(
        Float,
        nullable=True,
    )

    # =========================================================
    # ⏱️ TIME
    # =========================================================

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )

    assigned_at = Column(
        DateTime,
        nullable=True,
    )

    started_at = Column(
        DateTime,
        nullable=True,
    )

    completed_at = Column(
        DateTime,
        nullable=True,
    )

    # =========================================================
    # 📊 INDEXES
    # =========================================================

    __table_args__ = (

        Index(
            "idx_delivery_batch_date_meal",
            "delivery_date",
            "meal_type",
        ),

        Index(
            "idx_delivery_batch_partner_status",
            "delivery_partner_id",
            "status",
        ),

        Index(
            "idx_delivery_batch_date_status",
            "delivery_date",
            "status",
        ),

    )