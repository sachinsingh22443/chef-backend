# ============================================================
# 🚚 DELIVERY BATCH PICKUP
# ============================================================

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    Index,
)

from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class DeliveryBatchPickup(Base):
    __tablename__ = "delivery_batch_pickups"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # --------------------------------------------------------
    # BATCH
    # --------------------------------------------------------

    batch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("delivery_batches.id"),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # CHEF
    # --------------------------------------------------------

    chef_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # PICKUP SEQUENCE
    # --------------------------------------------------------

    sequence_no = Column(
        Integer,
        nullable=False,
    )

    # --------------------------------------------------------
    # CHEF / KITCHEN SNAPSHOT
    # --------------------------------------------------------

    chef_name = Column(
        String,
        nullable=False,
    )

    kitchen_location = Column(
        String,
        nullable=True,
    )

    latitude = Column(
        Float,
        nullable=True,
    )

    longitude = Column(
        Float,
        nullable=True,
    )

    # --------------------------------------------------------
    # TIFFIN QUANTITY
    # --------------------------------------------------------

    expected_tiffins = Column(
        Integer,
        nullable=False,
        default=0,
    )

    received_tiffins = Column(
        Integer,
        nullable=False,
        default=0,
    )

    # --------------------------------------------------------
    # PICKUP STATUS
    #
    # pending
    # arrived
    # picked_up
    # issue
    # --------------------------------------------------------

    status = Column(
        String,
        nullable=False,
        default="pending",
        index=True,
    )

    # --------------------------------------------------------
    # TIMESTAMPS
    # --------------------------------------------------------

    arrived_at = Column(
        DateTime,
        nullable=True,
    )

    picked_up_at = Column(
        DateTime,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # --------------------------------------------------------
    # INDEXES
    # --------------------------------------------------------

    __table_args__ = (
        Index(
            "idx_delivery_pickup_batch_sequence",
            "batch_id",
            "sequence_no",
        ),

        Index(
            "idx_delivery_pickup_batch_status",
            "batch_id",
            "status",
        ),

        Index(
            "idx_delivery_pickup_chef",
            "chef_id",
        ),

        Index(
            "idx_delivery_pickup_location",
            "latitude",
            "longitude",
        ),
    )