from sqlalchemy import Column, ForeignKey, Integer, String, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base


class Cart(Base):
    __tablename__ = "carts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    items = relationship("CartItem", back_populates="cart", cascade="all, delete")


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    cart_id = Column(UUID(as_uuid=True), ForeignKey("carts.id"))

    # 🔥 IMPORTANT (only once)
    menu_id = Column(UUID(as_uuid=True), ForeignKey("menus.id"), nullable=True)
    special_id = Column(UUID(as_uuid=True), ForeignKey("tomorrow_specials.id"), nullable=True)

    quantity = Column(Integer, default=1)

    # 🔥 SNAPSHOT (VERY IMPORTANT)
    name = Column(String)
    price = Column(Float)
    image = Column(String)
    food_type = Column(String)

    cart = relationship("Cart", back_populates="items")