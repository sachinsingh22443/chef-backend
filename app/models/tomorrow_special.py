from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.db.base import Base

class TomorrowSpecial(Base):
    __tablename__ = "tomorrow_specials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    chef_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    dish_name = Column(String)
    description = Column(String)

    price = Column(Float)
    max_plates = Column(Integer)

    cutoff_time = Column(String)  # simple rakha (HH:MM)

    image_url = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())