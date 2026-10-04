import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    DateTime,
    ForeignKey,
    Index,
)

from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class DeliveryEarning(Base):
    __tablename__ = "delivery_earnings"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    delivery_partner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    delivery_order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("delivery_orders.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id"),
        nullable=False,
        index=True,
    )

    batch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("delivery_batches.id"),
        nullable=True,
        index=True,
    )

    earning_type = Column(
        String,
        nullable=False,
        default="per_order",
    )

    delivery_count = Column(
        Integer,
        nullable=False,
        default=1,
    )

    amount = Column(
        Numeric(10, 2),
        nullable=False,
        default=0,
    )

    status = Column(
        String,
        nullable=False,
        default="earned",
        index=True,
    )

    earned_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    __table_args__ = (
        Index(
            "idx_delivery_earning_partner_date",
            "delivery_partner_id",
            "earned_at",
        ),
        Index(
            "idx_delivery_earning_partner_status",
            "delivery_partner_id",
            "status",
        ),
    )