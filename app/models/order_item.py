
import uuid

from sqlalchemy import (
    Column,
    Integer,
    Float,
    ForeignKey,
    String,
    Index,
    Date,
)

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id"),
        index=True,
        nullable=False,
    )

    # =====================================================
    # NORMAL MENU
    # =====================================================

    menu_id = Column(
        UUID(as_uuid=True),
        ForeignKey("menus.id"),
        nullable=True,
        index=True,
    )

    # =====================================================
    # TOMORROW SPECIAL
    # =====================================================

    special_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tomorrow_specials.id"),
        nullable=True,
        index=True,
    )

    # =====================================================
    # EXPLORE PRODUCT
    # =====================================================

    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("explore_products.id"),
        nullable=True,
        index=True,
    )

    # =====================================================
    # ORDER DETAILS
    # =====================================================

    quantity = Column(
        Integer,
        nullable=False,
    )

    # Total price for this item, including quantity
    price = Column(
        Float,
        nullable=False,
    )

    # Snapshot of product/menu name at order time
    item_name = Column(
        String,
        index=True,
    )

    # Snapshot of product/menu image at order time
    item_image = Column(
        String,
        nullable=True,
    )

    # =====================================================
    # NORMAL MENU ORDER DETAILS
    # =====================================================

    # breakfast / lunch / dinner
    meal_type = Column(
        String,
        nullable=True,
        index=True,
    )

    # Actual menu date customer ordered
    menu_date = Column(
        Date,
        nullable=True,
        index=True,
    )

    # =====================================================
    # RELATIONSHIP
    # =====================================================

    order = relationship(
        "Order",
        back_populates="items",
        lazy="selectin",
    )

    # =====================================================
    # INDEXES
    # =====================================================

    __table_args__ = (
        Index(
            "idx_orderitem_order_menu",
            "order_id",
            "menu_id",
        ),
        Index(
            "idx_orderitem_order_special",
            "order_id",
            "special_id",
        ),
        Index(
            "idx_orderitem_order_product",
            "order_id",
            "product_id",
        ),
        Index(
            "idx_orderitem_menu_quantity",
            "menu_id",
            "quantity",
        ),
        Index(
            "idx_orderitem_meal_date",
            "meal_type",
            "menu_date",
        ),
    )
