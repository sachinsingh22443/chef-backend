from sqlalchemy import Column, Integer, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"))
    menu_id = Column(UUID(as_uuid=True), ForeignKey("menus.id"), nullable=True)
    special_id = Column(UUID(as_uuid=True), ForeignKey("tomorrow_specials.id"), nullable=True)
    quantity = Column(Integer)
    price = Column(Float)

    # ✅ NEW FIELDS (IMPORTANT)
    item_name = Column(String)
    item_image = Column(String)

    order = relationship("Order", back_populates="items")