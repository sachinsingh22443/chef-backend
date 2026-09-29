from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.delivery_partner import DeliveryPartnerProfile


router = APIRouter(
    prefix="/delivery",
    tags=["Delivery Partner"],
)


# =========================================================
# SCHEMAS
# =========================================================

class DeliveryOnlineStatusSchema(BaseModel):
    is_online: bool


class DeliveryAvailabilitySchema(BaseModel):
    is_available: bool


class DeliveryLocationSchema(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


# =========================================================
# HELPER
# =========================================================

def get_delivery_partner_profile(
    current_user: User,
    db: Session,
) -> DeliveryPartnerProfile:

    # -----------------------------------------------------
    # ROLE CHECK
    # -----------------------------------------------------
    if current_user.role != "delivery_partner":
        raise HTTPException(
            status_code=403,
            detail="Only delivery partners can access this endpoint",
        )

    # -----------------------------------------------------
    # ACTIVE CHECK
    # -----------------------------------------------------
    if not current_user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Delivery partner account is disabled",
        )

    # -----------------------------------------------------
    # APPROVAL CHECK
    # -----------------------------------------------------
    if current_user.application_status != "approved":
        raise HTTPException(
            status_code=403,
            detail="Delivery partner application is not approved",
        )

    # -----------------------------------------------------
    # PROFILE
    # -----------------------------------------------------
    profile = (
        db.query(DeliveryPartnerProfile)
        .filter(
            DeliveryPartnerProfile.user_id == current_user.id
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
# GET CURRENT DELIVERY STATUS
# =========================================================

@router.get("/status")
def get_delivery_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = get_delivery_partner_profile(
        current_user,
        db,
    )

    return {
        "user_id": str(current_user.id),
        "profile_id": str(profile.id),
        "role": current_user.role,
        "application_status": current_user.application_status,
        "is_active": current_user.is_active,
        "is_online": profile.is_online,
        "is_available": profile.is_available,
        "current_latitude": profile.current_latitude,
        "current_longitude": profile.current_longitude,
    }


# =========================================================
# ONLINE / OFFLINE
# =========================================================

@router.put("/status")
def update_online_status(
    data: DeliveryOnlineStatusSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = get_delivery_partner_profile(
        current_user,
        db,
    )

    # -----------------------------------------------------
    # GO OFFLINE
    # -----------------------------------------------------
    if data.is_online is False:

        profile.is_online = False

        # Offline partner ko new delivery nahi milegi
        profile.is_available = False

    # -----------------------------------------------------
    # GO ONLINE
    # -----------------------------------------------------
    else:

        profile.is_online = True

        # Online hone par automatically available nahi karenge.
        # Partner ko separate availability API se available hona hoga.
        profile.is_available = False

    profile.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(profile)

    return {
        "message": (
            "Delivery partner is now online"
            if profile.is_online
            else "Delivery partner is now offline"
        ),
        "user_id": str(current_user.id),
        "is_online": profile.is_online,
        "is_available": profile.is_available,
    }


# =========================================================
# AVAILABILITY
# =========================================================

@router.put("/availability")
def update_availability(
    data: DeliveryAvailabilitySchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = get_delivery_partner_profile(
        current_user,
        db,
    )

    # -----------------------------------------------------
    # AVAILABLE = TRUE
    # -----------------------------------------------------
    if data.is_available:

        # Offline partner available nahi ho sakta
        if not profile.is_online:
            raise HTTPException(
                status_code=400,
                detail=(
                    "You must be online before becoming available"
                ),
            )

        profile.is_available = True

    # -----------------------------------------------------
    # AVAILABLE = FALSE
    # -----------------------------------------------------
    else:

        profile.is_available = False

    profile.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(profile)

    return {
        "message": (
            "Delivery partner is now available"
            if profile.is_available
            else "Delivery partner is now unavailable"
        ),
        "user_id": str(current_user.id),
        "is_online": profile.is_online,
        "is_available": profile.is_available,
    }


# =========================================================
# UPDATE CURRENT LOCATION
# =========================================================

@router.put("/location")
def update_delivery_location(
    data: DeliveryLocationSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = get_delivery_partner_profile(
        current_user,
        db,
    )

    profile.current_latitude = data.latitude
    profile.current_longitude = data.longitude
    profile.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(profile)

    return {
        "message": "Delivery partner location updated successfully",
        "user_id": str(current_user.id),
        "latitude": profile.current_latitude,
        "longitude": profile.current_longitude,
        "is_online": profile.is_online,
        "is_available": profile.is_available,
    }