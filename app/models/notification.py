# app/models/notification.py

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from app.db.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    type = Column(String, nullable=False)  # order, payment, review, system, offer
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)

    is_read = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # 🔥 optional (future use)
    action_url = Column(String, nullable=True)