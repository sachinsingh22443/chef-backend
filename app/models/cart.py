import uuid

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    Float,
    Date,
    Index,
)

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class Cart(Base):
    __tablename__ = "carts"

    __table_args__ = (
        Index("idx_cart_user", "user_id"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    items = relationship(
        "CartItem",
        back_populates="cart",
        cascade="all, delete",
        lazy="selectin",
    )


class CartItem(Base):
    __tablename__ = "cart_items"

    __table_args__ = (
        Index(
            "idx_cartitem_cart_menu",
            "cart_id",
            "menu_id",
        ),
        Index(
            "idx_cartitem_cart_special",
            "cart_id",
            "special_id",
        ),
        Index(
            "idx_cartitem_menu_date",
            "menu_id",
            "menu_date",
        ),
        Index(
            "idx_cartitem_meal_type",
            "meal_type",
        ),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    cart_id = Column(
        UUID(as_uuid=True),
        ForeignKey("carts.id"),
        nullable=False,
        index=True,
    )

    menu_id = Column(
        UUID(as_uuid=True),
        ForeignKey("menus.id"),
        nullable=True,
        index=True,
    )

    special_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tomorrow_specials.id"),
        nullable=True,
        index=True,
    )

    quantity = Column(
        Integer,
        default=1,
        nullable=False,
    )

    # =====================================================
    # SNAPSHOT
    # =====================================================

    name = Column(
        String,
        nullable=True,
    )

    price = Column(
        Float,
        nullable=True,
    )

    image = Column(
        String,
        nullable=True,
    )

    food_type = Column(
        String,
        index=True,
        nullable=True,
    )

    # =====================================================
    # NORMAL MENU CYCLE
    # =====================================================

    # The actual date for which customer is ordering
    menu_date = Column(
        Date,
        nullable=True,
        index=True,
    )

    # breakfast / lunch / dinner
    meal_type = Column(
        String,
        nullable=True,
        index=True,
    )

    # =====================================================
    # RELATIONSHIP
    # =====================================================

    cart = relationship(
        "Cart",
        back_populates="items",
        lazy="selectin",
    )