from sqlalchemy import Column, String, ForeignKey,Float
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base import Base

class ChefProfile(Base):
    __tablename__ = "chef_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

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
    
from sqlalchemy import Column, String, Boolean
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base

from sqlalchemy import Column, String, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base
from datetime import datetime
from sqlalchemy import DateTime
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String)

    password = Column(String, nullable=False)

    role = Column(String, default="customer")
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    application_status = Column(String, nullable=True)
    rejection_reason = Column(String, nullable=True)  # 🔥 optional
    created_at = Column(DateTime, default=datetime.utcnow)
    profile_image = Column(String, nullable=True)

    # ✅ YAHI PAR HOGA
    chef_profile = relationship("ChefProfile", backref="user", uselist=False)
    