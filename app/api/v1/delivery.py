from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.delivery_partner import DeliveryPartnerProfile
from app.services.delivery_assignment import run_delivery_assignment
from app.models.delivery_order import DeliveryOrder
from app.models.order import Order


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

        "application_status": (
            current_user.application_status
        ),

        "is_active": current_user.is_active,

        "is_online": profile.is_online,

        "is_available": profile.is_available,

        "current_latitude": (
            profile.current_latitude
        ),

        "current_longitude": (
            profile.current_longitude
        ),
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
        # Partner ko separate availability API se available
        # hona hoga.

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
    if profile.is_online and profile.is_available:

        try:
            assignment_result = run_delivery_assignment(
                db=db
            )
    
            print(
                "🚚 AUTO DELIVERY ASSIGNMENT:",
                assignment_result
            )
    
        except Exception as e:
            print(
                "⚠️ AUTO DELIVERY ASSIGNMENT ERROR:",
                str(e)
            )
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
    
    if profile.is_online and profile.is_available:

        try:
            assignment_result = run_delivery_assignment(
                db=db
            )
    
            print(
                "🚚 AUTO ASSIGN AFTER LOCATION UPDATE:",
                assignment_result
            )
    
        except Exception as e:
            print(
                "⚠️ AUTO ASSIGN LOCATION ERROR:",
                str(e)
            )

    db.refresh(profile)

    return {

        "message": (
            "Delivery partner location "
            "updated successfully"
        ),

        "user_id": str(current_user.id),

        "latitude": profile.current_latitude,

        "longitude": profile.current_longitude,

        "is_online": profile.is_online,

        "is_available": profile.is_available,
    }


# =========================================================
# 🚚 GET MY ASSIGNED DELIVERY ORDERS
# =========================================================


@router.get("/orders")
def get_my_delivery_orders(
    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),
):

    profile = get_delivery_partner_profile(
        current_user,
        db,
    )

    # =====================================================
    # GET ONLY ASSIGNED ORDERS
    # =====================================================

    delivery_orders = (
        db.query(
            DeliveryOrder,
            Order,
        )
        .join(
            Order,
            Order.id == DeliveryOrder.order_id,
        )
        .filter(
            DeliveryOrder.delivery_partner_id
            == current_user.id,

            DeliveryOrder.delivery_status.in_(
                [
                    "assigned",
                    "ready",
                    "out_for_delivery",
                ]
            ),
        )
        .order_by(
            DeliveryOrder.sequence_no.asc().nullslast(),
            DeliveryOrder.created_at.asc(),
        )
        .all()
    )

    orders = []

    for delivery_order, order in delivery_orders:

        orders.append({

            # =================================================
            # DELIVERY ORDER
            # =================================================

            "delivery_order_id": str(
                delivery_order.id
            ),

            "order_id": str(
                delivery_order.order_id
            ),

            "delivery_status": (
                delivery_order.delivery_status
            ),

            "sequence_no": (
                delivery_order.sequence_no
            ),

            # =================================================
            # CUSTOMER
            # =================================================

            "customer": {

                "id": str(
                    delivery_order.customer_id
                ),

                "name": (
                    delivery_order.customer_name
                ),

                "phone": (
                    delivery_order.customer_phone
                ),
            },

            # =================================================
            # DELIVERY ADDRESS
            # =================================================

            "address": {

                "full_address": (
                    delivery_order.address_snapshot
                ),

                "latitude": (
                    delivery_order.latitude
                ),

                "longitude": (
                    delivery_order.longitude
                ),
            },

            # =================================================
            # DELIVERY INFORMATION
            # =================================================

            "meal_type": (
                delivery_order.meal_type
            ),

            "total_tiffins": (
                delivery_order.total_tiffins
            ),

            # =================================================
            # BATCH
            # =================================================

            "batch_id": (
                str(delivery_order.batch_id)
                if delivery_order.batch_id
                else None
            ),

            # =================================================
            # MAIN ORDER STATUS
            # =================================================

            "order_status": (
                order.status
            ),

            # =================================================
            # TIMESTAMPS
            # =================================================

            "assigned_at": (
                delivery_order.assigned_at.isoformat()
                if delivery_order.assigned_at
                else None
            ),

            "picked_up_at": (
                delivery_order.picked_up_at.isoformat()
                if delivery_order.picked_up_at
                else None
            ),

            "delivered_at": (
                delivery_order.delivered_at.isoformat()
                if delivery_order.delivered_at
                else None
            ),

            "created_at": (
                delivery_order.created_at.isoformat()
                if delivery_order.created_at
                else None
            ),
        })

    # =====================================================
    # SUMMARY
    # =====================================================

    total_tiffins = sum(
        int(item["total_tiffins"] or 0)
        for item in orders
    )

    # =====================================================
    # RESPONSE
    # =====================================================

    return {

        "success": True,

        "delivery_partner": {

            "user_id": str(
                current_user.id
            ),

            "profile_id": str(
                profile.id
            ),

            "is_online": (
                profile.is_online
            ),

            "is_available": (
                profile.is_available
            ),

            "current_latitude": (
                profile.current_latitude
            ),

            "current_longitude": (
                profile.current_longitude
            ),
        },

        "summary": {

            "total_orders": len(
                orders
            ),

            "total_tiffins": (
                total_tiffins
            ),
        },

        "orders": orders,
    }


# =========================================================
# 🚚 GET SINGLE ASSIGNED DELIVERY ORDER
# =========================================================


@router.get(
    "/orders/{delivery_order_id}"
)
def get_my_delivery_order_detail(

    delivery_order_id: str,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),
):

    profile = get_delivery_partner_profile(
        current_user,
        db,
    )

    # =====================================================
    # VALIDATE UUID
    # =====================================================

    try:

        delivery_order_uuid = UUID(
            delivery_order_id
        )

    except ValueError:

        raise HTTPException(
            status_code=400,
            detail="Invalid delivery order ID",
        )

    # =====================================================
    # FIND ASSIGNED DELIVERY ORDER
    # =====================================================

    delivery_order = (
        db.query(DeliveryOrder)
        .filter(
            DeliveryOrder.id
            == delivery_order_uuid,

            DeliveryOrder.delivery_partner_id
            == current_user.id,
        )
        .first()
    )

    if not delivery_order:

        raise HTTPException(
            status_code=404,
            detail=(
                "Delivery order not found "
                "or this order is not assigned to you"
            ),
        )

    # =====================================================
    # GET MAIN ORDER
    # =====================================================

    order = (
        db.query(Order)
        .filter(
            Order.id
            == delivery_order.order_id
        )
        .first()
    )

    if not order:

        raise HTTPException(
            status_code=404,
            detail="Main order not found",
        )

    # =====================================================
    # RESPONSE
    # =====================================================

    return {

        "success": True,

        "delivery_partner": {

            "user_id": str(
                current_user.id
            ),

            "profile_id": str(
                profile.id
            ),

            "is_online": (
                profile.is_online
            ),

            "is_available": (
                profile.is_available
            ),

            "current_latitude": (
                profile.current_latitude
            ),

            "current_longitude": (
                profile.current_longitude
            ),
        },

        "order": {

            # =================================================
            # DELIVERY
            # =================================================

            "delivery_order_id": str(
                delivery_order.id
            ),

            "order_id": str(
                delivery_order.order_id
            ),

            "delivery_status": (
                delivery_order.delivery_status
            ),

            "order_status": (
                order.status
            ),

            "sequence_no": (
                delivery_order.sequence_no
            ),

            # =================================================
            # CUSTOMER
            # =================================================

            "customer": {

                "id": str(
                    delivery_order.customer_id
                ),

                "name": (
                    delivery_order.customer_name
                ),

                "phone": (
                    delivery_order.customer_phone
                ),
            },

            # =================================================
            # ADDRESS
            # =================================================

            "address": {

                "full_address": (
                    delivery_order.address_snapshot
                ),

                "latitude": (
                    delivery_order.latitude
                ),

                "longitude": (
                    delivery_order.longitude
                ),
            },

            # =================================================
            # DELIVERY INFORMATION
            # =================================================

            "meal_type": (
                delivery_order.meal_type
            ),

            "total_tiffins": (
                delivery_order.total_tiffins
            ),

            # =================================================
            # BATCH
            # =================================================

            "batch_id": (
                str(delivery_order.batch_id)
                if delivery_order.batch_id
                else None
            ),

            # =================================================
            # TIMESTAMPS
            # =================================================

            "assigned_at": (
                delivery_order.assigned_at.isoformat()
                if delivery_order.assigned_at
                else None
            ),

            "picked_up_at": (
                delivery_order.picked_up_at.isoformat()
                if delivery_order.picked_up_at
                else None
            ),

            "delivered_at": (
                delivery_order.delivered_at.isoformat()
                if delivery_order.delivered_at
                else None
            ),

            "created_at": (
                delivery_order.created_at.isoformat()
                if delivery_order.created_at
                else None
            ),
        },
    }