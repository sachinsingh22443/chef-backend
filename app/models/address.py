import uuid

from sqlalchemy import (
    Column,
    String,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class Address(Base):
    __tablename__ = "addresses"

    __table_args__ = (
        Index("idx_address_user_type", "user_id", "address_type"),
        Index("idx_address_city_state", "city", "state"),
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

    # 👤 Customer Info
    name = Column(String)

    phone = Column(
        String,
        index=True,
    )

    # 📍 Address
    flat_no = Column(String)

    area = Column(String)

    landmark = Column(String)

    city = Column(
        String,
        index=True,
    )

    state = Column(
        String,
        index=True,
    )

    pincode = Column(
        String,
        index=True,
    )

    address_type = Column(
        String,
        index=True,
    )

    # Full Address
    address = Column(String)