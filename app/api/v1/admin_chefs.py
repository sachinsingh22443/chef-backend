from datetime import datetime
from uuid import UUID as UUIDType

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from pydantic import BaseModel, Field
from sqlalchemy import func, distinct
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role

from app.models.user import User
from app.models.order import Order
from app.models.subscription import Subscription
from app.models.tomorrow_special import TomorrowSpecial


# =========================================================
# ROUTER
# =========================================================

router = APIRouter(
    prefix="/admin/chefs",
    tags=["Admin Chefs"],
)


# =========================================================
# REJECTION SCHEMA
# =========================================================

class ChefRejectSchema(BaseModel):
    reason: str = Field(
        min_length=1,
        max_length=1000,
    )


# =========================================================
# HELPER — UUID
# =========================================================

def parse_uuid(value: str):

    try:
        return UUIDType(value)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid chef ID",
        )


# =========================================================
# 1. ALL CHEFS
#
# GET /admin/chefs
#
# Optional:
# ?status=under_review
# ?status=approved
# ?status=rejected
# ?status=inactive
#
# ?search=sachin
# =========================================================

@router.get("")
def get_admin_chefs(
    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_role(["admin"])
    ),

    page: int = Query(
        1,
        ge=1,
    ),

    limit: int = Query(
        20,
        ge=1,
        le=100,
    ),

    status: str | None = Query(
        None,
        description=(
            "under_review, approved, "
            "rejected, inactive"
        ),
    ),

    search: str | None = Query(
        None,
        description=(
            "Search by chef name, email or phone"
        ),
    ),
):

    # =====================================================
    # BASE QUERY
    # =====================================================

    query = (
        db.query(User)
        .filter(
            User.role == "chef"
        )
    )

    # =====================================================
    # STATUS FILTER
    # =====================================================

    if status:

        status_value = (
            status.strip().lower()
        )

        if status_value == "under_review":

            query = query.filter(
                User.application_status
                == "under_review"
            )

        elif status_value == "approved":

            query = query.filter(
                User.application_status
                == "approved"
            )

        elif status_value == "rejected":

            query = query.filter(
                User.application_status
                == "rejected"
            )

        elif status_value == "inactive":

            query = query.filter(
                User.is_active == False
            )

        else:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid status. Use "
                    "under_review, approved, "
                    "rejected or inactive"
                ),
            )

    # =====================================================
    # SEARCH
    # =====================================================

    if search:

        value = search.strip()

        if value:

            pattern = f"%{value}%"

            query = query.filter(
                User.name.ilike(pattern)
                | User.email.ilike(pattern)
                | User.phone.ilike(pattern)
            )

    # =====================================================
    # TOTAL
    # =====================================================

    total = query.count()

    # =====================================================
    # PAGINATION
    # =====================================================

    offset = (
        (page - 1)
        * limit
    )

    chefs = (
        query
        .order_by(
            User.created_at.desc()
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    # =====================================================
    # RESULT
    # =====================================================

    result = []

    for chef in chefs:

        chef_profile = (
            chef.chef_profile
        )

        # -------------------------------------------------
        # TOTAL ORDERS
        # -------------------------------------------------

        total_orders = (
            db.query(
                func.count(Order.id)
            )
            .filter(
                Order.chef_id
                == chef.id
            )
            .scalar()
            or 0
        )

        # -------------------------------------------------
        # COMPLETED
        # -------------------------------------------------

        completed_orders = (
            db.query(
                func.count(Order.id)
            )
            .filter(
                Order.chef_id
                == chef.id,

                Order.status
                == "delivered",
            )
            .scalar()
            or 0
        )

        # -------------------------------------------------
        # CANCELLED
        # -------------------------------------------------

        cancelled_orders = (
            db.query(
                func.count(Order.id)
            )
            .filter(
                Order.chef_id
                == chef.id,

                Order.status
                == "cancelled",
            )
            .scalar()
            or 0
        )

        # -------------------------------------------------
        # ACTIVE ORDERS
        # -------------------------------------------------

        active_orders = (
            db.query(
                func.count(Order.id)
            )
            .filter(
                Order.chef_id
                == chef.id,

                Order.status.notin_(
                    [
                        "delivered",
                        "cancelled",
                    ]
                ),
            )
            .scalar()
            or 0
        )

        # -------------------------------------------------
        # REVENUE
        # -------------------------------------------------

        total_revenue = (
            db.query(
                func.coalesce(
                    func.sum(
                        Order.total_price
                    ),
                    0,
                )
            )
            .filter(
                Order.chef_id
                == chef.id,

                Order.status
                != "cancelled",
            )
            .scalar()
            or 0
        )

        # -------------------------------------------------
        # CUSTOMERS SERVED
        # -------------------------------------------------

        customers_served = (
            db.query(
                func.count(
                    distinct(
                        Order.user_id
                    )
                )
            )
            .filter(
                Order.chef_id
                == chef.id,

                Order.status
                != "cancelled",
            )
            .scalar()
            or 0
        )

        # -------------------------------------------------
        # ACTIVE SUBSCRIPTIONS
        # -------------------------------------------------

        active_subscriptions = (
            db.query(
                func.count(
                    Subscription.id
                )
            )
            .filter(
                Subscription.chef_id
                == chef.id,

                Subscription.status
                == "active",
            )
            .scalar()
            or 0
        )

        # -------------------------------------------------
        # TOTAL SUBSCRIPTIONS
        # -------------------------------------------------

        total_subscriptions = (
            db.query(
                func.count(
                    Subscription.id
                )
            )
            .filter(
                Subscription.chef_id
                == chef.id
            )
            .scalar()
            or 0
        )

        # -------------------------------------------------
        # TOMORROW SPECIAL
        # -------------------------------------------------

        tomorrow_specials = (
            db.query(
                func.count(
                    TomorrowSpecial.id
                )
            )
            .filter(
                TomorrowSpecial.chef_id
                == chef.id
            )
            .scalar()
            or 0
        )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        result.append(
            {
                "id": str(
                    chef.id
                ),

                "name": chef.name,

                "email": chef.email,

                "phone": chef.phone,

                "profile_image": (
                    chef_profile.profile_image
                    if chef_profile
                    else None
                ),

                "is_active": (
                    chef.is_active
                ),

                "is_verified": (
                    chef.is_verified
                ),

                "application_status": (
                    chef.application_status
                ),

                "rejection_reason": (
                    chef.rejection_reason
                ),

                "created_at": (
                    chef.created_at.isoformat()
                    if chef.created_at
                    else None
                ),

                "profile": {
                    "address": (
                        chef_profile.address
                        if chef_profile
                        else None
                    ),

                    "fssai_number": (
                        chef_profile.fssai_number
                        if chef_profile
                        else None
                    ),

                    "fssai_document": (
                        chef_profile.fssai_document
                        if chef_profile
                        else None
                    ),

                    "bio": (
                        chef_profile.bio
                        if chef_profile
                        else None
                    ),

                    "location": (
                        chef_profile.location
                        if chef_profile
                        else None
                    ),

                    "specialties": (
                        chef_profile.specialties
                        if chef_profile
                        else None
                    ),
                },

                "statistics": {

                    "total_orders":
                        total_orders,

                    "completed_orders":
                        completed_orders,

                    "cancelled_orders":
                        cancelled_orders,

                    "active_orders":
                        active_orders,

                    "customers_served":
                        customers_served,

                    "total_revenue": round(
                        float(
                            total_revenue
                        ),
                        2,
                    ),

                    "active_subscriptions":
                        active_subscriptions,

                    "total_subscriptions":
                        total_subscriptions,

                    "tomorrow_specials":
                        tomorrow_specials,
                },
            }
        )

    # =====================================================
    # PAGINATION
    # =====================================================

    total_pages = (
        (total + limit - 1)
        // limit
        if total > 0
        else 0
    )

    return {
        "success": True,

        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages,

            "has_next": (
                page < total_pages
            ),

            "has_previous": (
                page > 1
            ),
        },

        "chefs": result,
    }


# =========================================================
# 2. CHEF DETAIL
#
# GET /admin/chefs/{chef_id}
# =========================================================

@router.get("/{chef_id}")
def get_admin_chef_detail(
    chef_id: str,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_role(["admin"])
    ),
):

    chef_uuid = parse_uuid(
        chef_id
    )

    # =====================================================
    # FIND CHEF
    # =====================================================

    chef = (
        db.query(User)
        .filter(
            User.id == chef_uuid,
            User.role == "chef",
        )
        .first()
    )

    if not chef:

        raise HTTPException(
            status_code=404,
            detail="Chef not found",
        )

    chef_profile = (
        chef.chef_profile
    )

    # =====================================================
    # ORDER STATISTICS
    # =====================================================

    total_orders = (
        db.query(
            func.count(Order.id)
        )
        .filter(
            Order.chef_id
            == chef.id
        )
        .scalar()
        or 0
    )

    pending_orders = (
        db.query(
            func.count(Order.id)
        )
        .filter(
            Order.chef_id
            == chef.id,

            Order.status
            == "pending",
        )
        .scalar()
        or 0
    )

    preparing_orders = (
        db.query(
            func.count(Order.id)
        )
        .filter(
            Order.chef_id
            == chef.id,

            Order.status
            == "preparing",
        )
        .scalar()
        or 0
    )

    out_for_delivery = (
        db.query(
            func.count(Order.id)
        )
        .filter(
            Order.chef_id
            == chef.id,

            Order.status
            == "out_for_delivery",
        )
        .scalar()
        or 0
    )

    completed_orders = (
        db.query(
            func.count(Order.id)
        )
        .filter(
            Order.chef_id
            == chef.id,

            Order.status
            == "delivered",
        )
        .scalar()
        or 0
    )

    cancelled_orders = (
        db.query(
            func.count(Order.id)
        )
        .filter(
            Order.chef_id
            == chef.id,

            Order.status
            == "cancelled",
        )
        .scalar()
        or 0
    )

    # =====================================================
    # REVENUE
    # =====================================================

    total_revenue = (
        db.query(
            func.coalesce(
                func.sum(
                    Order.total_price
                ),
                0,
            )
        )
        .filter(
            Order.chef_id
            == chef.id,

            Order.status
            != "cancelled",
        )
        .scalar()
        or 0
    )

    cancelled_revenue = (
        db.query(
            func.coalesce(
                func.sum(
                    Order.total_price
                ),
                0,
            )
        )
        .filter(
            Order.chef_id
            == chef.id,

            Order.status
            == "cancelled",
        )
        .scalar()
        or 0
    )

    # =====================================================
    # CUSTOMERS SERVED
    # =====================================================

    customers_served = (
        db.query(
            func.count(
                distinct(
                    Order.user_id
                )
            )
        )
        .filter(
            Order.chef_id
            == chef.id,

            Order.status
            != "cancelled",
        )
        .scalar()
        or 0
    )

    # =====================================================
    # SUBSCRIPTIONS
    # =====================================================

    total_subscriptions = (
        db.query(
            func.count(
                Subscription.id
            )
        )
        .filter(
            Subscription.chef_id
            == chef.id
        )
        .scalar()
        or 0
    )

    active_subscriptions = (
        db.query(
            func.count(
                Subscription.id
            )
        )
        .filter(
            Subscription.chef_id
            == chef.id,

            Subscription.status
            == "active",
        )
        .scalar()
        or 0
    )

    # =====================================================
    # TOMORROW SPECIALS
    # =====================================================

    total_specials = (
        db.query(
            func.count(
                TomorrowSpecial.id
            )
        )
        .filter(
            TomorrowSpecial.chef_id
            == chef.id
        )
        .scalar()
        or 0
    )

    active_specials = (
        db.query(
            func.count(
                TomorrowSpecial.id
            )
        )
        .filter(
            TomorrowSpecial.chef_id
            == chef.id,

            TomorrowSpecial.is_active
            == 1,
        )
        .scalar()
        or 0
    )

    # =====================================================
    # RECENT ORDERS
    # =====================================================

    recent_orders = (
        db.query(Order)
        .filter(
            Order.chef_id
            == chef.id
        )
        .order_by(
            Order.created_at.desc()
        )
        .limit(10)
        .all()
    )

    orders_data = []

    for order in recent_orders:

        orders_data.append(
            {
                "id": str(
                    order.id
                ),

                "customer_id": (
                    str(order.user_id)
                    if order.user_id
                    else None
                ),

                "customer_name": (
                    order.customer_name
                ),

                "phone": (
                    order.phone
                ),

                "address": (
                    order.address
                ),

                "total_price": (
                    round(
                        float(
                            order.total_price
                        ),
                        2,
                    )
                    if order.total_price
                    is not None
                    else 0.0
                ),

                "status": (
                    order.status
                ),

                "payment_method": (
                    order.payment_method
                ),

                "payment_status": (
                    order.payment_status
                ),

                "payment_id": (
                    order.payment_id
                ),

                "cod_confirmed": (
                    order.cod_confirmed
                ),

                "refund_status": (
                    order.refund_status
                ),

                "refund_amount": (
                    round(
                        float(
                            order.refund_amount
                        ),
                        2,
                    )
                    if order.refund_amount
                    is not None
                    else 0.0
                ),

                "refund_date": (
                    order.refund_date.isoformat()
                    if order.refund_date
                    else None
                ),

                "created_at": (
                    order.created_at.isoformat()
                    if order.created_at
                    else None
                ),
            }
        )

    # =====================================================
    # PROFILE
    # =====================================================

    profile_data = {

        "address": (
            chef_profile.address
            if chef_profile
            else None
        ),

        "fssai_number": (
            chef_profile.fssai_number
            if chef_profile
            else None
        ),

        "fssai_document": (
            chef_profile.fssai_document
            if chef_profile
            else None
        ),

        "profile_image": (
            chef_profile.profile_image
            if chef_profile
            else None
        ),

        "bio": (
            chef_profile.bio
            if chef_profile
            else None
        ),

        "location": (
            chef_profile.location
            if chef_profile
            else None
        ),

        "specialties": (
            chef_profile.specialties
            if chef_profile
            else None
        ),

        "account_holder_name": (
            chef_profile.account_holder_name
            if chef_profile
            else None
        ),

        "account_number": (
            chef_profile.account_number
            if chef_profile
            else None
        ),

        "ifsc_code": (
            chef_profile.ifsc_code
            if chef_profile
            else None
        ),
    }

    # =====================================================
    # FINAL RESPONSE
    # =====================================================

    return {

        "success": True,

        "chef": {

            "id": str(
                chef.id
            ),

            "name": chef.name,

            "email": chef.email,

            "phone": chef.phone,

            "role": chef.role,

            "is_active": (
                chef.is_active
            ),

            "is_verified": (
                chef.is_verified
            ),

            "application_status": (
                chef.application_status
            ),

            "rejection_reason": (
                chef.rejection_reason
            ),

            "created_at": (
                chef.created_at.isoformat()
                if chef.created_at
                else None
            ),

            "profile": profile_data,

            "statistics": {

                "orders": {
                    "total": total_orders,
                    "pending": pending_orders,
                    "preparing": preparing_orders,
                    "out_for_delivery":
                        out_for_delivery,
                    "completed":
                        completed_orders,
                    "cancelled":
                        cancelled_orders,
                },

                "customers_served":
                    customers_served,

                "revenue": {
                    "total": round(
                        float(
                            total_revenue
                        ),
                        2,
                    ),

                    "cancelled": round(
                        float(
                            cancelled_revenue
                        ),
                        2,
                    ),
                },

                "subscriptions": {
                    "total":
                        total_subscriptions,

                    "active":
                        active_subscriptions,
                },

                "tomorrow_special": {
                    "total":
                        total_specials,

                    "active":
                        active_specials,
                },
            },

            "recent_orders":
                orders_data,
        },
    }


# =========================================================
# 3. APPROVE CHEF
#
# POST /admin/chefs/{chef_id}/approve
# =========================================================

@router.post("/{chef_id}/approve")
def approve_chef(
    chef_id: str,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_role(["admin"])
    ),
):

    chef_uuid = parse_uuid(
        chef_id
    )

    # =====================================================
    # FIND CHEF
    # =====================================================

    chef = (
        db.query(User)
        .filter(
            User.id == chef_uuid,
            User.role == "chef",
        )
        .first()
    )

    if not chef:

        raise HTTPException(
            status_code=404,
            detail="Chef not found",
        )

    # =====================================================
    # ALREADY APPROVED
    # =====================================================

    if (
        chef.application_status
        == "approved"
        and chef.is_verified
    ):

        return {
            "success": True,
            "message": "Chef is already approved",
            "chef_id": str(
                chef.id
            ),
            "application_status":
                chef.application_status,
            "is_verified":
                chef.is_verified,
        }

    # =====================================================
    # APPROVE
    # =====================================================

    chef.application_status = (
        "approved"
    )

    chef.is_verified = True

    chef.is_active = True

    chef.rejection_reason = None

    db.commit()

    db.refresh(chef)

    return {

        "success": True,

        "message":
            "Chef approved successfully",

        "chef_id": str(
            chef.id
        ),

        "application_status":
            chef.application_status,

        "is_verified":
            chef.is_verified,

        "is_active":
            chef.is_active,
    }


# =========================================================
# 4. REJECT CHEF
#
# POST /admin/chefs/{chef_id}/reject
# =========================================================

@router.post("/{chef_id}/reject")
def reject_chef(
    chef_id: str,

    data: ChefRejectSchema,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_role(["admin"])
    ),
):

    chef_uuid = parse_uuid(
        chef_id
    )

    # =====================================================
    # FIND CHEF
    # =====================================================

    chef = (
        db.query(User)
        .filter(
            User.id == chef_uuid,
            User.role == "chef",
        )
        .first()
    )

    if not chef:

        raise HTTPException(
            status_code=404,
            detail="Chef not found",
        )

    # =====================================================
    # REJECT
    # =====================================================

    chef.application_status = (
        "rejected"
    )

    chef.is_verified = False

    chef.is_active = False

    chef.rejection_reason = (
        data.reason.strip()
    )

    db.commit()

    db.refresh(chef)

    return {

        "success": True,

        "message":
            "Chef application rejected",

        "chef_id": str(
            chef.id
        ),

        "application_status":
            chef.application_status,

        "is_verified":
            chef.is_verified,

        "is_active":
            chef.is_active,

        "rejection_reason":
            chef.rejection_reason,
    }


# =========================================================
# 5. ACTIVATE CHEF
#
# POST /admin/chefs/{chef_id}/activate
# =========================================================

@router.post("/{chef_id}/activate")
def activate_chef(
    chef_id: str,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_role(["admin"])
    ),
):

    chef_uuid = parse_uuid(
        chef_id
    )

    chef = (
        db.query(User)
        .filter(
            User.id == chef_uuid,
            User.role == "chef",
        )
        .first()
    )

    if not chef:

        raise HTTPException(
            status_code=404,
            detail="Chef not found",
        )

    # =====================================================
    # ONLY APPROVED CHEF CAN BE ACTIVATED
    # =====================================================

    if (
        chef.application_status
        != "approved"
        or not chef.is_verified
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Only an approved and "
                "verified chef can be activated"
            ),
        )

    chef.is_active = True

    db.commit()

    db.refresh(chef)

    return {

        "success": True,

        "message":
            "Chef activated successfully",

        "chef_id": str(
            chef.id
        ),

        "is_active":
            chef.is_active,
    }


# =========================================================
# 6. DEACTIVATE CHEF
#
# POST /admin/chefs/{chef_id}/deactivate
# =========================================================

@router.post("/{chef_id}/deactivate")
def deactivate_chef(
    chef_id: str,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_role(["admin"])
    ),
):

    chef_uuid = parse_uuid(
        chef_id
    )

    chef = (
        db.query(User)
        .filter(
            User.id == chef_uuid,
            User.role == "chef",
        )
        .first()
    )

    if not chef:

        raise HTTPException(
            status_code=404,
            detail="Chef not found",
        )

    chef.is_active = False

    db.commit()

    db.refresh(chef)

    return {

        "success": True,

        "message":
            "Chef deactivated successfully",

        "chef_id": str(
            chef.id
        ),

        "is_active":
            chef.is_active,
    }