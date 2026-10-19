
import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Float,
    Boolean,
    ForeignKey,
    Integer,
    DateTime,
    Index,
    Text,
)

from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class ExploreProduct(Base):
    __tablename__ = "explore_products"

    __table_args__ = (
        Index(
            "idx_explore_product_chef_active",
            "chef_id",
            "is_active",
        ),
        Index(
            "idx_explore_product_category_active",
            "category",
            "is_active",
        ),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Chef who owns this Explore product
    chef_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    name = Column(
        String,
        nullable=False,
        index=True,
    )

    description = Column(
        Text,
        nullable=True,
    )

    category = Column(
        String,
        nullable=False,
        index=True,
    )

    price = Column(
        Float,
        nullable=False,
    )

    image_url = Column(
        String,
        nullable=True,
    )

    quantity = Column(
        Integer,
        nullable=False,
        default=0,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
