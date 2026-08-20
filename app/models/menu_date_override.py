import uuid

from sqlalchemy import Column, Date, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class MenuDateOverride(Base):
    __tablename__ = "menu_date_overrides"

    __table_args__ = (
        UniqueConstraint(
            "chef_id",
            "menu_date",
            name="uq_menu_override_chef_date",
        ),
        Index(
            "idx_menu_override_chef_date",
            "chef_id",
            "menu_date",
        ),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    chef_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    menu_id = Column(
        UUID(as_uuid=True),
        ForeignKey("menus.id"),
        nullable=False,
        index=True,
    )

    menu_date = Column(
        Date,
        nullable=False,
    )