import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Float,
    Date, 
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class DeliveryPartnerProfile(Base):
    __tablename__ = "delivery_partner_profiles"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Personal information
    date_of_birth = Column(String, nullable=True)

    address = Column(String, nullable=True)
    city = Column(String, nullable=True, index=True)
    state = Column(String, nullable=True)
    pincode = Column(String, nullable=True, index=True)

    # Profile
    profile_image = Column(String, nullable=True)

    # Vehicle
    vehicle_type = Column(String, nullable=True)
    vehicle_number = Column(String, nullable=True, index=True)

    # Driving licence
    driving_license_number = Column(String, nullable=True, index=True)
    driving_license_image = Column(String, nullable=True)

    # Identity proof
    id_proof_type = Column(String, nullable=True)
    id_proof_number = Column(String, nullable=True, index=True)
    id_proof_image = Column(String, nullable=True)

    # Bank details
    account_holder_name = Column(String, nullable=True)
    account_number = Column(String, nullable=True)
    ifsc_code = Column(String, nullable=True)

    # Delivery availability
    is_online = Column(Boolean, default=False, nullable=False, index=True)
    is_available = Column(Boolean, default=False, nullable=False, index=True)

    # Current location
    current_latitude = Column(Float, nullable=True)
    current_longitude = Column(Float, nullable=True)
    
    employee_id = Column(
        String(50),
        nullable=True,
        unique=True,
        index=True,
    )

    joining_date = Column(
        Date,
        nullable=True,
    )
    
    employment_type = Column(
        String(30),
        nullable=False,
        default="full_time",
    )
    
    joining_location = Column(
        String(150),
        nullable=True,
    )
    
    reporting_manager = Column(
        String(150),
        nullable=True,
    )
    
    employment_status = Column(
        String(30),
        nullable=False,
        default="active",
    )
    
    # Application
    application_status = Column(
        String,
        default="pending",
        nullable=False,
        index=True,
    )

    rejection_reason = Column(String, nullable=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        Index(
            "idx_delivery_partner_location",
            "current_latitude",
            "current_longitude",
        ),
        Index(
            "idx_delivery_partner_status",
            "application_status",
            "is_online",
            "is_available",
        ),
    )