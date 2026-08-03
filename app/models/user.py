import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class ChefProfile(Base):
    __tablename__ = "chef_profiles"

    __table_args__ = (
        
        Index("idx_chefprofile_location", "latitude", "longitude"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    address = Column(String)
    fssai_number = Column(String)
    profile_image = Column(String)

    account_holder_name = Column(String)
    account_number = Column(String)
    ifsc_code = Column(String)

    fssai_document = Column(String)

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    bio = Column(String)
    location = Column(String)
    specialties = Column(String)

    user = relationship(
        "User",
        back_populates="chef_profile",
        lazy="selectin",
    )


class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        Index("idx_user_role", "role"),
        Index("idx_user_email_role", "email", "role"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name = Column(String, nullable=False, index=True)

    email = Column(
        String,
        unique=True,
        nullable=False,
        index=True,
    )

    phone = Column(String, index=True)

    password = Column(String, nullable=False)

    role = Column(String, default="customer", index=True)

    is_active = Column(Boolean, default=True, index=True)

    is_verified = Column(Boolean, default=False, index=True)

    application_status = Column(String, nullable=True)

    rejection_reason = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    profile_image = Column(String, nullable=True)

    chef_profile = relationship(
        "ChefProfile",
        back_populates="user",
        uselist=False,
        lazy="selectin",
    )

    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )