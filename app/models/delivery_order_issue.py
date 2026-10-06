import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Text,
    ForeignKey,
    DateTime,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class DeliveryOrderIssue(Base):
    __tablename__ = "delivery_order_issues"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    delivery_order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("delivery_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    reported_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    issue_type = Column(
        String(50),
        nullable=False,
        index=True,
    )

    reason = Column(
        String(255),
        nullable=True,
    )

    notes = Column(
        Text,
        nullable=True,
    )

    status = Column(
        String(30),
        nullable=False,
        default="open",
        index=True,
    )

    resolved_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )

    resolved_at = Column(
        DateTime,
        nullable=True,
    )

    __table_args__ = (
        Index(
            "idx_delivery_issue_order_status",
            "delivery_order_id",
            "status",
        ),
        Index(
            "idx_delivery_issue_type_status",
            "issue_type",
            "status",
        ),
        Index(
            "idx_delivery_issue_created",
            "created_at",
        ),
    )