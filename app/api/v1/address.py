from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from app.api.deps import get_db, get_current_user
from app.models.address import Address
from app.schemas.address import AddressCreate

router = APIRouter(prefix="/address", tags=["Address"])


# ✅ ADD ADDRESS (UPDATED 🔥)
@router.post("/")
def add_address(
    data: AddressCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    # 🔥 FULL ADDRESS STRING
    full_address = f"{data.flatNo}, {data.area}, {data.city} - {data.pincode}"

    new_address = Address(
        id=uuid.uuid4(),
        user_id=user.id,

        # 🔥 NEW FIELDS
        name=data.name,
        phone=data.phone,

        flat_no=data.flatNo,
        area=data.area,
        landmark=data.landmark,

        city=data.city,
        state=data.state,
        pincode=data.pincode,

        address_type=data.addressType,

        # 🔥 FINAL ADDRESS STRING
        address=full_address
    )

    db.add(new_address)
    db.commit()
    db.refresh(new_address)

    return new_address


# ✅ GET ADDRESS (NO CHANGE)
@router.get("/")
def get_address(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    return db.query(Address).filter(Address.user_id == user.id).all()


# ✅ DELETE (IMPROVED 🔥)
@router.delete("/{id}")
def delete_address(
    id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    address = db.query(Address).filter(
        Address.id == id,
        Address.user_id == user.id   # 🔥 SECURITY FIX
    ).first()

    if not address:
        raise HTTPException(status_code=404, detail="Not found")

    db.delete(address)
    db.commit()

    return {"msg": "Deleted"}