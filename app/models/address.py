from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db.base import Base

class Address(Base):
    __tablename__ = "addresses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # 🔥 NEW FIELDS
    name = Column(String)
    phone = Column(String)

    flat_no = Column(String)
    area = Column(String)
    landmark = Column(String)

    city = Column(String)
    state = Column(String)
    pincode = Column(String)

    address_type = Column(String)  # home / work / other

    # 🔥 FINAL FULL ADDRESS (optional but useful)
    address = Column(String)