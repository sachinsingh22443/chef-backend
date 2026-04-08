from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from app.schemas.review import ReviewCreate,ReviewResponse
from app.api.deps import get_db, get_current_user
from app.models.order import Order
from app.models.earning import Earning
from app.models.review import Review
from app.schemas.dashboard import DashboardResponse
router = APIRouter(prefix="/reviews", tags=["Review"])

from app.models.notification import Notification

@router.post("/")
def create_review(
    data: ReviewCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    # ✅ CREATE REVIEW
    review = Review(
        user_id=user.id,
        chef_id=data.chef_id,
        rating=data.rating,
        comment=data.comment
    )

    db.add(review)

    # 🔔 NOTIFICATION
    db.add(Notification(
        user_id=data.chef_id,   # ✅ FIXED
        type="review",
        title="New Review",
        message=f"You got a {data.rating}⭐ review"
    ))

    # ✅ SINGLE COMMIT
    db.commit()

    return {"msg": "Review added"}


@router.get("/")
def get_reviews(db: Session = Depends(get_db), user=Depends(get_current_user)):
    reviews = db.query(Review).filter(Review.chef_id == user.id).all()
    return reviews