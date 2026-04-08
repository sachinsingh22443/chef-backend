from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from app.api.deps import get_db, get_current_user
from app.models.subscription import Subscription
from app.schemas.subscription import SubscriptionCreate

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


# ✅ GET ALL
@router.get("/")
def get_subscriptions(db: Session = Depends(get_db), user=Depends(get_current_user)):
    subs = db.query(Subscription)\
        .filter(Subscription.chef_id == user.id)\
        .all()

    result = []

    for s in subs:
        result.append({
            "id": str(s.id),
            "customer": s.customer_name,
            "plan": s.plan_name,
            "dish": s.dish_name,
            "quantity": s.meals_per_day,
            "startDate": s.start_date.strftime("%b %d, %Y"),
            "days": s.delivery_days or [],
            "time": s.delivery_time,
            "amount": s.price,
            "status": s.status
        })

    return result


# ✅ TODAY DELIVERIES
@router.get("/today")
def today_deliveries(db: Session = Depends(get_db), user=Depends(get_current_user)):
    subs = db.query(Subscription)\
        .filter(Subscription.chef_id == user.id)\
        .all()

    deliveries = []

    for s in subs:
        deliveries.append({
            "customer": s.customer_name,
            "dish": f"{s.dish_name} x{s.meals_per_day}",
            "time": s.delivery_time,
            "address": s.address,
            "status": "pending"
        })

    return deliveries


# ✅ UPCOMING
@router.get("/upcoming")
def upcoming():
    return [
        {
            "date": "Tomorrow",
            "count": 2,
            "dishes": ["Sample Dish x1"]
        }
    ]


# ✅ CREATE
@router.post("/")
def create_subscription(
    data: SubscriptionCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    sub = Subscription(
        user_id=user.id,
        chef_id=data.chef_id,
        menu_id=data.menu_id,

        customer_name=data.customer_name,
        dish_name=data.dish_name,

        plan_name=data.plan_name,
        price=data.price,
        meals_per_day=data.meals_per_day,

        delivery_days=data.delivery_days,
        delivery_time=data.delivery_time,
        address=data.address,

        start_date=data.start_date,
        end_date=data.end_date,

        status="active"
    )

    db.add(sub)
    db.commit()
    db.refresh(sub)

    return {"msg": "Subscription created", "id": sub.id}