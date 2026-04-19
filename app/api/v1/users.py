from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import get_current_user, get_db
from app.models.order import Order
from app.models.review import Review

router = APIRouter()


@router.get("/me")
def get_profile(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    chef = current_user.chef_profile

    # =========================
    # 🔥 ROLE BASED ORDERS
    # =========================
    if current_user.role == "chef":
        total_orders = db.query(Order)\
            .filter(Order.chef_id == current_user.id)\
            .count()
    else:
        total_orders = db.query(Order)\
            .filter(Order.user_id == current_user.id)\
            .count()

    # =========================
    # ⭐ RATING (ONLY CHEF)
    # =========================
    avg_rating = 0
    if current_user.role == "chef":
        avg_rating = db.query(func.avg(Review.rating))\
            .filter(Review.chef_id == current_user.id)\
            .scalar()

        avg_rating = round(avg_rating, 1) if avg_rating else 0

    # =========================
    # 🖼 PROFILE IMAGE FIX
    # =========================
    if chef and chef.profile_image:
        profile_image = chef.profile_image
    else:
        profile_image = getattr(current_user, "profile_image", None)

    return {
        "id": str(current_user.id),
        "name": current_user.name,
        "email": current_user.email,
        "phone": current_user.phone,
        "role": current_user.role,  # 🔥 ADD THIS

        # 👇 chef only fields
        "bio": chef.bio if chef else None,
        "location": chef.location if chef else None,
        "specialties": chef.specialties if chef else None,

        # 👇 fixed
        "profile_image": profile_image,

        # 🔥 stats
        "total_orders": total_orders,
        "avg_rating": avg_rating,

        # 📅 date
        "join_date": current_user.created_at.strftime("%d %b %Y")
    }