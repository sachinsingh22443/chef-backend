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

    # ✅ total orders
    total_orders = db.query(Order)\
        .filter(Order.chef_id == current_user.id)\
        .count()

    # ✅ avg rating
    avg_rating = db.query(func.avg(Review.rating))\
        .filter(Review.chef_id == current_user.id)\
        .scalar()

    avg_rating = round(avg_rating, 1) if avg_rating else 0

    return {
        "id": str(current_user.id),
        "name": current_user.name,
        "email": current_user.email,
        "phone": current_user.phone,

        # 👇 chef profile
        "bio": chef.bio if chef else None,
        "location": chef.location if chef else None,
        "specialties": chef.specialties if chef else None,
        "profile_image": chef.profile_image if chef and chef.profile_image else None,

        # 🔥 stats
        "total_orders": total_orders,
        "avg_rating": avg_rating,

        # 🔥 safe date format
        "join_date": current_user.created_at.isoformat() if current_user.created_at else None
    }