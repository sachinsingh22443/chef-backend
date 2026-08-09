from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.db.base import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        index=True
    )

    chef_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        index=True
    )

    status = Column(
        String,
        default="pending",
        index=True
    )
    
    cod_confirmed = Column(
      Boolean,
      default=False,
      nullable=False
    )
    total_price = Column(Float)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )

    customer_name = Column(String)

    phone = Column(
        String,
        index=True
    )

    address = Column(String)

    payment_method = Column(String)

    payment_status = Column(
        String,
        default="pending",
        index=True
    )

    payment_id = Column(
        String,
        nullable=True,
        index=True
    )

    refund_status = Column(
        String,
        default="pending",
        index=True
    )

    refund_amount = Column(Float, nullable=True)

    refund_date = Column(DateTime, nullable=True)

    items = relationship(
        "OrderItem",
        back_populates="order",
        lazy="selectin"
    )

    __table_args__ = (
       Index("idx_order_user_status", "user_id", "status"),
       Index("idx_order_chef_status", "chef_id", "status"),
       Index("idx_order_created_status", "created_at", "status"),

       Index(
         "idx_order_chef_created",
         "chef_id",
         "created_at",
        ),
    )