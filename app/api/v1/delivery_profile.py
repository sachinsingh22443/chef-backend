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


# ============================================================
# CONSTANTS
# ============================================================

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


# ============================================================
# HELPERS
# ============================================================

def get_profile(
    current_user: User,
    db: Session,
):
    # --------------------------------------------------------
    # ROLE CHECK
    # --------------------------------------------------------

    if current_user.role != "delivery_partner":
        raise HTTPException(
            status_code=403,
            detail="Only delivery partners can access this profile",
        )

    # --------------------------------------------------------
    # ACTIVE CHECK
    # --------------------------------------------------------

    if not current_user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Delivery partner account is disabled",
        )

    # --------------------------------------------------------
    # APPROVAL CHECK
    # --------------------------------------------------------

    if current_user.application_status != "approved":
        raise HTTPException(
            status_code=403,
            detail="Delivery partner application is not approved",
        )

    # --------------------------------------------------------
    # PROFILE
    # --------------------------------------------------------

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


# ============================================================
# GET PROFILE
# ============================================================

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

        # ====================================================
        # USER
        # ====================================================

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

        # ====================================================
        # PROFILE
        # ====================================================

        "profile": {
            "id": str(profile.id),

            # ------------------------------------------------
            # PERSONAL
            # ------------------------------------------------

            "profile_image":
                profile.profile_image,

            "date_of_birth":
                profile.date_of_birth,

            # ------------------------------------------------
            # ADDRESS
            # ------------------------------------------------

            "address":
                profile.address,

            "city":
                profile.city,

            "state":
                profile.state,

            "pincode":
                profile.pincode,

            # ------------------------------------------------
            # VEHICLE
            # ------------------------------------------------

            "vehicle_type":
                profile.vehicle_type,

            "vehicle_number":
                profile.vehicle_number,

            # ------------------------------------------------
            # DOCUMENTS
            # ------------------------------------------------

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

            # ------------------------------------------------
            # BANK
            # ------------------------------------------------

            "account_holder_name":
                profile.account_holder_name,

            "account_number":
                profile.account_number,

            "ifsc_code":
                profile.ifsc_code,

            # ------------------------------------------------
            # EMPLOYMENT
            # ADMIN CONTROLLED
            # ------------------------------------------------

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

            # ------------------------------------------------
            # DRIVER STATUS
            # Dashboard controls these values.
            # Profile only returns them.
            # ------------------------------------------------

            "is_online":
                profile.is_online,

            "is_available":
                profile.is_available,

            "current_latitude":
                profile.current_latitude,

            "current_longitude":
                profile.current_longitude,

            # ------------------------------------------------
            # APPLICATION
            # ------------------------------------------------

            "rejection_reason":
                profile.rejection_reason,

            # ------------------------------------------------
            # TIMESTAMPS
            # ------------------------------------------------

            "created_at":
                (
                    profile.created_at.isoformat()
                    if profile.created_at
                    else None
                ),

            "updated_at":
                (
                    profile.updated_at.isoformat()
                    if profile.updated_at
                    else None
                ),
        },
    }


# ============================================================
# UPDATE PROFILE SCHEMA
# ============================================================

class DeliveryProfileUpdateSchema(BaseModel):

    # ========================================================
    # PERSONAL
    # ========================================================

    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    date_of_birth: str | None = Field(
        default=None,
        max_length=20,
    )

    # ========================================================
    # ADDRESS
    # ========================================================

    address: str | None = Field(
        default=None,
        max_length=300,
    )

    city: str | None = Field(
        default=None,
        max_length=100,
    )

    state: str | None = Field(
        default=None,
        max_length=100,
    )

    pincode: str | None = Field(
        default=None,
        max_length=10,
    )

    # ========================================================
    # VEHICLE
    # ========================================================

    vehicle_type: str | None = Field(
        default=None,
        max_length=50,
    )

    vehicle_number: str | None = Field(
        default=None,
        max_length=30,
    )

    # ========================================================
    # DOCUMENT DETAILS
    # ========================================================

    driving_license_number: str | None = Field(
        default=None,
        max_length=50,
    )

    id_proof_type: str | None = Field(
        default=None,
        max_length=50,
    )

    id_proof_number: str | None = Field(
        default=None,
        max_length=100,
    )

    # ========================================================
    # BANK
    # ========================================================

    account_holder_name: str | None = Field(
        default=None,
        max_length=150,
    )

    account_number: str | None = Field(
        default=None,
        max_length=50,
    )

    ifsc_code: str | None = Field(
        default=None,
        max_length=20,
    )


# ============================================================
# UPDATE PROFILE
# ============================================================

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

    # ========================================================
    # USER DETAILS
    # ========================================================

    # Only NAME can be changed.
    #
    # Phone and Email intentionally NOT included.
    # They are identity/login fields.

    if data.name is not None:

        name = data.name.strip()

        if not name:
            raise HTTPException(
                status_code=400,
                detail="Name cannot be empty",
            )

        current_user.name = name

    # ========================================================
    # DATE OF BIRTH
    # ========================================================

    if data.date_of_birth is not None:

        profile.date_of_birth = (
            data.date_of_birth.strip()
        )

    # ========================================================
    # ADDRESS
    # ========================================================

    if data.address is not None:

        profile.address = (
            data.address.strip()
        )

    if data.city is not None:

        profile.city = (
            data.city.strip()
        )

    if data.state is not None:

        profile.state = (
            data.state.strip()
        )

    if data.pincode is not None:

        profile.pincode = (
            data.pincode.strip()
        )

    # ========================================================
    # VEHICLE
    # ========================================================

    if data.vehicle_type is not None:

        profile.vehicle_type = (
            data.vehicle_type.strip()
        )

    if data.vehicle_number is not None:

        vehicle_number = (
            data.vehicle_number
            .strip()
            .upper()
        )

        if not vehicle_number:

            raise HTTPException(
                status_code=400,
                detail="Vehicle number cannot be empty",
            )

        # ----------------------------------------------------
        # DUPLICATE VEHICLE CHECK
        # ----------------------------------------------------

        existing_vehicle = (
            db.query(DeliveryPartnerProfile)
            .filter(
                DeliveryPartnerProfile.vehicle_number
                == vehicle_number,

                DeliveryPartnerProfile.user_id
                != current_user.id,
            )
            .first()
        )

        if existing_vehicle:

            raise HTTPException(
                status_code=400,
                detail="Vehicle number already registered",
            )

        profile.vehicle_number = vehicle_number

    # ========================================================
    # DRIVING LICENCE NUMBER
    # ========================================================

    if data.driving_license_number is not None:

        license_number = (
            data.driving_license_number
            .strip()
            .upper()
        )

        if not license_number:

            raise HTTPException(
                status_code=400,
                detail="Driving licence number cannot be empty",
            )

        # ----------------------------------------------------
        # DUPLICATE LICENCE CHECK
        # ----------------------------------------------------

        existing_license = (
            db.query(DeliveryPartnerProfile)
            .filter(
                DeliveryPartnerProfile
                .driving_license_number
                == license_number,

                DeliveryPartnerProfile.user_id
                != current_user.id,
            )
            .first()
        )

        if existing_license:

            raise HTTPException(
                status_code=400,
                detail="Driving licence already registered",
            )

        profile.driving_license_number = (
            license_number
        )

    # ========================================================
    # ID PROOF
    # ========================================================

    if data.id_proof_type is not None:

        profile.id_proof_type = (
            data.id_proof_type.strip()
        )

    if data.id_proof_number is not None:

        profile.id_proof_number = (
            data.id_proof_number.strip()
        )

    # ========================================================
    # BANK DETAILS
    # ========================================================

    if data.account_holder_name is not None:

        profile.account_holder_name = (
            data.account_holder_name.strip()
        )

    if data.account_number is not None:

        account_number = (
            data.account_number.strip()
        )

        if not account_number:

            raise HTTPException(
                status_code=400,
                detail="Account number cannot be empty",
            )

        profile.account_number = account_number

    if data.ifsc_code is not None:

        ifsc_code = (
            data.ifsc_code
            .strip()
            .upper()
        )

        if not ifsc_code:

            raise HTTPException(
                status_code=400,
                detail="IFSC code cannot be empty",
            )

        profile.ifsc_code = ifsc_code

    # ========================================================
    # UPDATED TIME
    # ========================================================

    profile.updated_at = datetime.utcnow()

    # ========================================================
    # SAVE
    # ========================================================

    try:

        db.commit()

        db.refresh(current_user)

        db.refresh(profile)

    except Exception as e:

        db.rollback()

        print(
            "DELIVERY PROFILE UPDATE ERROR:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to update profile",
        )

    return {
        "success": True,
        "message": "Profile updated successfully",
    }


# ============================================================
# PROFILE PHOTO
# ============================================================

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

    # ========================================================
    # FILE TYPE
    # ========================================================

    if image.content_type not in ALLOWED_IMAGE_TYPES:

        raise HTTPException(
            status_code=400,
            detail=(
                "Only JPG, JPEG, PNG or WEBP "
                "images are allowed"
            ),
        )

    # ========================================================
    # READ FILE
    # ========================================================

    image_bytes = await image.read()

    if not image_bytes:

        raise HTTPException(
            status_code=400,
            detail="Profile image is empty",
        )

    # ========================================================
    # FILE SIZE
    # ========================================================

    if len(image_bytes) > MAX_IMAGE_SIZE:

        raise HTTPException(
            status_code=400,
            detail="Profile image must be under 5 MB",
        )

    # ========================================================
    # CLOUDINARY
    # ========================================================

    try:

        result = cloudinary.uploader.upload(
            image_bytes,
            folder="delivery_partner/profile_images",
            resource_type="image",
        )

        profile_url = result.get(
            "secure_url"
        )

        if not profile_url:

            raise Exception(
                "Cloudinary secure URL missing"
            )

        profile.profile_image = profile_url

        profile.updated_at = datetime.utcnow()

        db.commit()

        db.refresh(profile)

    except Exception as e:

        db.rollback()

        print(
            "DELIVERY PROFILE PHOTO ERROR:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to upload profile photo",
        )

    return {
        "success": True,

        "message":
            "Profile photo updated successfully",

        "profile_image":
            profile.profile_image,
    }


# ============================================================
# DRIVING LICENCE IMAGE
# ============================================================

@router.post("/driving-license")
async def upload_driving_license(
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

    # ========================================================
    # FILE TYPE
    # ========================================================

    if image.content_type not in ALLOWED_IMAGE_TYPES:

        raise HTTPException(
            status_code=400,
            detail=(
                "Only JPG, JPEG, PNG or WEBP "
                "images are allowed"
            ),
        )

    # ========================================================
    # READ FILE
    # ========================================================

    image_bytes = await image.read()

    if not image_bytes:

        raise HTTPException(
            status_code=400,
            detail="Driving licence image is empty",
        )

    # ========================================================
    # FILE SIZE
    # ========================================================

    if len(image_bytes) > MAX_IMAGE_SIZE:

        raise HTTPException(
            status_code=400,
            detail=(
                "Driving licence image "
                "must be under 5 MB"
            ),
        )

    # ========================================================
    # CLOUDINARY
    # ========================================================

    try:

        result = cloudinary.uploader.upload(
            image_bytes,
            folder="delivery_partner/driving_licenses",
            resource_type="image",
        )

        license_url = result.get(
            "secure_url"
        )

        if not license_url:

            raise Exception(
                "Cloudinary secure URL missing"
            )

        profile.driving_license_image = (
            license_url
        )

        profile.updated_at = datetime.utcnow()

        db.commit()

        db.refresh(profile)

    except Exception as e:

        db.rollback()

        print(
            "DRIVING LICENSE UPLOAD ERROR:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to upload driving licence"
            ),
        )

    return {
        "success": True,

        "message":
            "Driving licence updated successfully",

        "driving_license_image":
            profile.driving_license_image,
    }


# ============================================================
# ID PROOF IMAGE
# ============================================================

@router.post("/id-proof")
async def upload_id_proof(
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

    # ========================================================
    # FILE TYPE
    # ========================================================

    if image.content_type not in ALLOWED_IMAGE_TYPES:

        raise HTTPException(
            status_code=400,
            detail=(
                "Only JPG, JPEG, PNG or WEBP "
                "images are allowed"
            ),
        )

    # ========================================================
    # READ FILE
    # ========================================================

    image_bytes = await image.read()

    if not image_bytes:

        raise HTTPException(
            status_code=400,
            detail="ID proof image is empty",
        )

    # ========================================================
    # FILE SIZE
    # ========================================================

    if len(image_bytes) > MAX_IMAGE_SIZE:

        raise HTTPException(
            status_code=400,
            detail=(
                "ID proof image "
                "must be under 5 MB"
            ),
        )

    # ========================================================
    # CLOUDINARY
    # ========================================================

    try:

        result = cloudinary.uploader.upload(
            image_bytes,
            folder="delivery_partner/id_proofs",
            resource_type="image",
        )

        id_proof_url = result.get(
            "secure_url"
        )

        if not id_proof_url:

            raise Exception(
                "Cloudinary secure URL missing"
            )

        profile.id_proof_image = (
            id_proof_url
        )

        profile.updated_at = datetime.utcnow()

        db.commit()

        db.refresh(profile)

    except Exception as e:

        db.rollback()

        print(
            "ID PROOF UPLOAD ERROR:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to upload ID proof",
        )

    return {
        "success": True,

        "message":
            "ID proof updated successfully",

        "id_proof_image":
            profile.id_proof_image,
    }