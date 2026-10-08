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
from app.models.delivery_batch import DeliveryBatch
from app.models.delivery_batch_pickup import DeliveryBatchPickup
from app.models.delivery_order_event import DeliveryOrderEvent
from app.models.delivery_order_issue import DeliveryOrderIssue
from app.models.delivery_cod_collection import DeliveryCODCollection
from app.models.delivery_proof import DeliveryProof
from app.models.order_item import OrderItem


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
# PICKUP SCHEMAS
# =========================================================

class DeliveryPickupConfirmSchema(BaseModel):
    received_tiffins: int = Field(..., ge=0)
    
class DeliveryPickupResolveSchema(BaseModel):
    received_tiffins: int = Field(..., ge=0)


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


@router.get("/orders/{delivery_order_id}")
def get_my_delivery_order_detail(
    delivery_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = get_delivery_partner_profile(
        current_user,
        db,
    )

    # =====================================================
    # VALIDATE UUID
    # =====================================================

    try:
        delivery_order_uuid = UUID(delivery_order_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid delivery order ID",
        )

    # =====================================================
    # GET DELIVERY ORDER
    # =====================================================

    delivery_order = (
        db.query(DeliveryOrder)
        .filter(
            DeliveryOrder.id == delivery_order_uuid,
            DeliveryOrder.delivery_partner_id == current_user.id,
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
            Order.id == delivery_order.order_id
        )
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Main order not found",
        )

    # =====================================================
    # GET ORDER ITEMS
    # =====================================================

    order_items = (
        db.query(OrderItem)
        .filter(
            OrderItem.order_id == order.id
        )
        .order_by(OrderItem.menu_date.asc().nullslast())
        .all()
    )

    items = []

    for item in order_items:
        items.append(
            {
                "id": str(item.id),
                "menu_id": (
                    str(item.menu_id)
                    if item.menu_id
                    else None
                ),
                "special_id": (
                    str(item.special_id)
                    if item.special_id
                    else None
                ),
                "name": item.item_name,
                "quantity": item.quantity,
                "price": item.price,
                "image": item.item_image,
                "meal_type": item.meal_type,
                "menu_date": (
                    item.menu_date.isoformat()
                    if item.menu_date
                    else None
                ),
                "total": (
                    float(item.price or 0)
                    * int(item.quantity or 0)
                ),
            }
        )

    # =====================================================
    # GET DELIVERY EVENTS / TIMELINE
    # =====================================================

    events = (
        db.query(DeliveryOrderEvent)
        .filter(
            DeliveryOrderEvent.delivery_order_id
            == delivery_order.id
        )
        .order_by(
            DeliveryOrderEvent.created_at.asc()
        )
        .all()
    )

    timeline = []

    for event in events:
        timeline.append(
            {
                "id": str(event.id),
                "event_type": event.event_type,
                "status": event.status,
                "description": event.description,
                "latitude": event.latitude,
                "longitude": event.longitude,
                "created_by": (
                    str(event.created_by)
                    if event.created_by
                    else None
                ),
                "created_at": (
                    event.created_at.isoformat()
                    if event.created_at
                    else None
                ),
            }
        )

    # =====================================================
    # GET COD COLLECTION
    # =====================================================

    cod_collection = (
        db.query(DeliveryCODCollection)
        .filter(
            DeliveryCODCollection.delivery_order_id
            == delivery_order.id
        )
        .first()
    )

    cod_data = None

    if cod_collection:
        cod_data = {
            "id": str(cod_collection.id),
            "order_amount": float(
                cod_collection.order_amount or 0
            ),
            "collected_amount": float(
                cod_collection.collected_amount or 0
            ),
            "payment_status": (
                cod_collection.payment_status
            ),
            "collection_method": (
                cod_collection.collection_method
            ),
            "notes": cod_collection.notes,
            "collected_at": (
                cod_collection.collected_at.isoformat()
                if cod_collection.collected_at
                else None
            ),
            "created_at": (
                cod_collection.created_at.isoformat()
                if cod_collection.created_at
                else None
            ),
        }

    # =====================================================
    # GET DELIVERY PROOF
    # =====================================================

    delivery_proof = (
        db.query(DeliveryProof)
        .filter(
            DeliveryProof.delivery_order_id
            == delivery_order.id
        )
        .first()
    )

    proof_data = None

    if delivery_proof:
        proof_data = {
            "id": str(delivery_proof.id),
            "verification_type": (
                delivery_proof.verification_type
            ),
            "otp_verified": (
                delivery_proof.otp_verified
            ),
            "photo_url": delivery_proof.photo_url,
            "notes": delivery_proof.notes,
            "verified_at": (
                delivery_proof.verified_at.isoformat()
                if delivery_proof.verified_at
                else None
            ),
            "created_at": (
                delivery_proof.created_at.isoformat()
                if delivery_proof.created_at
                else None
            ),
        }

    # =====================================================
    # GET DELIVERY ISSUES
    # =====================================================

    issues = (
        db.query(DeliveryOrderIssue)
        .filter(
            DeliveryOrderIssue.delivery_order_id
            == delivery_order.id
        )
        .order_by(
            DeliveryOrderIssue.created_at.desc()
        )
        .all()
    )

    issue_data = []

    for issue in issues:
        issue_data.append(
            {
                "id": str(issue.id),
                "issue_type": issue.issue_type,
                "reason": issue.reason,
                "notes": issue.notes,
                "status": issue.status,
                "reported_by": (
                    str(issue.reported_by)
                    if issue.reported_by
                    else None
                ),
                "resolved_by": (
                    str(issue.resolved_by)
                    if issue.resolved_by
                    else None
                ),
                "created_at": (
                    issue.created_at.isoformat()
                    if issue.created_at
                    else None
                ),
                "resolved_at": (
                    issue.resolved_at.isoformat()
                    if issue.resolved_at
                    else None
                ),
            }
        )

    # =====================================================
    # PAYMENT INFORMATION
    # =====================================================

    payment_data = {
        "method": order.payment_method,
        "status": order.payment_status,
        "payment_id": order.payment_id,
        "razorpay_order_id": order.razorpay_order_id,
        "total_price": float(
            order.total_price or 0
        ),
        "cod_confirmed": bool(
            order.cod_confirmed
        ),
        "refund_status": order.refund_status,
        "refund_amount": (
            float(order.refund_amount)
            if order.refund_amount is not None
            else None
        ),
        "refund_date": (
            order.refund_date.isoformat()
            if order.refund_date
            else None
        ),
    }

    # =====================================================
    # DELIVERY PARTNER
    # =====================================================

    delivery_partner_data = {
        "user_id": str(current_user.id),
        "profile_id": str(profile.id),
        "name": current_user.name,
        "phone": current_user.phone,
        "is_online": profile.is_online,
        "is_available": profile.is_available,
        "current_latitude": profile.current_latitude,
        "current_longitude": profile.current_longitude,
    }

    # =====================================================
    # FINAL RESPONSE
    # =====================================================

    return {
        "success": True,

        "delivery_partner": delivery_partner_data,

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

            "order_status": order.status,

            "sequence_no": (
                delivery_order.sequence_no
            ),

            "batch_id": (
                str(delivery_order.batch_id)
                if delivery_order.batch_id
                else None
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
            # ORDER INFORMATION
            # =================================================

            "customer_name": order.customer_name,
            "customer_phone": order.phone,
            "is_subscription": bool(
                order.is_subscription
            ),

            "chef_id": (
                str(order.chef_id)
                if order.chef_id
                else None
            ),

            "order_created_at": (
                order.created_at.isoformat()
                if order.created_at
                else None
            ),

            # =================================================
            # ITEMS
            # =================================================

            "items": items,

            # =================================================
            # PAYMENT
            # =================================================

            "payment": payment_data,

            # =================================================
            # COD COLLECTION
            # =================================================

            "cod_collection": cod_data,

            # =================================================
            # DELIVERY PROOF
            # =================================================

            "delivery_proof": proof_data,

            # =================================================
            # TIMELINE / EVENTS
            # =================================================

            "timeline": timeline,

            # =================================================
            # ISSUES
            # =================================================

            "issues": issue_data,

            # =================================================
            # DELIVERY TIMESTAMPS
            # =================================================

            "created_at": (
                delivery_order.created_at.isoformat()
                if delivery_order.created_at
                else None
            ),

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
        },
    }
    
    

# =========================================================
# 🚚 GET MY BATCH PICKUP STOPS
# =========================================================

@router.get("/batches/{batch_id}/pickups")
def get_my_batch_pickups(
    batch_id: str,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),
):
    # -----------------------------------------------------
    # DELIVERY PARTNER VALIDATION
    # -----------------------------------------------------

    profile = get_delivery_partner_profile(
        current_user,
        db,
    )

    # -----------------------------------------------------
    # VALIDATE BATCH UUID
    # -----------------------------------------------------

    try:
        batch_uuid = UUID(batch_id)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid batch ID",
        )

    # -----------------------------------------------------
    # GET BATCH
    # -----------------------------------------------------

    batch = (
        db.query(DeliveryBatch)
        .filter(
            DeliveryBatch.id == batch_uuid,

            DeliveryBatch.delivery_partner_id
            == current_user.id,
        )
        .first()
    )

    if not batch:
        raise HTTPException(
            status_code=404,
            detail="Delivery batch not found",
        )

    # -----------------------------------------------------
    # GET PICKUPS
    # -----------------------------------------------------

    pickups = (
        db.query(DeliveryBatchPickup)
        .filter(
            DeliveryBatchPickup.batch_id
            == batch.id,
        )
        .order_by(
            DeliveryBatchPickup.sequence_no.asc()
        )
        .all()
    )

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    pickup_data = []

    for pickup in pickups:

        pickup_data.append(
            {
                "pickup_id": str(
                    pickup.id
                ),

                "batch_id": str(
                    pickup.batch_id
                ),

                "chef_id": str(
                    pickup.chef_id
                ),

                "sequence_no": (
                    pickup.sequence_no
                ),

                "chef_name": (
                    pickup.chef_name
                ),

                "kitchen_location": (
                    pickup.kitchen_location
                ),

                "latitude": (
                    pickup.latitude
                ),

                "longitude": (
                    pickup.longitude
                ),

                "expected_tiffins": (
                    pickup.expected_tiffins
                ),

                "received_tiffins": (
                    pickup.received_tiffins
                ),

                "status": (
                    pickup.status
                ),

                "arrived_at": (
                    pickup.arrived_at.isoformat()
                    if pickup.arrived_at
                    else None
                ),

                "picked_up_at": (
                    pickup.picked_up_at.isoformat()
                    if pickup.picked_up_at
                    else None
                ),
            }
        )

    # -----------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------

    total_expected = sum(
        int(
            pickup.expected_tiffins
            or 0
        )
        for pickup in pickups
    )

    total_received = sum(
        int(
            pickup.received_tiffins
            or 0
        )
        for pickup in pickups
    )

    completed_pickups = sum(
        1
        for pickup in pickups
        if pickup.status == "picked_up"
    )

    return {
        "success": True,

        "batch": {
            "id": str(batch.id),

            "delivery_date": str(
                batch.delivery_date
            ),

            "meal_type": (
                batch.meal_type
            ),

            "status": (
                batch.status
            ),

            "total_orders": (
                batch.total_orders
            ),

            "total_tiffins": (
                batch.total_tiffins
            ),
        },

        "summary": {
            "total_pickup_stops": len(
                pickups
            ),

            "completed_pickups": (
                completed_pickups
            ),

            "total_expected_tiffins": (
                total_expected
            ),

            "total_received_tiffins": (
                total_received
            ),
        },

        "pickups": pickup_data,
    }
    
# =========================================================
# 🚚 CONFIRM PICKUP
# =========================================================

# =========================================================
# 🚚 MARK PICKUP AS ARRIVED
# =========================================================

@router.post(
    "/pickups/{pickup_id}/arrive"
)
def arrive_at_pickup(
    pickup_id: str,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),
):
    # -----------------------------------------------------
    # DELIVERY PARTNER VALIDATION
    # -----------------------------------------------------

    profile = get_delivery_partner_profile(
        current_user,
        db,
    )

    # -----------------------------------------------------
    # VALIDATE UUID
    # -----------------------------------------------------

    try:
        pickup_uuid = UUID(pickup_id)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid pickup ID",
        )

    # -----------------------------------------------------
    # GET PICKUP + BATCH
    # -----------------------------------------------------

    pickup = (
        db.query(DeliveryBatchPickup)
        .join(
            DeliveryBatch,
            DeliveryBatch.id
            == DeliveryBatchPickup.batch_id,
        )
        .filter(
            DeliveryBatchPickup.id
            == pickup_uuid,

            DeliveryBatch.delivery_partner_id
            == current_user.id,
        )
        .first()
    )

    if not pickup:
        raise HTTPException(
            status_code=404,
            detail="Pickup stop not found",
        )

    # -----------------------------------------------------
    # ALREADY PICKED UP
    # -----------------------------------------------------

    if pickup.status == "picked_up":
        raise HTTPException(
            status_code=400,
            detail="This pickup has already been completed",
        )

    # -----------------------------------------------------
    # PICKUP SEQUENCE LOCK
    # -----------------------------------------------------

    previous_pickup = (
        db.query(DeliveryBatchPickup)
        .filter(
            DeliveryBatchPickup.batch_id
            == pickup.batch_id,

            DeliveryBatchPickup.sequence_no
            < pickup.sequence_no,
        )
        .order_by(
            DeliveryBatchPickup.sequence_no.desc()
        )
        .first()
    )

    if previous_pickup:

        if previous_pickup.status != "picked_up":

            raise HTTPException(
                status_code=400,
                detail={
                    "message": (
                        "You must complete the previous "
                        "chef pickup first"
                    ),

                    "current_chef": (
                        pickup.chef_name
                    ),

                    "current_sequence": (
                        pickup.sequence_no
                    ),

                    "previous_chef": (
                        previous_pickup.chef_name
                    ),

                    "previous_sequence": (
                        previous_pickup.sequence_no
                    ),

                    "previous_status": (
                        previous_pickup.status
                    ),
                },
            )

    # -----------------------------------------------------
    # STATUS CHECK
    # -----------------------------------------------------

    if pickup.status != "pending":

        raise HTTPException(
            status_code=400,
            detail=(
                f"Pickup cannot be marked arrived "
                f"from status '{pickup.status}'"
            ),
        )

    # -----------------------------------------------------
    # MARK ARRIVED
    # -----------------------------------------------------

    pickup.status = "arrived"

    pickup.arrived_at = datetime.utcnow()

    pickup.updated_at = datetime.utcnow()

    db.add(pickup)

    db.commit()

    db.refresh(pickup)

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return {
        "success": True,

        "message": (
            "Arrived at chef kitchen"
        ),

        "pickup": {
            "pickup_id": str(
                pickup.id
            ),

            "batch_id": str(
                pickup.batch_id
            ),

            "chef_id": str(
                pickup.chef_id
            ),

            "chef_name": (
                pickup.chef_name
            ),

            "sequence_no": (
                pickup.sequence_no
            ),

            "expected_tiffins": (
                pickup.expected_tiffins
            ),

            "received_tiffins": (
                pickup.received_tiffins
            ),

            "status": (
                pickup.status
            ),

            "arrived_at": (
                pickup.arrived_at.isoformat()
                if pickup.arrived_at
                else None
            ),
        },
    }

@router.post(
    "/pickups/{pickup_id}/confirm"
)
def confirm_pickup(
    pickup_id: str,

    data: DeliveryPickupConfirmSchema,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),
):
    # -----------------------------------------------------
    # DELIVERY PARTNER VALIDATION
    # -----------------------------------------------------

    profile = get_delivery_partner_profile(
        current_user,
        db,
    )

    # -----------------------------------------------------
    # VALIDATE UUID
    # -----------------------------------------------------

    try:
        pickup_uuid = UUID(pickup_id)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid pickup ID",
        )

    # -----------------------------------------------------
    # GET PICKUP + BATCH
    # -----------------------------------------------------

    pickup = (
        db.query(DeliveryBatchPickup)
        .join(
            DeliveryBatch,
            DeliveryBatch.id
            == DeliveryBatchPickup.batch_id,
        )
        .filter(
            DeliveryBatchPickup.id
            == pickup_uuid,

            DeliveryBatch.delivery_partner_id
            == current_user.id,
        )
        .first()
    )

    if not pickup:
        raise HTTPException(
            status_code=404,
            detail="Pickup stop not found",
        )

    # -----------------------------------------------------
    # MUST ARRIVE FIRST
    # -----------------------------------------------------

    if pickup.status == "pending":

        raise HTTPException(
            status_code=400,
            detail=(
                "You must mark arrived "
                "before confirming pickup"
            ),
        )

    # -----------------------------------------------------
    # ALREADY COMPLETED
    # -----------------------------------------------------
    
    # -----------------------------------------------------
# PICKUP SEQUENCE LOCK
# -----------------------------------------------------

    previous_pickup = (
        db.query(DeliveryBatchPickup)
        .filter(
            DeliveryBatchPickup.batch_id
            == pickup.batch_id,
    
            DeliveryBatchPickup.sequence_no
            < pickup.sequence_no,
        )
        .order_by(
            DeliveryBatchPickup.sequence_no.desc()
        )
        .first()
    )
    
    if previous_pickup:
    
        if previous_pickup.status != "picked_up":
    
            raise HTTPException(
                status_code=400,
                detail={
                    "message": (
                        "You must complete the previous "
                        "chef pickup first"
                    ),
    
                    "current_chef": (
                        pickup.chef_name
                    ),
    
                    "current_sequence": (
                        pickup.sequence_no
                    ),
    
                    "previous_chef": (
                        previous_pickup.chef_name
                    ),
    
                    "previous_sequence": (
                        previous_pickup.sequence_no
                    ),
    
                    "previous_status": (
                        previous_pickup.status
                    ),
                },
            )

    if pickup.status == "picked_up":

        raise HTTPException(
            status_code=400,
            detail=(
                "This pickup has already "
                "been completed"
            ),
        )

    # -----------------------------------------------------
    # RECEIVED TIFFINS
    # -----------------------------------------------------

    received_tiffins = int(
        data.received_tiffins
    )

    expected_tiffins = int(
        pickup.expected_tiffins or 0
    )

    # -----------------------------------------------------
    # VALIDATE RECEIVED QUANTITY
    # -----------------------------------------------------

    if received_tiffins < 0:

        raise HTTPException(
            status_code=400,
            detail=(
                "Received tiffins cannot "
                "be negative"
            ),
        )

    # -----------------------------------------------------
    # SAVE RECEIVED QUANTITY
    # -----------------------------------------------------

    pickup.received_tiffins = (
        received_tiffins
    )

    pickup.updated_at = datetime.utcnow()

    # -----------------------------------------------------
    # EXACT MATCH
    # -----------------------------------------------------

    if received_tiffins == expected_tiffins:

        pickup.status = "picked_up"
    
        pickup.picked_up_at = datetime.utcnow()
        synced_orders = sync_chef_pickup_to_delivery_orders(
            db=db,
            batch_id=pickup.batch_id,
            chef_id=pickup.chef_id,
            picked_up_at=pickup.picked_up_at,
        )
    
        message = (
            "Pickup confirmed successfully"
        )

    # -----------------------------------------------------
    # MISMATCH
    # -----------------------------------------------------

    else:

        pickup.status = "issue"

        pickup.picked_up_at = None

        message = (
            "Tiffin quantity mismatch. "
            "Pickup requires verification."
        )

    db.add(pickup)

    db.commit()

    db.refresh(pickup)

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return {
        "success": True,

        "message": message,

        "pickup": {
            "pickup_id": str(
                pickup.id
            ),

            "chef_id": str(
                pickup.chef_id
            ),

            "chef_name": (
                pickup.chef_name
            ),

            "expected_tiffins": (
                expected_tiffins
            ),

            "received_tiffins": (
                pickup.received_tiffins
            ),

            "status": (
                pickup.status
            ),

            "arrived_at": (
                pickup.arrived_at.isoformat()
                if pickup.arrived_at
                else None
            ),

            "picked_up_at": (
                pickup.picked_up_at.isoformat()
                if pickup.picked_up_at
                else None
            ),
        },
    }
    

@router.post(
    "/pickups/{pickup_id}/resolve"
)
def resolve_pickup_issue(
    pickup_id: str,

    data: DeliveryPickupResolveSchema,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),
):
    profile = get_delivery_partner_profile(
        current_user,
        db,
    )

    # -----------------------------------------------------
    # VALIDATE UUID
    # -----------------------------------------------------

    try:
        pickup_uuid = UUID(pickup_id)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid pickup ID",
        )

    # -----------------------------------------------------
    # GET PICKUP + BATCH
    # -----------------------------------------------------

    pickup = (
        db.query(DeliveryBatchPickup)
        .join(
            DeliveryBatch,
            DeliveryBatch.id
            == DeliveryBatchPickup.batch_id,
        )
        .filter(
            DeliveryBatchPickup.id
            == pickup_uuid,

            DeliveryBatch.delivery_partner_id
            == current_user.id,
        )
        .first()
    )

    if not pickup:
        raise HTTPException(
            status_code=404,
            detail="Pickup stop not found",
        )

    # -----------------------------------------------------
    # ONLY ISSUE PICKUPS CAN BE RESOLVED
    # -----------------------------------------------------

    if pickup.status != "issue":

        raise HTTPException(
            status_code=400,
            detail=(
                f"Only pickups with status 'issue' "
                f"can be resolved. "
                f"Current status: '{pickup.status}'"
            ),
        )

    # -----------------------------------------------------
    # RECEIVED TIFFINS
    # -----------------------------------------------------

    received_tiffins = int(
        data.received_tiffins
    )

    expected_tiffins = int(
        pickup.expected_tiffins or 0
    )

    # -----------------------------------------------------
    # EXACT QUANTITY REQUIRED
    # -----------------------------------------------------

    if received_tiffins != expected_tiffins:

        raise HTTPException(
            status_code=400,
            detail={
                "message": (
                    "Pickup issue cannot be resolved "
                    "until received quantity matches "
                    "expected quantity"
                ),

                "expected_tiffins": (
                    expected_tiffins
                ),

                "received_tiffins": (
                    received_tiffins
                ),
            },
        )

    # -----------------------------------------------------
    # RESOLVE
    # -----------------------------------------------------

    pickup.received_tiffins = (
        received_tiffins
    )

    pickup.status = "picked_up"

    pickup.picked_up_at = datetime.utcnow()
    
    pickup.updated_at = datetime.utcnow()
    
    # -----------------------------------------------------
    # SYNC DELIVERY ORDERS
    # -----------------------------------------------------
    
    synced_orders = sync_chef_pickup_to_delivery_orders(
        db=db,
        batch_id=pickup.batch_id,
        chef_id=pickup.chef_id,
        picked_up_at=pickup.picked_up_at,
    )

    db.add(pickup)

    db.commit()

    db.refresh(pickup)

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return {
        "success": True,

        "message": (
            "Pickup issue resolved "
            "and pickup confirmed"
        ),

        "pickup": {
            "pickup_id": str(
                pickup.id
            ),

            "batch_id": str(
                pickup.batch_id
            ),

            "chef_id": str(
                pickup.chef_id
            ),

            "chef_name": (
                pickup.chef_name
            ),

            "sequence_no": (
                pickup.sequence_no
            ),

            "expected_tiffins": (
                expected_tiffins
            ),

            "received_tiffins": (
                pickup.received_tiffins
            ),

            "status": (
                pickup.status
            ),

            "arrived_at": (
                pickup.arrived_at.isoformat()
                if pickup.arrived_at
                else None
            ),

            "picked_up_at": (
                pickup.picked_up_at.isoformat()
                if pickup.picked_up_at
                else None
            ),
        },
    }
    
# =========================================================
# 🚚 SYNC CHEF PICKUP TO DELIVERY ORDERS
# =========================================================

def sync_chef_pickup_to_delivery_orders(
    db: Session,
    batch_id: UUID,
    chef_id: UUID,
    picked_up_at: datetime,
):
    delivery_orders = (
        db.query(DeliveryOrder)
        .join(
            Order,
            Order.id == DeliveryOrder.order_id,
        )
        .filter(
            DeliveryOrder.batch_id == batch_id,
            Order.chef_id == chef_id,
            DeliveryOrder.delivery_status.in_(
                [
                    "assigned",
                    "ready",
                    "out_for_delivery",
                    "delivered",
                    "cancelled",
                ]
            ),
        )
        .all()
    )

    synced_count = 0

    for delivery_order in delivery_orders:
        delivery_order.picked_up_at = picked_up_at
        db.add(delivery_order)
        synced_count += 1

    return synced_count