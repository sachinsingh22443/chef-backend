import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    __table_args__ = (
        Index(
            "idx_notification_user_created",
            "user_id",
            "created_at",
        ),
        Index(
            "idx_notification_user_read",
            "user_id",
            "is_read",
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

    type = Column(
        String,
        nullable=False,
    )

    title = Column(
        String,
        nullable=False,
    )

    message = Column(
        String,
        nullable=False,
    )

    is_read = Column(
        Boolean,
        default=False,
        index=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        index=True,
    )

    action_url = Column(
        String,
        nullable=True,
    )