import logging
logger = logging.getLogger(__name__)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from uuid import UUID
from app.core.cache import (
    get_cache,
    set_cache,
    delete_cache,
)
import uuid
from app.models.notification import Notification
from app.models.subscription_meal_schedule import SubscriptionMealSchedule
from app.models.subscription_plan_menu_cycle import SubscriptionPlanMenuCycle
from app.services.wallet import credit_wallet, debit_wallet
from app.services.whatsapp import (
    send_subscription_meal_whatsapp,
)
from app.api.deps import get_db, get_current_user
from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.schemas.subscription import SubscriptionCreate
from app.schemas.subscription_plan import SubscriptionPlanOut
from datetime import date, time, timedelta
from zoneinfo import ZoneInfo
IST = ZoneInfo("Asia/Kolkata")
MEAL_CUTOFF_TIMES = {
    "breakfast": time(8, 0),
    "lunch": time(11, 0),
    "dinner": time(18, 0),
}
from app.models.user import User
from math import radians, cos, sin, asin, sqrt
from fastapi import Query
from app.api.v1.menu_cycle import get_menu_for_day
import os
import base64
import hmac
import hashlib
import requests

from app.models.menu import Menu
from app.schemas.subscription_plan_menu_cycle import (
    SubscriptionPlanMenuCycleBulkSave,
)
from pydantic import BaseModel
from typing import Optional
router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])

# =========================================================
# DAILY SUBSCRIPTION DELIVERY
# =========================================================

ALL_DELIVERY_DAYS = [
    "Mon",
    "Tue",
    "Wed",
    "Thu",
    "Fri",
    "Sat",
    "Sun",
]

# from pydantic import BaseModel




class BreakfastPaymentCreate(BaseModel):
    subscription_id: str

class BreakfastPaymentVerify(BaseModel):
    subscription_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str



def create_meal_schedules(
    db: Session,
    subscription: Subscription,
    plan: SubscriptionPlan,
):
    """
    Create subscription meal schedules from the NORMAL MENU.

    Flow:

        Subscription
            ↓
        Each subscription date
            ↓
        get_menu_for_day()
            ↓
        Normal Menu
            ↓
        SubscriptionMealSchedule

    Rules:
    - Normal Menu is the source of truth.
    - Existing Menu records are reused.
    - No new Menu is created.
    - Subscription gets ₹10 discount per meal.
    - Breakfast is included only when enabled.
    - Only customer's selected delivery days are scheduled.
    - Maximum subscription menu period = 30 days.
    """

    # =====================================================
    # 1. MEALS
    # =====================================================

    # Fixed order
    meals = [
        "lunch",
        "dinner",
    ]

    # Breakfast only if customer selected it
    if subscription.breakfast_enabled:
        meals.insert(0, "breakfast")

    # =====================================================
    # 2. DELIVERY DAYS
    # =====================================================

    delivery_days = {
        day.strip().lower()[:3]
        for day in (subscription.delivery_days or [])
    }

    # =====================================================
    # 3. VALIDATE DELIVERY DAYS
    # =====================================================

    if not delivery_days:
        raise HTTPException(
            status_code=400,
            detail="No delivery days configured for subscription",
        )

    # =====================================================
    # 4. NORMALIZE SUBSCRIPTION START DATE
    # =====================================================

    if not subscription.start_date:
        raise HTTPException(
            status_code=400,
            detail="Subscription start date is not configured",
        )

    start_date = (
        subscription.start_date.date()
        if isinstance(subscription.start_date, datetime)
        else subscription.start_date
    )

    # =====================================================
    # 5. NORMALIZE SUBSCRIPTION END DATE
    # =====================================================

    if not subscription.end_date:
        raise HTTPException(
            status_code=400,
            detail="Subscription end date is not configured",
        )

    end_date = (
        subscription.end_date.date()
        if isinstance(subscription.end_date, datetime)
        else subscription.end_date
    )

    # =====================================================
    # 6. VALIDATE DATE RANGE
    # =====================================================

    if end_date < start_date:
        raise HTTPException(
            status_code=400,
            detail="Invalid subscription date range",
        )

    # =====================================================
    # 7. MAXIMUM 30 DAYS
    # =====================================================

    max_end_date = start_date + timedelta(days=29)

    if end_date > max_end_date:
        end_date = max_end_date

    # =====================================================
    # 8. LOOP THROUGH SUBSCRIPTION DATES
    # =====================================================

    current_date = start_date

    while current_date <= end_date:

        # =================================================
        # GET WEEKDAY
        # =================================================

        weekday = current_date.strftime("%a").lower()

        # =================================================
        # ONLY CUSTOMER SELECTED DELIVERY DAYS
        # =================================================

        if weekday in delivery_days:

            # =============================================
            # SUBSCRIPTION DAY NUMBER
            # =============================================

            day_number = (
                current_date - start_date
            ).days + 1

            if day_number < 1 or day_number > 30:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Invalid subscription day: "
                        f"{day_number}"
                    ),
                )

            # =============================================
            # CREATE EACH MEAL
            # =============================================

            for meal_type in meals:

                # =========================================
                # GET NORMAL MENU
                # =========================================

                menu, source = get_menu_for_day(
                    db=db,
                    chef_id=subscription.chef_id,
                    target_date=current_date,
                    meal_type=meal_type,
                )

                # =========================================
                # NORMAL MENU NOT FOUND
                # =========================================

                if not menu:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"No {meal_type} normal menu "
                            f"available for "
                            f"{current_date}"
                        ),
                    )

                # =========================================
                # VERIFY MENU BELONGS TO SAME CHEF
                # =========================================

                if menu.chef_id != subscription.chef_id:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Invalid {meal_type} menu "
                            f"for subscription"
                        ),
                    )

                # =========================================
                # CUTOFF TIME
                # =========================================

                cutoff_time = MEAL_CUTOFF_TIMES[meal_type]

                cutoff_at = datetime.combine(
                    current_date,
                    cutoff_time,
                    tzinfo=IST,
                )

                # =========================================
                # NORMAL MENU PRICE
                # =========================================

                normal_menu_price = float(
                    menu.price or 0.0
                )

                # =========================================
                # SUBSCRIPTION DISCOUNT
                #
                # Normal Menu ₹100
                # Subscription ₹90
                #
                # Normal Menu ₹90
                # Subscription ₹80
                #
                # Normal Menu ₹70
                # Subscription ₹60
                # =========================================

                meal_price = max(
                    normal_menu_price - 10.0,
                    0.0,
                )

                # =========================================
                # CREATE SUBSCRIPTION MEAL SCHEDULE
                # =========================================

                schedule = SubscriptionMealSchedule(
                    subscription_id=subscription.id,

                    # IMPORTANT:
                    # Existing NORMAL MENU ID
                    menu_id=menu.id,

                    # Exact subscription date
                    date=current_date,

                    # breakfast / lunch / dinner
                    meal_type=meal_type,

                    # Normal Menu price - ₹10
                    meal_price=meal_price,

                    # Default state
                    status="on",

                    # Subscription cutoff
                    cutoff_at=cutoff_at,
                )

                db.add(schedule)

        # =================================================
        # NEXT DATE
        # =================================================

        current_date += timedelta(days=1)
# =========================
# 🔥 GET ALL PLANS (CUSTOMER)
# =========================



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

@router.get("/plans", response_model=list[SubscriptionPlanOut])
def get_plans(
    lat: float = Query(...),
    lng: float = Query(...),
    db: Session = Depends(get_db)
):
    # =====================================================
    # CACHE KEY
    # Location ko 2 decimal tak round kar rahe hain
    # taaki nearby requests same cache use karein.
    # =====================================================

    lat_key = round(lat, 2)
    lng_key = round(lng, 2)

    cache_key = (
        f"subscription:plans:"
        f"{lat_key}:{lng_key}"
    )

    # =====================================================
    # CACHE HIT
    # =====================================================

    cached = get_cache(cache_key)

    if cached is not None:
        logger.info(
            "✅ Subscription Plans Cache HIT: %s",
            cache_key
        )
        return cached

    logger.info(
        "🔥 Subscription Plans Cache MISS: %s",
        cache_key
    )

    # =====================================================
    # DATABASE
    # =====================================================

    chefs = (
        db.query(User)
        .filter(User.role == "chef")
        .all()
    )

    result = []

    for chef in chefs:

        profile = chef.chef_profile

        if not profile:
            continue

        if (
            profile.latitude is None
            or profile.longitude is None
        ):
            continue

        # =================================================
        # DISTANCE
        # =================================================

        distance = calculate_distance(
            lat,
            lng,
            profile.latitude,
            profile.longitude
        )

        if distance > 50:
            continue

        # =================================================
        # GET ANY AVAILABLE MENU
        # =================================================

        menu = (
            db.query(Menu)
            .filter(
                Menu.chef_id == chef.id,
                Menu.is_available == True
            )
            .first()
        )

        if not menu:
            continue

        # =================================================
        # CHEF PLANS
        # =================================================

        plans = (
            db.query(SubscriptionPlan)
            .filter(
                SubscriptionPlan.chef_id == chef.id,
                SubscriptionPlan.is_active == True
            )
            .all()
        )

        if not plans:
            continue

        # =================================================
        # BUILD RESPONSE
        # =================================================

        for p in plans:

            result.append({
                "id": p.id,
                "title": p.title,
                "price": p.price,
                "plan_type": p.plan_type,
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
                "menu_name": menu.name,

                "goal": p.goal,
                "diet_type": p.diet_type,
                "meal_type": p.meal_type or [],
                "calories_per_day": p.calories_per_day,
                "duration_days": p.duration_days,

                "breakfast_available": p.breakfast_available,
                "breakfast_price": p.breakfast_price,
                "lunch_price": p.lunch_price,
                "dinner_price": p.dinner_price,
            })

    # =====================================================
    # SORT
    # =====================================================

    result.sort(
        key=lambda x: x["distance"]
    )

    # =====================================================
    # SAVE CACHE
    # 2 minutes
    # =====================================================

    set_cache(
        cache_key,
        result,
        ttl=120,
    )

    logger.info(
        "💾 Subscription Plans Cached: %s",
        cache_key
    )

    return result
# =========================
# 🔥 GET ALL SUBSCRIPTIONS (CHEF)
# =========================
@router.get("/")
def get_subscriptions(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    cache_key = f"subscription:chef:{user.id}"

    cached = get_cache(cache_key)

    if cached is not None:
        logger.info(
            "✅ Chef Subscriptions Cache HIT: %s",
            user.id
        )
        return cached

    subs = db.query(Subscription).filter(
        Subscription.chef_id == user.id
    ).all()

    result = []

    for s in subs:

        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.id == s.plan_id
        ).first()

        chef = db.query(User).filter(
            User.id == s.chef_id
        ).first()

        result.append({
            "id": str(s.id),

            "plan": (
                plan.title
                if plan
                else "Subscription Plan"
            ),

            "plan_type": (
                plan.plan_type
                if plan
                else None
            ),

            "chefName": (
                chef.name
                if chef
                else "Chef"
            ),

            "startDate": s.start_date.strftime(
                "%b %d, %Y"
            ),

            "endDate": s.end_date.strftime(
                "%b %d, %Y"
            ),

            "time": s.delivery_time,

            "days": s.delivery_days or [],

            "status": s.status,

            "price": s.price,

            "breakfast_enabled": (
                s.breakfast_enabled
            ),

            "breakfast_price": (
                s.breakfast_price
            ),

            "meals_per_day": (
                s.meals_per_day
            ),
        })

    set_cache(
        cache_key,
        result,
        ttl=30
    )

    return result


# =========================
# 🔥 TODAY DELIVERIES
# =========================
@router.get("/today")
def today_deliveries(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    cache_key = f"subscription:today-deliveries:{user.id}"

    # CACHE HIT
    cached = get_cache(cache_key)

    if cached is not None:
        logger.info(
            "✅ Today Deliveries Cache HIT: %s",
            user.id
        )
        return cached

    logger.info(
        "🔥 Today Deliveries Cache MISS: %s",
        user.id
    )

    # DATABASE
    subs = (
        db.query(Subscription)
        .filter(
            Subscription.chef_id == user.id
        )
        .all()
    )

    deliveries = []

    for s in subs:
        deliveries.append({
            "customer": s.customer_name,
            "dish": f"{s.dish_name} x{s.meals_per_day}",
            "time": s.delivery_time,
            "address": s.address,
            "status": "pending"
        })

    # CACHE — short TTL
    set_cache(
        cache_key,
        deliveries,
        ttl=20
    )

    logger.info(
        "💾 Today Deliveries Cached: %s",
        user.id
    )

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

    delivery_days = [
     day.strip().lower()[:3]
     for day in (data.delivery_days or [])
    ]

    if not delivery_days:
        raise HTTPException(
         status_code=400,
         detail="At least one delivery day is required",
        )

    # ========= GET MENU (🔥 FIX) =========
    menu = db.query(Menu).filter(Menu.id == data.menu_id).first()

    if not menu:
        raise HTTPException(404, "Menu not found")

    # ========= CHECK PLAN =========
    plan = db.query(SubscriptionPlan).filter(
     SubscriptionPlan.id == data.plan_id,
     SubscriptionPlan.chef_id == menu.chef_id,
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

    breakfast_price = None

    if plan.breakfast_price is not None and plan.breakfast_price > 0:
        breakfast_price = float(plan.breakfast_price)

    # IMPORTANT:
    # Plan ki current breakfast price ko
    # subscription ke andar lock/snapshot kar rahe hain.
    breakfast_price = float(plan.breakfast_price)
    
    if data.duration_days not in (7, 15, 30):
        raise HTTPException(
         status_code=400,
         detail="Duration must be 7, 15 or 30 days",
        ) 
    daily_plan_price = plan.price / 30
    
    duration_plan_price = (
     daily_plan_price * data.duration_days
    )
    
    breakfast_total = 0.0
    if data.breakfast_enabled:
        breakfast_total = (
            breakfast_price * data.duration_days
        )
    total_price = (
       duration_plan_price
       + breakfast_total
    )

    sub = Subscription(
        user_id=user.id,
        chef_id=menu.chef_id,
        menu_id=data.menu_id,

        customer_name=user.name,
        dish_name=menu.name,

        plan_id=plan.id,

        # Final subscription price
        price=total_price,

        meals_per_day=data.meals_per_day,

        # =====================================================
        # BREAKFAST
        # =====================================================

        breakfast_enabled=data.breakfast_enabled,

        breakfast_price=breakfast_price,

        # =====================================================
        # DELIVERY
        # =====================================================

        delivery_days=delivery_days,
        delivery_time=data.delivery_time,
        address=data.address,

        # =====================================================
        # DATES
        # =====================================================

        start_date=data.start_date,
        end_date=data.end_date,

        status="active",
    )

    try:
        # ---------------------------------------------
        # SAVE SUBSCRIPTION
        # ---------------------------------------------

        db.add(sub)

        # ID generate/available ho jayegi
        db.flush()

        # ---------------------------------------------
        # CREATE DAILY MEAL SCHEDULES
        # ---------------------------------------------

        create_meal_schedules(
            db=db,
            subscription=sub,
            plan=plan,
        )

        # ---------------------------------------------
        # CUSTOMER NOTIFICATION
        # ---------------------------------------------

        customer_notification = Notification(
            user_id=user.id,
            type="subscription",
            title="Subscription Activated 🎉",
            message=(
                f"Your {plan.title} subscription "
                f"has been activated successfully."
            ),
        )

        # ---------------------------------------------
        # CHEF NOTIFICATION
        # ---------------------------------------------

        chef_notification = Notification(
            user_id=menu.chef_id,
            type="subscription",
            title="New Subscription Received 🍱",
            message=(
                f"{user.name} subscribed to "
                f"your {plan.title} plan."
            ),
        )

        # ---------------------------------------------
        # SAVE NOTIFICATIONS
        # ---------------------------------------------

        db.add(customer_notification)
        db.add(chef_notification)

        # ---------------------------------------------
        # COMMIT EVERYTHING
        # ---------------------------------------------

        db.commit()
        db.refresh(sub)
        
        delete_cache(
            f"subscription:my:{user.id}"
        )

        delete_cache(
            f"subscription:active:{user.id}"
        )

        delete_cache(
            f"subscription:chef:{menu.chef_id}"
        )

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Database error",
        )

    return {
        "msg": "Subscription created",
        "id": str(sub.id),
    }
    

# GET ALL CHEF PLANS
@router.get("/chef/plans")
def get_chef_plans(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    # =====================================================
    # CACHE KEY
    # =====================================================

    cache_key = f"subscription:chef:plans:{user.id}"

    # =====================================================
    # CACHE HIT
    # =====================================================

    cached = get_cache(cache_key)

    if cached is not None:
        logger.info(
            "✅ Chef Plans Cache HIT: %s",
            user.id
        )
        return cached

    logger.info(
        "🔥 Chef Plans Cache MISS: %s",
        user.id
    )

    # =====================================================
    # DATABASE
    # =====================================================

    plans = (
        db.query(SubscriptionPlan)
        .filter(
            SubscriptionPlan.chef_id == user.id
        )
        .all()
    )

    # =====================================================
    # BUILD RESPONSE
    # =====================================================

    result = [
        {
            "id": str(plan.id),
            "title": plan.title,
            "price": plan.price,
            "plan_type": plan.plan_type,
            "description": plan.description,
            "tagline": plan.tagline,
            "emoji": plan.emoji,
            "color": plan.color,
            "features": plan.features or [],
            "includes": plan.includes or [],
            "goal": plan.goal,
            "diet_type": plan.diet_type,
            "meal_type": plan.meal_type or [],
            "calories_per_day": plan.calories_per_day,
            "duration_days": plan.duration_days,
            "breakfast_available": plan.breakfast_available,
            "breakfast_price": plan.breakfast_price,
            "lunch_price": plan.lunch_price,
            "dinner_price": plan.dinner_price,
        }
        for plan in plans
    ]

    # =====================================================
    # SAVE CACHE
    # =====================================================

    set_cache(
        cache_key,
        result,
        ttl=300
    )

    logger.info(
        "💾 Chef Plans Cached: %s",
        user.id
    )

    return result

# CREATE PLAN
@router.post("/chef/plans")
def create_plan(
    data: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    plan = SubscriptionPlan(
        id=str(uuid.uuid4()),
        chef_id=user.id,
        title=data["title"],
        price=data["price"],
        plan_type=data.get("plan_type"),
        description=data.get("description"),
        tagline=data.get("tagline"),
        emoji=data.get("emoji"),
        color=data.get("color"),
        features=data.get("features", []),
        includes=data.get("includes", []),
        goal=data.get("goal"),
        diet_type=data.get("diet_type"),
        meal_type=data.get("meal_type", []),
        calories_per_day=data.get("calories_per_day"),
        duration_days=data.get("duration_days"),
        breakfast_available=data.get("breakfast_available", False),
        breakfast_price=data.get("breakfast_price"),
        lunch_price=data.get("lunch_price"),
        dinner_price=data.get("dinner_price"),
        
    )
    
    

    db.add(plan)
    db.commit()

    return {"msg": "Plan created"}



# UPDATE PLAN
@router.put("/chef/plans/{plan_id}")
def update_plan(
    plan_id: str,
    data: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    plan = db.query(SubscriptionPlan).filter(
     SubscriptionPlan.id == plan_id,
     SubscriptionPlan.chef_id == user.id,
     SubscriptionPlan.is_active == True
    ).first()

    if not plan:
        raise HTTPException(404, "Plan not found")

    plan.title = data["title"]
    plan.price = data["price"]
    plan.plan_type = data.get("plan_type")
    plan.description = data.get("description")
    plan.tagline = data.get("tagline")
    plan.features = data.get("features", [])
    plan.includes = data.get("includes", [])
    plan.goal = data.get("goal")
    plan.diet_type = data.get("diet_type")
    plan.meal_type = data.get("meal_type", [])
    plan.calories_per_day = data.get("calories_per_day")
    plan.duration_days = data.get("duration_days")
    
    plan.breakfast_available = data.get(
     "breakfast_available",
     False
    )

    plan.breakfast_price = data.get(
     "breakfast_price"
    )
    plan.lunch_price = data.get(
     "lunch_price"
    )

    plan.dinner_price = data.get(
     "dinner_price"
    )
    plan.emoji = data.get("emoji")
    plan.color = data.get("color")
    

    db.commit()

    return {"msg": "Updated"}


# DELETE PLAN
@router.delete("/chef/plans/{plan_id}")
def delete_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == plan_id,
        SubscriptionPlan.chef_id == user.id
    ).first()

    if not plan:
        raise HTTPException(404, "Plan not found")

    db.delete(plan)
    db.commit()

    return {"msg": "Deleted"}


@router.get("/my-active")
def my_active_subscription(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    cache_key = f"subscription:active:{user.id}"

    # CACHE HIT
    cached = get_cache(cache_key)

    if cached is not None:
        logger.info(
            "✅ Active Subscription Cache HIT: %s",
            user.id
        )
        return cached

    # DATABASE
    active = db.query(Subscription).filter(
        Subscription.user_id == user.id,
        Subscription.status == "active"
    ).first()

    if not active:
        response = {
            "has_active_subscription": False
        }

        set_cache(
            cache_key,
            response,
            ttl=30
        )

        return response

    response = {
        "has_active_subscription": True,
        "end_date": active.end_date
    }

    set_cache(
        cache_key,
        response,
        ttl=30
    )

    return response

@router.get("/my")
def my_subscriptions(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    CUSTOMER MY SUBSCRIPTIONS

    Optimized:
    - Redis cache
    - Single database query
    - JOIN SubscriptionPlan
    - JOIN Chef/User
    - Removes N+1 queries
    - Response structure remains unchanged
    """

    # =====================================================
    # CACHE KEY
    # =====================================================

    cache_key = f"subscription:my:{user.id}"

    # =====================================================
    # CACHE HIT
    # =====================================================

    cached = get_cache(cache_key)

    if cached is not None:
        logger.info(
            "✅ My Subscription Cache HIT: %s",
            user.id
        )
        return cached

    logger.info(
        "🔥 My Subscription Cache MISS: %s",
        user.id
    )

    # =====================================================
    # SINGLE DATABASE QUERY
    # =====================================================
    # Previously:
    #
    # 1 query -> subscriptions
    # + 1 query per subscription -> plan
    # + 1 query per subscription -> chef
    #
    # Now:
    # ONE query using JOINs.
    # =====================================================

    rows = (
        db.query(
            Subscription,
            SubscriptionPlan,
            User,
        )
        .outerjoin(
            SubscriptionPlan,
            SubscriptionPlan.id == Subscription.plan_id,
        )
        .outerjoin(
            User,
            User.id == Subscription.chef_id,
        )
        .filter(
            Subscription.user_id == user.id
        )
        .all()
    )

    # =====================================================
    # BUILD RESPONSE
    # =====================================================

    result = []

    for subscription, plan, chef in rows:

        result.append({
            "id": str(subscription.id),

            "plan": (
                plan.title
                if plan
                else "Subscription Plan"
            ),

            "plan_type": (
                plan.plan_type
                if plan
                else None
            ),

            "chefName": (
                chef.name
                if chef
                else "Chef"
            ),

            "startDate": (
                subscription.start_date.strftime("%b %d, %Y")
                if subscription.start_date
                else None
            ),

            "endDate": (
                subscription.end_date.strftime("%b %d, %Y")
                if subscription.end_date
                else None
            ),

            "time": subscription.delivery_time,

            "days": (
                subscription.delivery_days
                or []
            ),

            "status": subscription.status,

            "price": subscription.price,

            "breakfast_enabled": (
                subscription.breakfast_enabled
            ),

            "breakfast_price": (
                subscription.breakfast_price
            ),

            "meals_per_day": (
                subscription.meals_per_day
            ),
        })

    # =====================================================
    # SAVE CACHE
    # =====================================================

    set_cache(
        cache_key,
        result,
        ttl=60
    )

    logger.info(
        "💾 My Subscription Cached: %s",
        user.id
    )

    return result

# =========================================================
# GET TODAY'S MEAL SCHEDULE
# =========================================================

# =========================================================
# GET TODAY'S MEAL SCHEDULE WITH MENU DETAILS
# =========================================================

@router.get("/{subscription_id}/meals/today")
def get_today_meals(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    
    cache_key = (
        f"subscription:today:"
        f"{subscription_id}:"
        f"{user.id}"
    )

    cached = get_cache(cache_key)

    if cached is not None:
        logger.info(
            "✅ Today's Meals Cache HIT: %s",
            cache_key
        )
        return cached

    # =====================================================
    # FIND SUBSCRIPTION
    # =====================================================

    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id == subscription_id,
            Subscription.user_id == user.id,
        )
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    # =====================================================
    # TODAY
    # =====================================================

    today = datetime.now(IST).date()

    # =====================================================
    # GET TODAY'S MEAL SCHEDULES
    # =====================================================

    meals = (
        db.query(SubscriptionMealSchedule)
        .filter(
            SubscriptionMealSchedule.subscription_id
            == subscription.id,

            SubscriptionMealSchedule.date
            == today,
        )
        .order_by(
            SubscriptionMealSchedule.meal_type
        )
        .all()
    )

    # =====================================================
    # RESPONSE
    # =====================================================

    result = []

    for meal in meals:

        menu, source = get_menu_for_day(
           db=db,
           chef_id=subscription.chef_id,
           target_date=today,
           meal_type=meal.meal_type,
        )

        # =================================================
        # MENU DETAILS
        # =================================================

        result.append({

            # ---------------------------------------------
            # MEAL
            # ---------------------------------------------

            "id": str(meal.id),

            "subscription_id": str(
                meal.subscription_id
            ),

            "date": meal.date,

            "meal_type": meal.meal_type,

            "status": meal.status,

            "meal_price": meal.meal_price,

            "cutoff_at": meal.cutoff_at,

            # ---------------------------------------------
            # EXACT MENU
            # ---------------------------------------------

            "menu_id": (
                str(menu.id)
                if menu
                else None
            ),

            "menu_name": (
                menu.name
                if menu
                else None
            ),

            "menu_description": (
                menu.description
                if menu
                else None
            ),

            "menu_price": (
              max(float(menu.price or 0.0) - 10.0, 0.0)
              if menu
              else None
            ),

            "menu_category": (
                menu.category
                if menu
                else None
            ),

            "food_type": (
                menu.food_type
                if menu
                else None
            ),

            # ---------------------------------------------
            # NUTRITION
            # ---------------------------------------------

            "calories": (
                menu.calories
                if menu
                else None
            ),

            "protein": (
                menu.protein
                if menu
                else None
            ),

            "carbs": (
                menu.carbs
                if menu
                else None
            ),

            "fats": (
                menu.fats
                if menu
                else None
            ),

            # ---------------------------------------------
            # INGREDIENTS
            # ---------------------------------------------

            "ingredients": (
                menu.ingredients
                if menu
                else []
            ),

            # ---------------------------------------------
            # IMAGES
            # ---------------------------------------------

            "image_urls": (
                menu.image_urls
                if menu
                else []
            ),

            "menu_image": (
                menu.image_urls[0]
                if menu
                and menu.image_urls
                else None
            ),
        })
    set_cache(
        cache_key,
        result,
        ttl=30
    )

    return result


# =========================================================
# GET SUBSCRIPTION MENU
#
# DEFAULT:
#   First 7 subscription days
#
# VIEW ALL:
#   Complete subscription menu
#
# IMPORTANT:
#   Existing Menu records are reused.
#   No new Menu is created here.
# =========================================================

@router.get("/{subscription_id}/meals")
def get_subscription_meals(
    subscription_id: UUID,
    view_all: bool = Query(
        False,
        description="False = first 7 days, True = complete subscription menu",
    ),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        
                # =====================================================
        # CACHE
        # =====================================================

        cache_key = (
            f"subscription:meals:"
            f"{subscription_id}:"
            f"{user.id}:"
            f"{view_all}"
        )

        cached = get_cache(cache_key)

        if cached is not None:
            logger.info(
                "✅ Subscription Meals Cache HIT: %s",
                cache_key
            )
            return cached
        # =====================================================
        # 1. FIND SUBSCRIPTION
        # =====================================================

        subscription = (
            db.query(Subscription)
            .filter(
                Subscription.id == subscription_id,
                Subscription.user_id == user.id,
            )
            .first()
        )

        if not subscription:
            raise HTTPException(
                status_code=404,
                detail="Subscription not found",
            )

        # =====================================================
        # 2. VALIDATE SUBSCRIPTION DATES
        # =====================================================

        if not subscription.start_date or not subscription.end_date:
            raise HTTPException(
                status_code=400,
                detail="Subscription dates are not configured",
            )

        if subscription.end_date < subscription.start_date:
            raise HTTPException(
                status_code=400,
                detail="Invalid subscription date range",
            )

        # =====================================================
        # 3. GET SCHEDULES
        #
        # IMPORTANT:
        # We read from SubscriptionMealSchedule.
        #
        # This means:
        # Subscription
        #      ↓
        # SubscriptionMealSchedule
        #      ↓
        # Existing Menu
        # =====================================================

        schedules_query = (
            db.query(SubscriptionMealSchedule)
            .filter(
                SubscriptionMealSchedule.subscription_id
                == subscription.id,
            )
            .order_by(
                SubscriptionMealSchedule.date.asc(),
                SubscriptionMealSchedule.meal_type.asc(),
            )
        )

        schedules = schedules_query.all()

        # =====================================================
        # 4. NO SCHEDULES
        # =====================================================

        if not schedules:
            return {
                "success": True,
                "subscription_id": str(subscription.id),
                "view_all": view_all,
                "total_days": 0,
                "days": [],
            }

        # =====================================================
        # 5. GROUP MEALS BY DATE
        # =====================================================

        grouped_days = {}

        for schedule in schedules:

            schedule_date = schedule.date

            if schedule_date not in grouped_days:
                grouped_days[schedule_date] = []

            # =================================================
            # GET EXACT EXISTING MENU
            # =================================================

            menu = None

            if schedule.menu_id:

                menu = (
                    db.query(Menu)
                    .filter(
                        Menu.id == schedule.menu_id,
                        Menu.chef_id == subscription.chef_id,
                    )
                    .first()
                )

            # =================================================
            # MENU NOT FOUND
            #
            # Do NOT crash entire subscription menu.
            # Return meal with menu=None.
            # =================================================

            menu_data = None

            if menu:

                menu_data = {
                    "id": str(menu.id),
                    "name": menu.name,
                    "description": menu.description,
                    "price": (
                       max(float(menu.price or 0.0) - 10.0, 0.0)
                       if menu
                       else None
                    ),
                    "category": menu.category,
                    "food_type": menu.food_type,

                    "calories": menu.calories,
                    "protein": menu.protein,
                    "carbs": menu.carbs,
                    "fats": menu.fats,

                    "ingredients": menu.ingredients or [],
                    "image_urls": menu.image_urls or [],

                    "menu_image": (
                        menu.image_urls[0]
                        if menu.image_urls
                        else None
                    ),
                }

            # =================================================
            # ADD MEAL
            # =================================================

            grouped_days[schedule_date].append(
                {
                    "schedule_id": str(schedule.id),

                    "subscription_id": str(
                        schedule.subscription_id
                    ),

                    "date": schedule.date,

                    "meal_type": schedule.meal_type,

                    "status": schedule.status,

                    "meal_price": schedule.meal_price,

                    "cutoff_at": schedule.cutoff_at,

                    "menu_id": (
                        str(schedule.menu_id)
                        if schedule.menu_id
                        else None
                    ),

                    "menu": menu_data,
                }
            )

        # =====================================================
        # 6. SORT DATES
        # =====================================================

        sorted_dates = sorted(grouped_days.keys())

        # =====================================================
        # 7. 7 DAYS / VIEW ALL
        #
        # False:
        #   First 7 subscription delivery dates
        #
        # True:
        #   Complete subscription schedule
        # =====================================================

        if not view_all:
            sorted_dates = sorted_dates[:7]

        # =====================================================
        # 8. BUILD FINAL RESPONSE
        # =====================================================

        result_days = []

        meal_order = {
            "breakfast": 1,
            "lunch": 2,
            "dinner": 3,
        }

        for current_date in sorted_dates:

            meals = grouped_days[current_date]

            # -----------------------------------------------
            # Sort Breakfast → Lunch → Dinner
            # -----------------------------------------------

            meals.sort(
                key=lambda meal: meal_order.get(
                    meal["meal_type"],
                    99,
                )
            )

            result_days.append(
                {
                    "date": current_date,
                    "day": current_date.strftime("%A"),
                    "meals": meals,
                }
            )

        # =====================================================
        # 9. FINAL RESPONSE
        # =====================================================

        return {
            "success": True,

            "subscription_id": str(
                subscription.id
            ),

            "start_date": subscription.start_date,

            "end_date": subscription.end_date,

            "breakfast_enabled": bool(
                subscription.breakfast_enabled
            ),

            "view_all": view_all,

            "total_days": len(result_days),

            "days": result_days,
        }
        
        set_cache(
            cache_key,
            response,
            ttl=60
        )

    # =========================================================
    # FASTAPI HTTP ERRORS
    # =========================================================

    except HTTPException:
        raise

    # =========================================================
    # DATABASE / SQL ERRORS
    # =========================================================

    except Exception as e:

        logger.exception(
            "Failed to load subscription meals. "
            "subscription_id=%s user_id=%s error=%s",
            subscription_id,
            getattr(user, "id", None),
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to load subscription menu",
        )
        
# =========================================================
# GET CUSTOMER SUBSCRIPTION MENU CYCLE
# =========================================================
#
# IMPORTANT:
# Subscription menu is taken from SubscriptionMealSchedule.
#
# Flow:
#
# Normal Menu
#     ↓
# SubscriptionMealSchedule
#     ↓
# /subscriptions/{subscription_id}/menu-cycle
#     ↓
# Customer
#
# Rules:
# - Do NOT use SubscriptionPlanMenuCycle
# - Use exact menu saved for each subscription date
# - Use existing Normal Menu record
# - No new Menu is created
# - Subscription price = Normal Menu price - ₹10
# - Return actual subscription days
# =========================================================

@router.get("/{subscription_id}/menu-cycle")
def get_customer_subscription_menu_cycle(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Get customer's subscription menu cycle.

    IMPORTANT:

    Normal Menu
        ↓
    SubscriptionMealSchedule
        ↓
    Existing Menu
        ↓
    Customer

    Rules:
    - Do NOT use SubscriptionPlanMenuCycle.
    - Use SubscriptionMealSchedule.
    - Use exact menu saved for subscription.
    - No new Menu is created.
    - Subscription price = Normal Menu price - ₹10.
    - Start date = Day 1.
    """

    # =====================================================
    # CACHE KEY
    # =====================================================

    cache_key = (
        f"subscription:menu-cycle:"
        f"{subscription_id}:"
        f"{user.id}"
    )

    # =====================================================
    # CACHE HIT
    # =====================================================

    cached = get_cache(cache_key)

    if cached is not None:
        logger.info(
            "✅ Menu Cycle Cache HIT: %s",
            cache_key
        )
        return cached

    try:

        # =====================================================
        # 1. FIND CUSTOMER SUBSCRIPTION
        # =====================================================

        subscription = (
            db.query(Subscription)
            .filter(
                Subscription.id == subscription_id,
                Subscription.user_id == user.id,
                Subscription.status == "active",
            )
            .first()
        )

        if not subscription:
            raise HTTPException(
                status_code=404,
                detail="Active subscription not found",
            )

        # =====================================================
        # 2. VALIDATE SUBSCRIPTION DATES
        # =====================================================

        if (
            not subscription.start_date
            or not subscription.end_date
        ):
            raise HTTPException(
                status_code=400,
                detail="Subscription dates are not configured",
            )

        # =====================================================
        # IMPORTANT:
        # Normalize BOTH dates to datetime.date
        #
        # This prevents:
        #
        # datetime.date - datetime.datetime
        #
        # TypeError
        # =====================================================

        subscription_start_date = (
            subscription.start_date.date()
            if isinstance(
                subscription.start_date,
                datetime,
            )
            else subscription.start_date
        )

        subscription_end_date = (
            subscription.end_date.date()
            if isinstance(
                subscription.end_date,
                datetime,
            )
            else subscription.end_date
        )

        # =====================================================
        # VALIDATE DATE RANGE
        # =====================================================

        if subscription_end_date < subscription_start_date:
            raise HTTPException(
                status_code=400,
                detail="Invalid subscription date range",
            )

        # =====================================================
        # 3. GET ACTUAL SUBSCRIPTION MEAL SCHEDULES
        # =====================================================

        schedules = (
            db.query(SubscriptionMealSchedule)
            .filter(
                SubscriptionMealSchedule.subscription_id
                == subscription.id,
            )
            .order_by(
                SubscriptionMealSchedule.date.asc(),
                SubscriptionMealSchedule.meal_type.asc(),
            )
            .all()
        )

        # =====================================================
        # 4. EMPTY
        # =====================================================

        if not schedules:
            response = []

            set_cache(
                cache_key,
                response,
                ttl=300,
            )

            return response

        # =====================================================
        # 5. MEAL ORDER
        # =====================================================

        meal_order = {
            "breakfast": 1,
            "lunch": 2,
            "dinner": 3,
        }

        # =====================================================
        # 6. SORT SCHEDULES
        #
        # Normalize date while sorting too.
        # =====================================================

        schedules.sort(
            key=lambda row: (
                (
                    row.date.date()
                    if isinstance(row.date, datetime)
                    else row.date
                ),
                meal_order.get(
                    row.meal_type,
                    99,
                ),
            )
        )

        # =====================================================
        # 7. BUILD RESPONSE
        # =====================================================

        result = []

        for schedule in schedules:

            # =================================================
            # NORMALIZE SCHEDULE DATE
            #
            # IMPORTANT FIX
            # =================================================

            schedule_date = (
                schedule.date.date()
                if isinstance(
                    schedule.date,
                    datetime,
                )
                else schedule.date
            )

            # =================================================
            # DAY NUMBER
            #
            # Start Date = Day 1
            #
            # Example:
            #
            # Aug 17 = Day 1
            # Aug 18 = Day 2
            # Aug 19 = Day 3
            #
            # =================================================

            day_number = (
                schedule_date -
                subscription_start_date
            ).days + 1

            # =================================================
            # VALIDATE DAY NUMBER
            # =================================================

            if day_number < 1 or day_number > 30:
                logger.warning(
                    "Invalid subscription day number: "
                    "subscription=%s schedule_date=%s "
                    "start_date=%s day_number=%s",
                    subscription.id,
                    schedule_date,
                    subscription_start_date,
                    day_number,
                )

                continue

            # =================================================
            # GET EXACT NORMAL MENU
            # =================================================

            menu = None

            if schedule.menu_id:

                menu = (
                    db.query(Menu)
                    .filter(
                        Menu.id == schedule.menu_id,
                        Menu.chef_id == subscription.chef_id,
                    )
                    .first()
                )

            # =================================================
            # NORMAL MENU PRICE
            # =================================================

            normal_price = (
                float(menu.price)
                if menu and menu.price is not None
                else 0.0
            )

            # =================================================
            # SUBSCRIPTION DISCOUNT
            #
            # NORMAL MENU ₹100
            # SUBSCRIPTION ₹90
            #
            # NORMAL MENU ₹90
            # SUBSCRIPTION ₹80
            #
            # NORMAL MENU ₹50
            # SUBSCRIPTION ₹40
            #
            # Minimum ₹0
            # =================================================

            subscription_price = max(
                normal_price - 10.0,
                0.0,
            )

            # =================================================
            # IMAGE
            # =================================================

            menu_image = None

            if menu and menu.image_urls:
                menu_image = menu.image_urls[0]

            # =================================================
            # RESULT
            # =================================================

            result.append({
                # ---------------------------------------------
                # SCHEDULE
                # ---------------------------------------------

                "id": str(schedule.id),

                "day_number": day_number,

                "meal_type": schedule.meal_type,

                "date": schedule_date,

                "status": schedule.status,

                "cutoff_at": schedule.cutoff_at,

                # ---------------------------------------------
                # MENU
                # ---------------------------------------------

                "menu_id": (
                    str(menu.id)
                    if menu
                    else (
                        str(schedule.menu_id)
                        if schedule.menu_id
                        else None
                    )
                ),

                "menu_name": (
                    menu.name
                    if menu
                    else None
                ),

                "menu_description": (
                    menu.description
                    if menu
                    else None
                ),

                # ---------------------------------------------
                # PRICE
                # ---------------------------------------------

                # Customer sees discounted price
                "menu_price": subscription_price,

                # Original Normal Menu price
                "normal_menu_price": normal_price,

                # Subscription price
                "subscription_price": subscription_price,

                # ---------------------------------------------
                # MENU CATEGORY
                # ---------------------------------------------

                "menu_category": (
                    menu.category
                    if menu
                    else None
                ),

                "food_type": (
                    menu.food_type
                    if menu
                    else None
                ),

                # ---------------------------------------------
                # NUTRITION
                # ---------------------------------------------

                "calories": (
                    menu.calories
                    if menu
                    else None
                ),

                "protein": (
                    menu.protein
                    if menu
                    else None
                ),

                "carbs": (
                    menu.carbs
                    if menu
                    else None
                ),

                "fats": (
                    menu.fats
                    if menu
                    else None
                ),

                # ---------------------------------------------
                # INGREDIENTS
                # ---------------------------------------------

                "ingredients": (
                    menu.ingredients or []
                    if menu
                    else []
                ),

                # ---------------------------------------------
                # IMAGE
                # ---------------------------------------------

                "menu_image": menu_image,

                "image_urls": (
                    menu.image_urls or []
                    if menu
                    else []
                ),

                # ---------------------------------------------
                # CHEF
                # ---------------------------------------------

                "chef_id": str(
                    subscription.chef_id
                ),

                "chef_name": None,
            })

        # =====================================================
        # 8. CACHE RESULT
        # =====================================================

        set_cache(
            cache_key,
            result,
            ttl=300,
        )

        # =====================================================
        # LOG
        # =====================================================

        logger.info(
            "✅ Subscription Menu Cycle Loaded: "
            "subscription=%s items=%s",
            subscription_id,
            len(result),
        )

        # =====================================================
        # RETURN
        # =====================================================

        return result

    # =========================================================
    # FASTAPI HTTP ERRORS
    # =========================================================

    except HTTPException:
        raise

    # =========================================================
    # DATABASE / OTHER ERRORS
    # =========================================================

    except Exception as e:

        logger.exception(
            "❌ Failed to load subscription menu cycle: "
            "subscription_id=%s user_id=%s error=%s",
            subscription_id,
            getattr(user, "id", None),
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to load subscription menu",
        )

# =========================================================
# TURN MEAL OFF
# =========================================================

@router.post("/{subscription_id}/meals/{meal_type}/off")
async def turn_meal_off(
    subscription_id: UUID,
    meal_type: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # -----------------------------------------------------
    # VALIDATE MEAL TYPE
    # -----------------------------------------------------

    if meal_type not in MEAL_CUTOFF_TIMES:
        raise HTTPException(
            status_code=400,
            detail="Invalid meal type",
        )

    # -----------------------------------------------------
    # FIND SUBSCRIPTION
    # -----------------------------------------------------

    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id == subscription_id,
            Subscription.user_id == user.id,
            Subscription.status == "active",
        )
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Active subscription not found",
        )

    # -----------------------------------------------------
    # FIND PLAN
    # -----------------------------------------------------

    plan = (
        db.query(SubscriptionPlan)
        .filter(
            SubscriptionPlan.id == subscription.plan_id,
        )
        .first()
    )

    if not plan:
        raise HTTPException(
            status_code=404,
            detail="Subscription plan not found",
        )

    # -----------------------------------------------------
    # CURRENT TIME
    # -----------------------------------------------------

    now = datetime.now(IST)
    today = now.date()

    # -----------------------------------------------------
    # FIND TODAY'S MEAL
    # -----------------------------------------------------

    meal = (
        db.query(SubscriptionMealSchedule)
        .filter(
            SubscriptionMealSchedule.subscription_id == subscription.id,
            SubscriptionMealSchedule.date == today,
            SubscriptionMealSchedule.meal_type == meal_type,
        )
        .first()
    )

    if not meal:
        raise HTTPException(
            status_code=404,
            detail=f"{meal_type.title()} is not scheduled for today",
        )

    # -----------------------------------------------------
    # CUTOFF CHECK
    # -----------------------------------------------------

    if now >= meal.cutoff_at:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{meal_type.title()} cutoff time has passed. "
                f"You cannot turn this meal off now."
            ),
        )

    # -----------------------------------------------------
    # ALREADY OFF
    # -----------------------------------------------------

    if meal.status == "off":
        return {
            "message": f"{meal_type.title()} is already off",
            "subscription_id": str(subscription.id),
            "date": today,
            "meal_type": meal_type,
            "status": "off",
        }

    # -----------------------------------------------------
    # CALCULATE WALLET CREDIT
    # -----------------------------------------------------

    # -----------------------------------------------------
# CALCULATE WALLET CREDIT
# -----------------------------------------------------

    amount = float(meal.meal_price or 0)

    try:
        # -------------------------------------------------
        # TURN MEAL OFF
        # -------------------------------------------------

        meal.status = "off"

        # -------------------------------------------------
        # CREDIT WALLET
        # -------------------------------------------------

        if amount > 0:
            credit_wallet(
                db=db,
                user_id=user.id,
                amount=amount,
                transaction_type="meal_off_credit",
                meal_type=meal_type,
                subscription_id=subscription.id,
                schedule_id=meal.id,
                description=(
                    f"{meal_type.title()} meal turned off "
                    f"for {today}"
                ),
            )

        # -------------------------------------------------
        # CUSTOMER NOTIFICATION
        # -------------------------------------------------

        notification = Notification(
            user_id=user.id,
            type="wallet",
            title="Meal Turned Off 💰",
            message=(
                f"Your {meal_type.title()} meal has been "
                f"turned off. ₹{amount:.2f} has been added "
                f"to your wallet."
            ),
        )

        db.add(notification)
        # -------------------------------------------------
# CHEF NOTIFICATION
# -------------------------------------------------

        chef_notification = Notification(
            user_id=subscription.chef_id,
            type="subscription_meal",
            title="Meal Turned Off ⚠️",
            message=(
             f"{user.name} has turned OFF "
             f"{meal_type.title()} for {today}. "
             f"₹{amount:.2f} has been credited to the customer's wallet."
            ),
        )

        db.add(chef_notification)

        # -------------------------------------------------
        # COMMIT
        # -------------------------------------------------

        db.commit()
        db.refresh(meal)
        delete_cache(
            f"subscription:today:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        delete_cache(
            f"subscription:meals:"
            f"{subscription.id}:"
            f"{user.id}:False"
        )

        delete_cache(
            f"subscription:meals:"
            f"{subscription.id}:"
            f"{user.id}:True"
        )
        
        # -------------------------------------------------
# WHATSAPP ADMIN NOTIFICATION
# -------------------------------------------------

        try:
            await send_subscription_meal_whatsapp(
              customer_name=user.name,
              meal_type=meal_type,
              action="off",
              date=str(today),
              amount=amount,
            )

        except Exception:
            logger.exception(
              "Failed to send diet OFF WhatsApp notification"
            )
        
    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Unable to turn meal off",
        )

    return {
        "message": f"{meal_type.title()} turned off successfully",
        "subscription_id": str(subscription.id),
        "date": today,
        "meal_type": meal_type,
        "status": "off",
        "wallet_credit": amount,
        "cutoff_at": meal.cutoff_at,
    }

# =========================================================
# TURN MEAL ON
# =========================================================

@router.post("/{subscription_id}/meals/{meal_type}/on")
async def turn_meal_on(
    subscription_id: UUID,
    meal_type: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # -----------------------------------------------------
    # VALIDATE MEAL TYPE
    # -----------------------------------------------------

    if meal_type not in MEAL_CUTOFF_TIMES:
        raise HTTPException(
            status_code=400,
            detail="Invalid meal type",
        )

    # -----------------------------------------------------
    # FIND SUBSCRIPTION
    # -----------------------------------------------------

    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id == subscription_id,
            Subscription.user_id == user.id,
            Subscription.status == "active",
        )
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Active subscription not found",
        )

    # -----------------------------------------------------
    # FIND PLAN
    # -----------------------------------------------------

    plan = (
        db.query(SubscriptionPlan)
        .filter(
            SubscriptionPlan.id == subscription.plan_id,
        )
        .first()
    )

    if not plan:
        raise HTTPException(
            status_code=404,
            detail="Subscription plan not found",
        )

    # -----------------------------------------------------
    # CURRENT TIME
    # -----------------------------------------------------

    now = datetime.now(IST)
    today = now.date()

    # -----------------------------------------------------
    # FIND TODAY'S MEAL
    # -----------------------------------------------------

    meal = (
        db.query(SubscriptionMealSchedule)
        .filter(
            SubscriptionMealSchedule.subscription_id == subscription.id,
            SubscriptionMealSchedule.date == today,
            SubscriptionMealSchedule.meal_type == meal_type,
        )
        .first()
    )

    if not meal:
        raise HTTPException(
            status_code=404,
            detail=f"{meal_type.title()} is not scheduled for today",
        )

    # -----------------------------------------------------
    # CUTOFF CHECK
    # -----------------------------------------------------

    if now >= meal.cutoff_at:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{meal_type.title()} cutoff time has passed. "
                f"You cannot turn this meal on now."
            ),
        )

    # -----------------------------------------------------
    # ALREADY ON
    # -----------------------------------------------------

    if meal.status == "on":
        return {
            "message": f"{meal_type.title()} is already on",
            "subscription_id": str(subscription.id),
            "date": today,
            "meal_type": meal_type,
            "status": "on",
        }

    # -----------------------------------------------------
    # CALCULATE WALLET DEBIT
    # -----------------------------------------------------

    # -----------------------------------------------------
# CALCULATE WALLET DEBIT
# -----------------------------------------------------

    amount = float(meal.meal_price or 0)

    try:
        # -------------------------------------------------
        # DEBIT WALLET
        # -------------------------------------------------

        if amount > 0:
            try:
                debit_wallet(
                    db=db,
                    user_id=user.id,
                    amount=amount,
                    transaction_type="meal_on_debit",
                    meal_type=meal_type,
                    subscription_id=subscription.id,
                    schedule_id=meal.id,
                    description=(
                        f"{meal_type.title()} meal turned "
                        f"on for {today}"
                    ),
                )

            except ValueError:
                db.rollback()

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Insufficient wallet balance. "
                        f"₹{amount:.2f} required to turn "
                        f"{meal_type.title()} back on."
                    ),
                )

        # -------------------------------------------------
        # TURN MEAL ON
        # -------------------------------------------------

        meal.status = "on"

        # -------------------------------------------------
        # CUSTOMER NOTIFICATION
        # -------------------------------------------------

        notification = Notification(
            user_id=user.id,
            type="wallet",
            title="Meal Turned On 🍱",
            message=(
                f"Your {meal_type.title()} meal has been "
                f"turned on. ₹{amount:.2f} has been deducted "
                f"from your wallet."
            ),
        )

        db.add(notification)
        
        # -------------------------------------------------
# CHEF NOTIFICATION
# -------------------------------------------------

        chef_notification = Notification(
           user_id=subscription.chef_id,
           type="subscription_meal",
           title="Meal Turned On 🍱",
           message=(
             f"{user.name} has turned ON "
             f"{meal_type.title()} for {today}. "
             f"₹{amount:.2f} has been deducted from "
             f"the customer's wallet."
            ),
        )

        db.add(chef_notification)
  
        # -------------------------------------------------
        # COMMIT
        # -------------------------------------------------

        db.commit()
        db.refresh(meal)
        delete_cache(
            f"subscription:today:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        delete_cache(
            f"subscription:meals:"
            f"{subscription.id}:"
            f"{user.id}:False"
        )

        delete_cache(
            f"subscription:meals:"
            f"{subscription.id}:"
            f"{user.id}:True"
        )
        try:
            await send_subscription_meal_whatsapp(
             customer_name=user.name,
             meal_type=meal_type,
             action="on",
             date=str(today),
             amount=amount,
            )

        except Exception:
            logger.exception(
             "Failed to send diet ON WhatsApp notification"
            )
    except HTTPException:
        raise

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Unable to turn meal on",
        )

    return {
        "message": f"{meal_type.title()} turned on successfully",
        "subscription_id": str(subscription.id),
        "date": today,
        "meal_type": meal_type,
        "status": "on",
        "wallet_debit": amount,
        "cutoff_at": meal.cutoff_at,
    }
    


# =========================================================
# BREAKFAST ADD-ON - CREATE RAZORPAY PAYMENT
# =========================================================

@router.post("/breakfast/create-payment")
def create_breakfast_payment(
    data: BreakfastPaymentCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:

        # =========================================
        # FIND SUBSCRIPTION
        # =========================================

        subscription = (
            db.query(Subscription)
            .filter(
                Subscription.id == data.subscription_id,
                Subscription.user_id == user.id,
            )
            .first()
        )

        if not subscription:
            raise HTTPException(
                status_code=404,
                detail="Subscription not found",
            )

        # =========================================
        # ACTIVE CHECK
        # =========================================

        if subscription.status != "active":
            raise HTTPException(
                status_code=400,
                detail="Subscription is not active",
            )

        # =========================================
        # ALREADY ENABLED
        # =========================================

        if subscription.breakfast_enabled:
            raise HTTPException(
                status_code=400,
                detail="Breakfast is already enabled",
            )

        # =========================================
        # FIND PLAN
        # =========================================

        plan = (
            db.query(SubscriptionPlan)
            .filter(
                SubscriptionPlan.id == subscription.plan_id
            )
            .first()
        )

        if not plan:
            raise HTTPException(
                status_code=404,
                detail="Subscription plan not found",
            )

        # =========================================
        # PLAN MUST SUPPORT BREAKFAST
        # =========================================

        if (
           plan.breakfast_price is None
           or plan.breakfast_price <= 0
           ):
            raise HTTPException(
             status_code=400,
             detail="Breakfast is not available for this plan",
            )
        if (
            subscription.breakfast_price is None
            or subscription.breakfast_price <= 0
        ):
            breakfast_price = float(plan.breakfast_price)
            subscription.breakfast_price = breakfast_price
        else:
            breakfast_price = float(
             subscription.breakfast_price
            )

        today = datetime.now(IST).date()

        start = subscription.start_date.date()
        end = subscription.end_date.date()

        if today < start:
            calculation_start = start
        else:
            calculation_start = today

        if calculation_start > end:
            raise HTTPException(
                status_code=400,
                detail="Subscription has expired",
            )

        # =========================================
        # DELIVERY DAY MAP
        # =========================================

        day_map = {
            "Mon": 0,
            "Tue": 1,
            "Wed": 2,
            "Thu": 3,
            "Fri": 4,
            "Sat": 5,
            "Sun": 6,
        }

        delivery_weekdays = set()

        for day in subscription.delivery_days or []:
            clean_day = day.strip().title()[:3]

            if clean_day in day_map:
                delivery_weekdays.add(
                    day_map[clean_day]
                )

        if not delivery_weekdays:
            raise HTTPException(
                status_code=400,
                detail="No valid delivery days configured",
            )

        # =========================================
        # COUNT REMAINING DELIVERY DAYS
        # =========================================

        remaining_days = 0

        current_date = calculation_start

        while current_date <= end:

            if current_date.weekday() in delivery_weekdays:
                remaining_days += 1

            current_date += timedelta(days=1)

        if remaining_days <= 0:
            raise HTTPException(
                status_code=400,
                detail="No remaining delivery days",
            )

        # =========================================
        # FINAL BREAKFAST AMOUNT
        # =========================================

        breakfast_amount = (
          breakfast_price * remaining_days
        )
        amount_paise = int(
           round(breakfast_amount * 100)
        )

        if amount_paise < 100:
            raise HTTPException(
                status_code=400,
                detail="Minimum ₹1 required",
            )

        # =========================================
        # RAZORPAY KEYS
        # =========================================

        key_id = os.getenv("RAZORPAY_KEY_ID")
        key_secret = os.getenv("RAZORPAY_KEY_SECRET")

        if not key_id or not key_secret:
            raise HTTPException(
                status_code=500,
                detail="Razorpay keys missing",
            )

        # =========================================
        # RAZORPAY AUTH
        # =========================================

        auth = base64.b64encode(
            f"{key_id}:{key_secret}".encode()
        ).decode()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth}",
        }

        # =========================================
        # RAZORPAY ORDER PAYLOAD
        # =========================================

        payload = {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": f"breakfast_{subscription.id}",
            "notes": {
                "subscription_id": str(subscription.id),
                "type": "breakfast_addon",
                "remaining_days": remaining_days,
                "breakfast_price_per_day": breakfast_price,
            },
        }

        # =========================================
        # CREATE RAZORPAY ORDER
        # =========================================

        response = requests.post(
            "https://api.razorpay.com/v1/orders",
            json=payload,
            headers=headers,
            timeout=10,
        )

        if response.status_code != 200:
            print(
                "❌ BREAKFAST RAZORPAY ERROR:",
                response.text,
            )

            raise HTTPException(
                status_code=500,
                detail="Payment gateway error",
            )

        payment = response.json()

        # =========================================
        # RESPONSE
        # =========================================

        return {
          "success": True,
          "razorpay_order_id": payment["id"],
          "amount": payment["amount"],
          "key": key_id,
          "breakfast_price_per_day": breakfast_price,
          "remaining_days": remaining_days,
          "total_amount": breakfast_amount,
        }

    except HTTPException:
        raise

    except Exception as e:

        print(
            "❌ BREAKFAST PAYMENT ERROR:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Breakfast payment initialization failed",
        )



# =========================================================
# BREAKFAST ADD-ON - VERIFY RAZORPAY PAYMENT
# =========================================================

@router.post("/breakfast/verify-payment")
def verify_breakfast_payment(
    data: BreakfastPaymentVerify,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:

        # =========================================
        # RAZORPAY SECRET
        # =========================================

        key_secret = os.getenv("RAZORPAY_KEY_SECRET")

        if not key_secret:
            raise HTTPException(
                status_code=500,
                detail="Razorpay key missing",
            )

        # =========================================
        # FIND SUBSCRIPTION
        # =========================================

        subscription = (
            db.query(Subscription)
            .filter(
                Subscription.id == data.subscription_id,
                Subscription.user_id == user.id,
            )
            .first()
        )

        if not subscription:
            raise HTTPException(
                status_code=404,
                detail="Subscription not found",
            )

        # =========================================
        # ACTIVE CHECK
        # =========================================

        if subscription.status != "active":
            raise HTTPException(
                status_code=400,
                detail="Subscription is not active",
            )

        # =========================================
        # ALREADY ENABLED
        # =========================================

        if subscription.breakfast_enabled:
            raise HTTPException(
                status_code=400,
                detail="Breakfast already enabled",
            )

        # =========================================
        # FIND PLAN
        # =========================================

        plan = (
            db.query(SubscriptionPlan)
            .filter(
                SubscriptionPlan.id == subscription.plan_id
            )
            .first()
        )

        if not plan:
            raise HTTPException(
                status_code=404,
                detail="Subscription plan not found",
            )

        # =========================================
        # BREAKFAST AVAILABILITY + PRICE
        # =========================================

        if (
            plan.breakfast_price is None
            or plan.breakfast_price <= 0
        ):
            raise HTTPException(
                status_code=400,
                detail="Breakfast is not available for this plan",
            )

        # =========================================
        # USE LOCKED SUBSCRIPTION PRICE
        # =========================================

        if (
            subscription.breakfast_price is None
            or subscription.breakfast_price <= 0
        ):
            breakfast_price = float(
                plan.breakfast_price
            )

            subscription.breakfast_price = (
                breakfast_price
            )

        else:
            breakfast_price = float(
                subscription.breakfast_price
            )

        # =========================================
        # VERIFY RAZORPAY SIGNATURE
        # =========================================

        body = (
            f"{data.razorpay_order_id}|"
            f"{data.razorpay_payment_id}"
        )

        generated_signature = hmac.new(
            key_secret.encode(),
            body.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(
            generated_signature,
            data.razorpay_signature,
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid payment signature",
            )

        # =========================================
        # ENABLE BREAKFAST
        # =========================================

        subscription.breakfast_enabled = True
        subscription.breakfast_price = breakfast_price

        # =========================================
        # GENERATE BREAKFAST SCHEDULE
        # =========================================

        today = datetime.now(IST).date()

        start = subscription.start_date.date()
        end = subscription.end_date.date()

        # Breakfast starts from today if subscription
        # is already active, otherwise from subscription start.
        calculation_start = max(
            today,
            start,
        )

        # =========================================
        # DELIVERY DAY MAP
        # =========================================

        day_map = {
            "Mon": 0,
            "Tue": 1,
            "Wed": 2,
            "Thu": 3,
            "Fri": 4,
            "Sat": 5,
            "Sun": 6,
        }

        delivery_weekdays = set()

        for day in subscription.delivery_days or []:

            clean_day = (
                day.strip()
                .title()[:3]
            )

            if clean_day in day_map:
                delivery_weekdays.add(
                    day_map[clean_day]
                )

        if not delivery_weekdays:
            raise HTTPException(
                status_code=400,
                detail="No valid delivery days configured",
            )

        # =========================================
        # CREATE BREAKFAST SCHEDULES
        # =========================================

        current_date = calculation_start

        while current_date <= end:

            # Only customer's selected delivery days
            if current_date.weekday() in delivery_weekdays:

                # =========================================
                # CHECK EXISTING BREAKFAST SCHEDULE
                # =========================================

                existing = (
                    db.query(
                        SubscriptionMealSchedule
                    )
                    .filter(
                        SubscriptionMealSchedule.subscription_id
                        == subscription.id,

                        SubscriptionMealSchedule.date
                        == current_date,

                        SubscriptionMealSchedule.meal_type
                        == "breakfast",
                    )
                    .first()
                )

                if not existing:

                    # =========================================
                    # GET MENU FOR THIS EXACT DATE
                    #
                    # Priority:
                    # 1. Date override
                    # 2. 30-day cycle
                    # 3. Repeating cycle
                    # =========================================

                    menu, source = get_menu_for_day(
                        db=db,
                        chef_id=subscription.chef_id,
                        target_date=current_date,
                    )

                    # =========================================
                    # MENU MUST EXIST
                    # =========================================

                    if not menu:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"No menu configured for "
                                f"{current_date.strftime('%d-%m-%Y')}"
                            ),
                        )

                    # =========================================
                    # BREAKFAST CUTOFF
                    # =========================================

                    cutoff_at = datetime.combine(
                        current_date,
                         MEAL_CUTOFF_TIMES["breakfast"],
                        tzinfo=IST,
                    )

                    # =========================================
                    # CREATE BREAKFAST SCHEDULE
                    # =========================================

                    db.add(
                        SubscriptionMealSchedule(
                            subscription_id=subscription.id,

                            # 🔥 IMPORTANT
                            # Save exact menu for this date
                            menu_id=menu.id,

                            date=current_date,
                            meal_type="breakfast",
                            meal_price=breakfast_price,
                            status="on",
                            cutoff_at=cutoff_at,
                        )
                    )

            current_date += timedelta(days=1)

        # =========================================
        # SAVE
        # =========================================

        db.commit()

        db.refresh(subscription)
        
        delete_cache(
            f"subscription:my:{user.id}"
        )

        delete_cache(
            f"subscription:active:{user.id}"
        )

        delete_cache(
            f"subscription:today:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        delete_cache(
            f"subscription:meals:"
            f"{subscription.id}:"
            f"{user.id}:False"
        )

        delete_cache(
            f"subscription:meals:"
            f"{subscription.id}:"
            f"{user.id}:True"
        )

        delete_cache(
            f"subscription:menu-cycle:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        # =========================================
        # SUCCESS RESPONSE
        # =========================================

        return {
            "success": True,
            "message": "Breakfast added successfully",
            "subscription_id": str(
                subscription.id
            ),
            "breakfast_enabled": (
                subscription.breakfast_enabled
            ),
            "breakfast_price": float(
                subscription.breakfast_price
            ),
        }

    except HTTPException:
        raise

    except Exception as e:

        db.rollback()

        print(
            "❌ BREAKFAST VERIFY ERROR:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Breakfast payment verification failed",
        )
        
        
# =========================================================
# GET SUBSCRIPTION PLAN MENU CYCLE
# =========================================================

# =========================================================
# GET SUBSCRIPTION PLAN MENU CYCLE
# =========================================================

@router.get("/chef/plans/{plan_id}/menu-cycle")
def get_subscription_plan_menu_cycle(
    plan_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # -----------------------------------------------------
    # FIND PLAN
    # -----------------------------------------------------

    plan = (
        db.query(SubscriptionPlan)
        .filter(
            SubscriptionPlan.id == plan_id,
            SubscriptionPlan.chef_id == user.id,
        )
        .first()
    )

    if not plan:
        raise HTTPException(
            status_code=404,
            detail="Subscription plan not found",
        )

    # -----------------------------------------------------
    # GET EXISTING CYCLE
    # -----------------------------------------------------

    cycle = (
        db.query(SubscriptionPlanMenuCycle)
        .filter(
            SubscriptionPlanMenuCycle.plan_id == plan.id
        )
        .order_by(
            SubscriptionPlanMenuCycle.day_number.asc(),
            SubscriptionPlanMenuCycle.meal_type.asc(),
        )
        .all()
    )

    # -----------------------------------------------------
    # RETURN 30 DAYS
    # -----------------------------------------------------

    return {
        "success": True,
        "plan_id": str(plan.id),
        "days": [
            {
                "id": str(row.id),
                "day_number": row.day_number,
                "meal_type": row.meal_type,
                "menu_id": str(row.menu_id),
            }
            for row in cycle
        ],
    }


# =========================================================
# SAVE / UPDATE SUBSCRIPTION PLAN MENU CYCLE
# =========================================================

# =========================================================
# SAVE / UPDATE SUBSCRIPTION PLAN MENU CYCLE
# =========================================================

@router.put("/chef/plans/{plan_id}/menu-cycle")
def save_subscription_plan_menu_cycle(
    plan_id: str,
    data: SubscriptionPlanMenuCycleBulkSave,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # -----------------------------------------------------
    # FIND PLAN
    # -----------------------------------------------------

    plan = (
        db.query(SubscriptionPlan)
        .filter(
            SubscriptionPlan.id == plan_id,
            SubscriptionPlan.chef_id == user.id,
        )
        .first()
    )

    if not plan:
        raise HTTPException(
            status_code=404,
            detail="Subscription plan not found",
        )

    # -----------------------------------------------------
    # BASIC VALIDATION
    # -----------------------------------------------------

    if not data.items:
        raise HTTPException(
            status_code=400,
            detail="At least one menu mapping is required",
        )

    # -----------------------------------------------------
    # DELETE OLD MAPPING
    # -----------------------------------------------------

    db.query(SubscriptionPlanMenuCycle).filter(
        SubscriptionPlanMenuCycle.plan_id == plan.id
    ).delete(
        synchronize_session=False
    )

    # -----------------------------------------------------
    # SAVE NEW MAPPING
    # -----------------------------------------------------

    for item in data.items:

        # Verify menu belongs to this chef
        menu = (
            db.query(Menu)
            .filter(
                Menu.id == item.menu_id,
                Menu.chef_id == user.id,
            )
            .first()
        )

        if not menu:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Menu {item.menu_id} does not "
                    f"belong to this chef"
                ),
            )

        cycle = SubscriptionPlanMenuCycle(
            plan_id=plan.id,
            day_number=item.day_number,
            meal_type=item.meal_type,
            menu_id=item.menu_id,
        )

        db.add(cycle)

    # -----------------------------------------------------
    # COMMIT
    # -----------------------------------------------------

    db.commit()
    subscriptions = (
        db.query(Subscription)
        .filter(
            Subscription.plan_id == plan.id,
            Subscription.status == "active",
        )
        .all()
    )

    for subscription in subscriptions:

        delete_cache(
            f"subscription:menu-cycle:"
            f"{subscription.id}:"
            f"{subscription.user_id}"
        )

        delete_cache(
            f"subscription:meals:"
            f"{subscription.id}:"
            f"{subscription.user_id}:False"
        )

        delete_cache(
            f"subscription:meals:"
            f"{subscription.id}:"
            f"{subscription.user_id}:True"
        )

    return {
        "success": True,
        "message": "Subscription menu cycle saved successfully",
        "plan_id": str(plan.id),
        "total_mappings": len(data.items),
    }