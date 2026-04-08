from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.db.base import Base

class Review(Base):
    __tablename__ = "reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    chef_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    rating = Column(Integer)
    comment = Column(String)

    created_at = Column(DateTime(timezone=True), server_default=func.now())  # 🔥 ADD