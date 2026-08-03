import uuid

from sqlalchemy import (
    Column,
    String,
    Integer,
    ForeignKey,
    DateTime,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.base import Base


class Review(Base):
    __tablename__ = "reviews"

    __table_args__ = (
        Index(
            "idx_review_chef_created",
            "chef_id",
            "created_at",
        ),
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

    chef_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    rating = Column(
        Integer,
        nullable=False,
    )

    comment = Column(String)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )