# ============================================================
# 🚚 DELIVERY BATCH + DELIVERY LIFECYCLE API
# ============================================================

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user

from app.models.user import User

from app.models.delivery_partner import DeliveryPartnerProfile
from app.models.delivery_batch import DeliveryBatch
from app.models.delivery_order import DeliveryOrder
from app.models.order import Order
from app.models.delivery_batch_pickup import DeliveryBatchPickup


router = APIRouter(
    prefix="/delivery/batches",
    tags=["Delivery Batches"],
)


# ============================================================
# HELPER
# ============================================================

def get_delivery_profile(
    db: Session,
    user: User,
):
    if user.role != "delivery_partner":
        raise HTTPException(
            status_code=403,
            detail="Delivery partner access required",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Delivery partner account is inactive",
        )

    if user.application_status != "approved":
        raise HTTPException(
            status_code=403,
            detail="Delivery partner account is not approved",
        )

    profile = (
        db.query(DeliveryPartnerProfile)
        .filter(
            DeliveryPartnerProfile.user_id
            == user.id
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
# HELPER
# GET BATCH OWNED BY CURRENT DELIVERY PARTNER
# ============================================================

def get_my_batch(
    db: Session,
    batch_id: UUID,
    user: User,
):
    batch = (
        db.query(DeliveryBatch)
        .filter(
            DeliveryBatch.id == batch_id,
            DeliveryBatch.delivery_partner_id
            == user.id,
        )
        .first()
    )

    if not batch:
        raise HTTPException(
            status_code=404,
            detail="Delivery batch not found",
        )

    return batch


# ============================================================
# HELPER
# GET BATCH ORDERS
# ============================================================

def get_batch_orders(
    db: Session,
    batch_id: UUID,
):
    return (
        db.query(
            DeliveryOrder,
            Order,
        )
        .join(
            Order,
            Order.id == DeliveryOrder.order_id,
        )
        .filter(
            DeliveryOrder.batch_id
            == batch_id,
        )
        .order_by(
            DeliveryOrder.sequence_no.asc()
        )
        .all()
    )


# ============================================================
# HELPER
# GET NEXT ASSIGNED ORDER
# ============================================================

def get_next_assigned_order(
    db: Session,
    batch_id: UUID,
):
    return (
        db.query(
            DeliveryOrder,
            Order,
        )
        .join(
            Order,
            Order.id == DeliveryOrder.order_id,
        )
        .filter(
            DeliveryOrder.batch_id
            == batch_id,

            DeliveryOrder.delivery_status
            == "assigned",
        )
        .order_by(
            DeliveryOrder.sequence_no.asc()
        )
        .first()
    )


# ============================================================
# GET BATCH DETAIL
# ============================================================

@router.get("/{batch_id}")
def get_batch_detail(
    batch_id: str,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),
):
    # --------------------------------------------------------
    # VALIDATE UUID
    # --------------------------------------------------------

    try:
        batch_uuid = UUID(batch_id)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid batch ID",
        )

    # --------------------------------------------------------
    # PROFILE
    # --------------------------------------------------------

    profile = get_delivery_profile(
        db,
        current_user,
    )

    # --------------------------------------------------------
    # BATCH
    # --------------------------------------------------------

    batch = get_my_batch(
        db,
        batch_uuid,
        current_user,
    )

    # --------------------------------------------------------
    # ORDERS
    # --------------------------------------------------------

    rows = get_batch_orders(
        db,
        batch.id,
    )

    orders = []

    for delivery_order, order in rows:

        orders.append(
            {
                "delivery_order_id": str(
                    delivery_order.id
                ),

                "order_id": str(
                    delivery_order.order_id
                ),

                "sequence_no": (
                    delivery_order.sequence_no
                ),

                "delivery_status": (
                    delivery_order.delivery_status
                ),

                "order_status": (
                    order.status
                ),

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

                "address": {
                    "address": (
                        delivery_order.address_snapshot
                    ),

                    "latitude": (
                        delivery_order.latitude
                    ),

                    "longitude": (
                        delivery_order.longitude
                    ),
                },

                "meal_type": (
                    delivery_order.meal_type
                ),

                "total_tiffins": (
                    delivery_order.total_tiffins
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
            }
        )

    # --------------------------------------------------------
    # COUNTS
    # --------------------------------------------------------

    delivered_count = sum(
        1
        for item in orders
        if item["delivery_status"]
        == "delivered"
    )

    pending_count = sum(
        1
        for item in orders
        if item["delivery_status"]
        in {
            "assigned",
            "out_for_delivery",
        }
    )

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return {
        "success": True,

        "batch": {
            "id": str(batch.id),

            "delivery_partner_id": str(
                batch.delivery_partner_id
            ),

            "delivery_date": str(
                batch.delivery_date
            ),

            "meal_type": batch.meal_type,

            "status": batch.status,

            "total_orders": (
                batch.total_orders
            ),

            "total_tiffins": (
                batch.total_tiffins
            ),

            "start_latitude": (
                batch.start_latitude
            ),

            "start_longitude": (
                batch.start_longitude
            ),

            "created_at": (
                batch.created_at.isoformat()
                if batch.created_at
                else None
            ),

            "assigned_at": (
                batch.assigned_at.isoformat()
                if batch.assigned_at
                else None
            ),

            "started_at": (
                batch.started_at.isoformat()
                if batch.started_at
                else None
            ),

            "completed_at": (
                batch.completed_at.isoformat()
                if batch.completed_at
                else None
            ),
        },

        "driver": {
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
            "total_orders": len(orders),

            "total_tiffins": (
                sum(
                    int(
                        item["total_tiffins"]
                        or 0
                    )
                    for item in orders
                )
            ),

            "delivered_orders": (
                delivered_count
            ),

            "pending_orders": (
                pending_count
            ),
        },

        "orders": orders,
    }


# ============================================================
# START BATCH / START DELIVERY
# ============================================================

# ============================================================
# START BATCH / START DELIVERY
# ============================================================

@router.post("/{batch_id}/start")
def start_batch(
    batch_id: str,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),
):
    # --------------------------------------------------------
    # UUID
    # --------------------------------------------------------

    try:
        batch_uuid = UUID(batch_id)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid batch ID",
        )

    # --------------------------------------------------------
    # PROFILE
    # --------------------------------------------------------

    profile = get_delivery_profile(
        db,
        current_user,
    )

    # --------------------------------------------------------
    # BATCH
    # --------------------------------------------------------

    batch = get_my_batch(
        db,
        batch_uuid,
        current_user,
    )

    # --------------------------------------------------------
    # STATUS CHECK
    # --------------------------------------------------------

    if batch.status == "completed":

        raise HTTPException(
            status_code=400,
            detail="This delivery batch is already completed",
        )

    if batch.status == "started":

        raise HTTPException(
            status_code=400,
            detail="This delivery batch is already started",
        )

    if batch.status != "assigned":

        raise HTTPException(
            status_code=400,
            detail=(
                f"Batch cannot be started from "
                f"status '{batch.status}'"
            ),
        )

    # ========================================================
    # PICKUP CHECK
    # ========================================================

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

    # --------------------------------------------------------
    # NO PICKUP STOPS
    # --------------------------------------------------------

    if not pickups:

        raise HTTPException(
            status_code=400,
            detail=(
                "Pickup stops are not created "
                "for this batch"
            ),
        )

    # --------------------------------------------------------
    # CHECK PICKUP ISSUES
    # --------------------------------------------------------

    issue_pickups = [
        pickup
        for pickup in pickups
        if pickup.status == "issue"
    ]

    if issue_pickups:

        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot start delivery because "
                "one or more chef pickups have "
                "quantity issues"
            ),
        )

    # --------------------------------------------------------
    # CHECK PENDING / ARRIVED PICKUPS
    # --------------------------------------------------------

    incomplete_pickups = [
        pickup
        for pickup in pickups
        if pickup.status != "picked_up"
    ]

    if incomplete_pickups:

        pending_names = [
            pickup.chef_name
            for pickup in incomplete_pickups
        ]

        raise HTTPException(
            status_code=400,
            detail={
                "message": (
                    "All chef pickups must be "
                    "completed before starting delivery"
                ),
                "pending_pickups": pending_names,
            },
        )

    # ========================================================
    # VERIFY PICKUP TIFFIN TOTAL
    # ========================================================

    expected_total = sum(
        int(
            pickup.expected_tiffins
            or 0
        )
        for pickup in pickups
    )

    received_total = sum(
        int(
            pickup.received_tiffins
            or 0
        )
        for pickup in pickups
    )

    if expected_total != received_total:

        raise HTTPException(
            status_code=400,
            detail={
                "message": (
                    "Received tiffin quantity does "
                    "not match expected quantity"
                ),
                "expected_tiffins": expected_total,
                "received_tiffins": received_total,
            },
        )

    # ========================================================
    # GET FIRST DELIVERY ORDER
    # ========================================================

    first_order = (
        db.query(
            DeliveryOrder,
            Order,
        )
        .join(
            Order,
            Order.id
            == DeliveryOrder.order_id,
        )
        .filter(
            DeliveryOrder.batch_id
            == batch.id,

            DeliveryOrder.delivery_status
            == "assigned",
        )
        .order_by(
            DeliveryOrder.sequence_no.asc()
        )
        .first()
    )

    if not first_order:

        raise HTTPException(
            status_code=400,
            detail=(
                "No assigned orders available "
                "in this batch"
            ),
        )

    delivery_order, order = first_order

    # ========================================================
    # START DELIVERY
    # ========================================================

    now = datetime.utcnow()

    batch.status = "started"

    batch.started_at = now

    # --------------------------------------------------------
    # FIRST CUSTOMER ORDER
    # --------------------------------------------------------

    delivery_order.delivery_status = (
        "out_for_delivery"
    )

    delivery_order.picked_up_at = (
        delivery_order.picked_up_at
        or now
    )

    order.status = "out_for_delivery"

    # --------------------------------------------------------
    # DRIVER BUSY
    # --------------------------------------------------------

    profile.is_available = False

    db.add(batch)
    db.add(delivery_order)
    db.add(order)
    db.add(profile)

    db.commit()

    db.refresh(batch)
    db.refresh(delivery_order)
    db.refresh(profile)

    # ========================================================
    # RESPONSE
    # ========================================================

    return {
        "success": True,

        "message": (
            "All chef pickups completed. "
            "Delivery trip started."
        ),

        "batch_id": str(
            batch.id
        ),

        "batch_status": (
            batch.status
        ),

        "started_at": (
            batch.started_at.isoformat()
        ),

        "pickup_summary": {
            "total_pickup_stops": len(
                pickups
            ),

            "completed_pickups": len(
                [
                    pickup
                    for pickup in pickups
                    if pickup.status
                    == "picked_up"
                ]
            ),

            "expected_tiffins": (
                expected_total
            ),

            "received_tiffins": (
                received_total
            ),
        },

        "current_delivery": {
            "delivery_order_id": str(
                delivery_order.id
            ),

            "order_id": str(
                delivery_order.order_id
            ),

            "sequence_no": (
                delivery_order.sequence_no
            ),

            "delivery_status": (
                delivery_order.delivery_status
            ),

            "customer_name": (
                delivery_order.customer_name
            ),

            "customer_phone": (
                delivery_order.customer_phone
            ),

            "address": (
                delivery_order.address_snapshot
            ),

            "latitude": (
                delivery_order.latitude
            ),

            "longitude": (
                delivery_order.longitude
            ),

            "total_tiffins": (
                delivery_order.total_tiffins
            ),
        },
    }


# ============================================================
# DELIVER ONE ORDER
# ============================================================

@router.post("/{batch_id}/orders/{delivery_order_id}/deliver")
def deliver_order(
    batch_id: str,
    delivery_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # --------------------------------------------------------
    # UUID VALIDATION
    # --------------------------------------------------------

    try:
        batch_uuid = UUID(batch_id)
        delivery_order_uuid = UUID(delivery_order_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid batch or delivery order ID",
        )

    # --------------------------------------------------------
    # PROFILE
    # --------------------------------------------------------

    profile = get_delivery_profile(
        db,
        current_user,
    )

    # --------------------------------------------------------
    # BATCH
    # --------------------------------------------------------

    batch = get_my_batch(
        db,
        batch_uuid,
        current_user,
    )

    # --------------------------------------------------------
    # BATCH MUST BE STARTED
    # --------------------------------------------------------

    if batch.status != "started":
        raise HTTPException(
            status_code=400,
            detail=(
                "Delivery batch must be started "
                "before delivering orders"
            ),
        )

    # --------------------------------------------------------
    # DELIVERY ORDER
    # --------------------------------------------------------

    result = (
        db.query(
            DeliveryOrder,
            Order,
        )
        .join(
            Order,
            Order.id == DeliveryOrder.order_id,
        )
        .filter(
            DeliveryOrder.id == delivery_order_uuid,
            DeliveryOrder.batch_id == batch.id,
            DeliveryOrder.delivery_partner_id == current_user.id,
        )
        .first()
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail=(
                "Delivery order not found "
                "in this batch"
            ),
        )

    delivery_order, order = result

    # --------------------------------------------------------
    # ONLY CURRENT OUT-FOR-DELIVERY ORDER
    # --------------------------------------------------------

    if delivery_order.delivery_status != "out_for_delivery":
        raise HTTPException(
            status_code=400,
            detail=(
                "This order is not currently "
                "out for delivery"
            ),
        )

    # --------------------------------------------------------
    # DELIVER
    # --------------------------------------------------------

    now = datetime.utcnow()

    delivery_order.delivery_status = "delivered"
    delivery_order.delivered_at = now
    order.status = "delivered"

    db.add(delivery_order)
    db.add(order)

    # IMPORTANT:
    # Flush the delivered status before querying remaining orders.
    db.flush()

    # --------------------------------------------------------
    # FIND NEXT ASSIGNED ORDER
    # --------------------------------------------------------

    next_order = get_next_assigned_order(
        db,
        batch.id,
    )

    next_delivery_order = None
    next_main_order = None

    # --------------------------------------------------------
    # START NEXT ORDER AUTOMATICALLY
    # --------------------------------------------------------

    if next_order:
        (
            next_delivery_order,
            next_main_order,
        ) = next_order

        next_delivery_order.delivery_status = "out_for_delivery"
        next_delivery_order.picked_up_at = (
            next_delivery_order.picked_up_at
            or now
        )

        next_main_order.status = "out_for_delivery"

        db.add(next_delivery_order)
        db.add(next_main_order)

        db.flush()

    # --------------------------------------------------------
    # CHECK REMAINING ORDERS
    #
    # ONLY assigned and out_for_delivery are pending.
    # delivered orders are NOT counted.
    # --------------------------------------------------------

    remaining_count = (
        db.query(DeliveryOrder)
        .filter(
            DeliveryOrder.batch_id == batch.id,
            DeliveryOrder.delivery_status.in_(
                [
                    "assigned",
                    "out_for_delivery",
                ]
            ),
        )
        .count()
    )

    # --------------------------------------------------------
    # BATCH COMPLETED
    # --------------------------------------------------------

    batch_completed = (
        remaining_count == 0
    )

    if batch_completed:
        batch.status = "completed"
        batch.completed_at = now

        # Driver is free for another batch.
        profile.is_available = True

    else:
        batch.status = "started"

        # Driver remains busy.
        profile.is_available = False

    db.add(batch)
    db.add(profile)

    # --------------------------------------------------------
    # FINAL COMMIT
    # --------------------------------------------------------

    db.commit()

    # --------------------------------------------------------
    # REFRESH
    # --------------------------------------------------------

    db.refresh(batch)
    db.refresh(delivery_order)
    db.refresh(profile)

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    response = {
        "success": True,

        "message": (
            "Order delivered successfully"
        ),

        "batch_id": str(
            batch.id
        ),

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

        "batch_status": (
            batch.status
        ),

        "remaining_orders": (
            remaining_count
        ),

        "batch_completed": (
            batch_completed
        ),

        "driver": {
            "user_id": str(
                current_user.id
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
    }

    # --------------------------------------------------------
    # NEXT DELIVERY
    # --------------------------------------------------------

    if next_delivery_order:
        response["next_delivery"] = {
            "delivery_order_id": str(
                next_delivery_order.id
            ),

            "order_id": str(
                next_delivery_order.order_id
            ),

            "sequence_no": (
                next_delivery_order.sequence_no
            ),

            "delivery_status": (
                next_delivery_order.delivery_status
            ),

            "customer_name": (
                next_delivery_order.customer_name
            ),

            "customer_phone": (
                next_delivery_order.customer_phone
            ),

            "address": (
                next_delivery_order.address_snapshot
            ),

            "latitude": (
                next_delivery_order.latitude
            ),

            "longitude": (
                next_delivery_order.longitude
            ),

            "total_tiffins": (
                next_delivery_order.total_tiffins
            ),
        }
    else:
        response["next_delivery"] = None

    return response


# ============================================================
# MANUAL COMPLETE BATCH
#
# Safety endpoint.
# Batch can ONLY be completed if all orders delivered.
# ============================================================

@router.post("/{batch_id}/complete")
def complete_batch(
    batch_id: str,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),
):
    # --------------------------------------------------------
    # UUID
    # --------------------------------------------------------

    try:
        batch_uuid = UUID(batch_id)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid batch ID",
        )

    # --------------------------------------------------------
    # PROFILE
    # --------------------------------------------------------

    profile = get_delivery_profile(
        db,
        current_user,
    )

    # --------------------------------------------------------
    # BATCH
    # --------------------------------------------------------

    batch = get_my_batch(
        db,
        batch_uuid,
        current_user,
    )

    # --------------------------------------------------------
    # CHECK UNDELIVERED
    # --------------------------------------------------------

    remaining = (
        db.query(DeliveryOrder)
        .filter(
            DeliveryOrder.batch_id
            == batch.id,

            DeliveryOrder.delivery_status
            != "delivered",
        )
        .count()
    )

    if remaining > 0:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot complete batch. "
                f"{remaining} order(s) are still pending."
            ),
        )

    # --------------------------------------------------------
    # COMPLETE
    # --------------------------------------------------------

    now = datetime.utcnow()

    batch.status = "completed"

    batch.completed_at = now

    profile.is_available = True

    db.add(batch)
    db.add(profile)

    db.commit()

    return {
        "success": True,

        "message": (
            "Delivery batch completed"
        ),

        "batch_id": str(
            batch.id
        ),

        "batch_status": (
            batch.status
        ),

        "completed_at": (
            batch.completed_at.isoformat()
        ),

        "driver_available": (
            profile.is_available
        ),
    }