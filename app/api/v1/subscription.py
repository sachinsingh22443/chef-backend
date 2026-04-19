from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.api.deps import get_db, get_current_user
from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.schemas.subscription import SubscriptionCreate
from app.schemas.subscription_plan import SubscriptionPlanOut

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


# =========================
# 🔥 GET ALL PLANS (CUSTOMER)
# =========================
from app.models.user import User
from math import radians, cos, sin, asin, sqrt
from fastapi import Query


# 🔥 distance function
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    return R * c


# =========================
# 🔥 GET PLANS (NEARBY)
# =========================
from app.models.menu import Menu   # 🔥 ADD THIS IMPORT

@router.get("/plans", response_model=list[SubscriptionPlanOut])
def get_plans(
    lat: float = Query(...),
    lng: float = Query(...),
    db: Session = Depends(get_db)
):
    chefs = db.query(User).filter(User.role == "chef").all()

    result = []

    for chef in chefs:
        profile = chef.chef_profile

        # ❌ skip invalid profile
        if not profile:
            continue

        if profile.latitude is None or profile.longitude is None:
            continue

        # 🔥 DISTANCE CALCULATION
        distance = calculate_distance(
            lat,
            lng,
            profile.latitude,
            profile.longitude
        )

        # ❌ skip if >10km
        if distance > 50:
            continue

        # 🔥 GET ANY MENU (subscription के लिए जरूरी)
        menu = db.query(Menu).filter(
            Menu.chef_id == chef.id,
            Menu.is_available == True
        ).first()

        if not menu:
            continue

        # 🔥 🔥 FINAL FIX (chef-wise plans)
        plans = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.chef_id == chef.id,   # 🔥 IMPORTANT
            SubscriptionPlan.is_active == True
        ).all()

        if not plans:
            continue

        # 🔥 BUILD RESPONSE
        for p in plans:
            result.append({
                "id": p.id,
                "title": p.title,
                "price": p.price,
                "description": p.description,
                "tagline": p.tagline,
                "emoji": p.emoji,
                "color": p.color,
                "features": p.features or [],
                "includes": p.includes or [],

                "chef_id": str(chef.id),
                "chef_name": chef.name,
                "distance": round(distance, 2),

                "menu_id": str(menu.id),
                "menu_name": menu.name
            })

    # 🔥 SORT BY DISTANCE
    result.sort(key=lambda x: x["distance"])

    return result
# =========================
# 🔥 GET ALL SUBSCRIPTIONS (CHEF)
# =========================
@router.get("/")
def get_subscriptions(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    subs = db.query(Subscription).filter(
        Subscription.chef_id == user.id
    ).all()

    result = []

    for s in subs:
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.id == s.plan_id
        ).first()

        result.append({
            "id": str(s.id),
            "customer": s.customer_name,
            "plan": plan.title if plan else s.plan_id,
            "dish": s.dish_name,
            "quantity": s.meals_per_day,
            "startDate": s.start_date.strftime("%b %d, %Y"),
            "days": s.delivery_days or [],
            "time": s.delivery_time,
            "amount": s.price,
            "status": s.status
        })

    return result


# =========================
# 🔥 TODAY DELIVERIES
# =========================
@router.get("/today")
def today_deliveries(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    subs = db.query(Subscription).filter(
        Subscription.chef_id == user.id
    ).all()

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


# =========================
# 🔥 UPCOMING (TEMP)
# =========================
@router.get("/upcoming")
def upcoming():
    return [
        {
            "date": "Tomorrow",
            "count": 2,
            "dishes": ["Sample Dish x1"]
        }
    ]


# =========================
# 🔥 CREATE SUBSCRIPTION
# =========================
from app.models.menu import Menu   # 🔥 जरूरी

@router.post("/")
def create_subscription(
    data: SubscriptionCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    # ========= VALIDATION =========
    if data.meals_per_day <= 0:
        raise HTTPException(400, "Invalid meals_per_day")

    if data.end_date <= data.start_date:
        raise HTTPException(400, "Invalid date range")

    if not data.delivery_days:
        raise HTTPException(400, "Select delivery days")

    # ========= GET MENU (🔥 FIX) =========
    menu = db.query(Menu).filter(Menu.id == data.menu_id).first()

    if not menu:
        raise HTTPException(404, "Menu not found")

    # ========= CHECK PLAN =========
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == data.plan_id,
        SubscriptionPlan.is_active == True
    ).first()

    if not plan:
        raise HTTPException(404, "Plan not found")

    # ========= DUPLICATE CHECK =========
    existing = db.query(Subscription).filter(
        Subscription.user_id == user.id,
        Subscription.status == "active"
    ).first()

    if existing:
        raise HTTPException(400, "Active subscription already exists")

    # ========= CREATE =========
    sub = Subscription(
        user_id=user.id,
        chef_id=menu.chef_id,   # 🔥 FINAL FIX
        menu_id=data.menu_id,

        customer_name=user.name,
        dish_name=data.dish_name,

        plan_id=plan.id,
        price=plan.price,

        meals_per_day=data.meals_per_day,

        delivery_days=data.delivery_days,
        delivery_time=data.delivery_time,
        address=data.address,

        start_date=data.start_date,
        end_date=data.end_date,

        status="active"
    )

    try:
        db.add(sub)
        db.commit()
        db.refresh(sub)
    except Exception:
        db.rollback()
        raise HTTPException(500, "Database error")

    return {
        "msg": "Subscription created",
        "id": str(sub.id)
    }