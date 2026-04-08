from sqlalchemy import Column, Float, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.db.base import Base

class Earning(Base):
    __tablename__ = "earnings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    chef_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    amount = Column(Float, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())