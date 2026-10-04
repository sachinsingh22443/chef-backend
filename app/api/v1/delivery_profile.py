import os
import cloudinary
import cloudinary.uploader

from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
)

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.delivery_partner import DeliveryPartnerProfile


router = APIRouter(
    prefix="/delivery/profile",
    tags=["Delivery Partner Profile"],
)


# =========================================================
# HELPERS
# =========================================================

def get_profile(
    current_user: User,
    db: Session,
):
    if current_user.role != "delivery_partner":
        raise HTTPException(
            status_code=403,
            detail="Only delivery partners can access this profile",
        )

    profile = (
        db.query(DeliveryPartnerProfile)
        .filter(
            DeliveryPartnerProfile.user_id
            == current_user.id
        )
        .first()
    )

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Delivery partner profile not found",
        )

    return profile


# =========================================================
# GET PROFILE
# =========================================================

@router.get("")
def get_delivery_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = get_profile(
        current_user,
        db,
    )

    return {
        "success": True,

        "user": {
            "id": str(current_user.id),
            "name": current_user.name,
            "email": current_user.email,
            "phone": current_user.phone,
            "role": current_user.role,
            "is_active": current_user.is_active,
            "application_status":
                current_user.application_status,
        },

        "profile": {
            "id": str(profile.id),

            "profile_image":
                profile.profile_image,

            "date_of_birth":
                profile.date_of_birth,

            "address":
                profile.address,

            "city":
                profile.city,

            "state":
                profile.state,

            "pincode":
                profile.pincode,

            "vehicle_type":
                profile.vehicle_type,

            "vehicle_number":
                profile.vehicle_number,

            "driving_license_number":
                profile.driving_license_number,

            "driving_license_image":
                profile.driving_license_image,

            "id_proof_type":
                profile.id_proof_type,

            "id_proof_number":
                profile.id_proof_number,

            "id_proof_image":
                profile.id_proof_image,

            "account_holder_name":
                profile.account_holder_name,

            "account_number":
                profile.account_number,

            "ifsc_code":
                profile.ifsc_code,

            "employee_id":
                profile.employee_id,

            "joining_date":
                (
                    profile.joining_date.isoformat()
                    if profile.joining_date
                    else None
                ),

            "employment_type":
                profile.employment_type,

            "joining_location":
                profile.joining_location,

            "reporting_manager":
                profile.reporting_manager,

            "employment_status":
                profile.employment_status,

            "is_online":
                profile.is_online,

            "is_available":
                profile.is_available,

            "created_at":
                (
                    profile.created_at.isoformat()
                    if profile.created_at
                    else None
                ),
        },
    }


# =========================================================
# UPDATE PERSONAL PROFILE
# =========================================================

class DeliveryProfileUpdateSchema(BaseModel):

    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    phone: str | None = None

    date_of_birth: str | None = None

    address: str | None = None

    city: str | None = None

    state: str | None = None

    pincode: str | None = None

    vehicle_type: str | None = None

    vehicle_number: str | None = None


@router.put("")
def update_delivery_profile(
    data: DeliveryProfileUpdateSchema,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),
):

    profile = get_profile(
        current_user,
        db,
    )

    # -------------------------
    # USER DETAILS
    # -------------------------

    if data.name is not None:
        current_user.name = data.name.strip()

    if data.phone is not None:
        current_user.phone = data.phone.strip()

    # -------------------------
    # PROFILE DETAILS
    # -------------------------

    if data.date_of_birth is not None:
        profile.date_of_birth = data.date_of_birth

    if data.address is not None:
        profile.address = data.address.strip()

    if data.city is not None:
        profile.city = data.city.strip()

    if data.state is not None:
        profile.state = data.state.strip()

    if data.pincode is not None:
        profile.pincode = data.pincode.strip()

    if data.vehicle_type is not None:
        profile.vehicle_type = data.vehicle_type.strip()

    if data.vehicle_number is not None:
        profile.vehicle_number = (
            data.vehicle_number.strip().upper()
        )

    profile.updated_at = datetime.utcnow()

    db.commit()

    db.refresh(current_user)
    db.refresh(profile)

    return {
        "success": True,
        "message": "Profile updated successfully",
    }


# =========================================================
# PROFILE PHOTO
# =========================================================

@router.post("/photo")
async def upload_profile_photo(
    image: UploadFile = File(...),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),
):

    profile = get_profile(
        current_user,
        db,
    )

    allowed_types = {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
    }

    if image.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=(
                "Only JPG, JPEG, PNG or WEBP "
                "images are allowed"
            ),
        )

    image_bytes = await image.read()

    if len(image_bytes) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="Profile image must be under 5 MB",
        )

    try:

        result = cloudinary.uploader.upload(
            image_bytes,
            folder="delivery_partner/profile_images",
            resource_type="image",
        )

        profile.profile_image = result[
            "secure_url"
        ]

        profile.updated_at = datetime.utcnow()

        db.commit()

        db.refresh(profile)

        return {
            "success": True,
            "message": "Profile photo updated successfully",
            "profile_image":
                profile.profile_image,
        }

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to upload profile photo"
            ),
        )