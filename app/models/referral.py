import uuid

from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Float,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
)

from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.sql import func

from app.db.base import Base


class Referral(Base):
    __tablename__ = "referrals"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    referrer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    referred_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    referral_code = Column(
        String(20),
        nullable=False,
        index=True,
    )

    status = Column(
        String(20),
        nullable=False,
        default="PENDING",
        index=True,
    )

    reward_amount = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    reward_type = Column(
        String(50),
        nullable=True,
    )

    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    subscription_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    rewarded_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancelled_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancellation_reason = Column(
        String,
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "referrer_id",
            "referred_user_id",
            name="uq_referral_referrer_referred",
        ),
        Index(
            "idx_referral_referrer_status",
            "referrer_id",
            "status",
        ),
    )