import uuid

from sqlalchemy import (
    Column,
    String,
    Float,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.base import Base


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    wallet_id = Column(
        UUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    amount = Column(
        Float,
        nullable=False,
    )

    transaction_type = Column(
        String,
        nullable=False,
    )

    meal_type = Column(
        String,
        nullable=True,
    )

    subscription_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    schedule_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "subscription_meal_schedule.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    description = Column(
        String,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index(
            "idx_wallet_tx_user_created",
            "user_id",
            "created_at",
        ),
        Index(
            "idx_wallet_tx_subscription_meal",
            "subscription_id",
            "meal_type",
        ),
    )