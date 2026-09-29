# app/models/delivery_order.py

import uuid

from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    ForeignKey,
    DateTime,
    Index,
)

from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class DeliveryOrder(Base):

    __tablename__ = "delivery_orders"

    # =========================================================
    # 🆔 PRIMARY KEY
    # =========================================================

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # =========================================================
    # 🔗 ORIGINAL ORDER
    # =========================================================

    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    # =========================================================
    # 👤 CUSTOMER
    # =========================================================

    customer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    customer_name = Column(
        String,
        nullable=False,
    )

    customer_phone = Column(
        String,
        nullable=False,
        index=True,
    )

    # =========================================================
    # 📍 DELIVERY ADDRESS SNAPSHOT
    # =========================================================

    address_snapshot = Column(
        String,
        nullable=False,
    )

    latitude = Column(
        Float,
        nullable=True,
    )

    longitude = Column(
        Float,
        nullable=True,
    )

    # =========================================================
    # 🍱 DELIVERY DETAILS
    # =========================================================

    meal_type = Column(
        String,
        nullable=True,
        index=True,
    )

    total_tiffins = Column(
        Integer,
        nullable=False,
        default=0,
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
    # 📦 DELIVERY BATCH
    # =========================================================

    batch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("delivery_batches.id"),
        nullable=True,
        index=True,
    )

    # =========================================================
    # 🚦 DELIVERY STATUS
    # =========================================================

    delivery_status = Column(
        String,
        nullable=False,
        default="waiting",
        index=True,
    )

    # =========================================================
    # 🛣️ ROUTE SEQUENCE
    # =========================================================

    sequence_no = Column(
        Integer,
        nullable=True,
    )

    # =========================================================
    # ⏱️ DELIVERY TIMESTAMPS
    # =========================================================

    assigned_at = Column(
        DateTime,
        nullable=True,
    )

    picked_up_at = Column(
        DateTime,
        nullable=True,
    )

    delivered_at = Column(
        DateTime,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )

    # =========================================================
    # 📊 INDEXES
    # =========================================================

    __table_args__ = (

        Index(
            "idx_delivery_order_customer_status",
            "customer_id",
            "delivery_status",
        ),

        Index(
            "idx_delivery_order_partner_status",
            "delivery_partner_id",
            "delivery_status",
        ),

        Index(
            "idx_delivery_order_batch_sequence",
            "batch_id",
            "sequence_no",
        ),

        Index(
            "idx_delivery_order_location",
            "latitude",
            "longitude",
        ),

        Index(
            "idx_delivery_order_meal_status",
            "meal_type",
            "delivery_status",
        ),

    )