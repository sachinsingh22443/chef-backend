from sqlalchemy import Column, String, Float, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.db.base import Base

from sqlalchemy import Column, String, Float, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.db.base import Base

class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    chef_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    status = Column(String, default="pending")
    total_price = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)

    customer_name = Column(String)
    phone = Column(String)
    address = Column(String)

    payment_method = Column(String)
    payment_status = Column(String, default="pending")
    payment_id = Column(String, nullable=True)

    # 🔥 REFUND SYSTEM
    refund_status = Column(String, default="pending")  # pending / processing / completed / failed
    refund_amount = Column(Float, nullable=True)
    refund_date = Column(DateTime, nullable=True)

    items = relationship("OrderItem", back_populates="order")
    
    
