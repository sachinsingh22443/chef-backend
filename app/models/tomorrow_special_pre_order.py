import uuid

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    Index,
)

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class TomorrowSpecialPreOrder(Base):
    __tablename__ = "tomorrow_special_pre_orders"

    __table_args__ = (
        Index(
            "idx_ts_preorder_special",
            "special_id",
        ),
        Index(
            "idx_ts_preorder_order",
            "order_id",
        ),
        Index(
            "idx_ts_preorder_customer",
            "customer_id",
        ),
        Index(
            "idx_ts_preorder_created",
            "created_at",
        ),
    )

    # =====================================================
    # 🆔 ID
    # =====================================================

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # =====================================================
    # 🍱 TOMORROW SPECIAL
    # =====================================================

    special_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "tomorrow_specials.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =====================================================
    # 🧾 ACTUAL ORDER
    # =====================================================

    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "orders.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    # =====================================================
    # 👤 CUSTOMER
    # =====================================================

    customer_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =====================================================
    # 📦 QUANTITY
    # =====================================================

    quantity = Column(
        Integer,
        nullable=False,
    )

    # =====================================================
    # 💰 PRICE SNAPSHOT
    # =====================================================

    unit_price = Column(
        Float,
        nullable=False,
    )

    total_amount = Column(
        Float,
        nullable=False,
    )

    # =====================================================
    # 🕒 CREATED
    # =====================================================

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    # =====================================================
    # 🔗 RELATIONSHIPS
    # =====================================================

    special = relationship(
        "TomorrowSpecial",
        lazy="selectin",
    )

    order = relationship(
        "Order",
        lazy="selectin",
    )

    customer = relationship(
        "User",
        lazy="selectin",
    )