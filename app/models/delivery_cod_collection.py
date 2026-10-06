import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    ForeignKey,
    DateTime,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class DeliveryCODCollection(Base):
    __tablename__ = "delivery_cod_collections"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    delivery_order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("delivery_orders.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    delivery_partner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    order_amount = Column(
        Float,
        nullable=False,
        default=0,
    )

    collected_amount = Column(
        Float,
        nullable=False,
        default=0,
    )

    payment_status = Column(
        String(30),
        nullable=False,
        default="pending",
        index=True,
    )

    collection_method = Column(
        String(30),
        nullable=True,
    )

    notes = Column(
        Text,
        nullable=True,
    )

    collected_at = Column(
        DateTime,
        nullable=True,
        index=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )

    __table_args__ = (
        Index(
            "idx_delivery_cod_partner_status",
            "delivery_partner_id",
            "payment_status",
        ),
        Index(
            "idx_delivery_cod_order_status",
            "order_id",
            "payment_status",
        ),
        Index(
            "idx_delivery_cod_collected_at",
            "collected_at",
        ),
    )