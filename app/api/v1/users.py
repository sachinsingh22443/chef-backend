from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.cache import get_cache, set_cache

from app.api.deps import get_current_user, get_db
from app.models.order import Order
from app.models.review import Review

router = APIRouter()


@router.get("/me")
def get_profile(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    CUSTOMER / CHEF PROFILE

    Production optimized:
    - User-specific Redis cache
    - Cache HIT avoids profile/order/rating DB queries
    - Customer order count remains dynamic after cache expiry
    - Chef rating remains dynamic after cache expiry
    - Existing response structure preserved
    """

    # =====================================================
    # REDIS CACHE
    # =====================================================

    cache_key = f"profile:v1:user:{current_user.id}"

    cached = get_cache(cache_key)

    if cached is not None:
        return cached

    # =====================================================
    # CHEF PROFILE
    # =====================================================

    chef = None

    if current_user.role == "chef":
        chef = current_user.chef_profile

    # =====================================================
    # TOTAL ORDERS
    # =====================================================

    if current_user.role == "chef":

        total_orders = (
            db.query(func.count(Order.id))
            .filter(
                Order.chef_id == current_user.id,
                Order.status != "cancelled",
            )
            .scalar()
            or 0
        )

    else:

        total_orders = (
            db.query(func.count(Order.id))
            .filter(
                Order.user_id == current_user.id,
                Order.status != "cancelled",
            )
            .scalar()
            or 0
        )

    # =====================================================
    # RATING - CHEF ONLY
    # =====================================================

    avg_rating = 0

    if current_user.role == "chef":

        avg_rating = (
            db.query(func.avg(Review.rating))
            .filter(
                Review.chef_id == current_user.id,
            )
            .scalar()
            or 0
        )

        avg_rating = round(float(avg_rating), 1)

    # =====================================================
    # PROFILE IMAGE
    # =====================================================

    if chef and chef.profile_image:

        profile_image = chef.profile_image

    else:

        profile_image = getattr(
            current_user,
            "profile_image",
            None,
        )

    # =====================================================
    # RESPONSE
    # =====================================================

    response = {
        "id": str(current_user.id),
        "name": current_user.name,
        "email": current_user.email,
        "phone": current_user.phone,
        "role": current_user.role,

        # Chef fields
        "bio": chef.bio if chef else None,
        "location": chef.location if chef else None,
        "specialties": chef.specialties if chef else None,

        # Profile image
        "profile_image": profile_image,

        # Statistics
        "total_orders": total_orders,
        "avg_rating": avg_rating,

        # Join date
        "join_date": (
            current_user.created_at.strftime("%d %b %Y")
            if current_user.created_at
            else None
        ),
    }

    # =====================================================
    # SAVE TO REDIS
    # =====================================================

    set_cache(
        cache_key,
        response,
        ttl=120,
    )

    return response