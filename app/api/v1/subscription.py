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
from app.models.wallet import Wallet
import uuid
from app.models.notification import Notification
from app.models.subscription_meal_schedule import SubscriptionMealSchedule
from app.models.subscription_plan_menu_cycle import SubscriptionPlanMenuCycle
from app.services.wallet import credit_wallet, debit_wallet

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
from app.models.menu_cycle import MenuCycle
from app.models.menu_date_override import MenuDateOverride
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
    Create subscription meal schedules from NORMAL MENU.

    Rules:
    - Normal Menu is the source of truth.
    - Same Menu record is reused.
    - No new Menu is created.
    - Normal Menu price is NEVER modified.
    - Subscription price = Normal Menu price - ₹10.
    - Breakfast only when enabled.
    - Only selected delivery days are scheduled.
    - Maximum subscription duration = 30 calendar days.
    """

    # =====================================================
    # 1. MEALS
    # =====================================================

    meals = [
        "lunch",
        "dinner",
    ]

    if subscription.breakfast_enabled:
        meals.insert(0, "breakfast")

    # =====================================================
    # 2. DELIVERY DAYS
    # =====================================================

    delivery_days = {
        str(day).strip().lower()[:3]
        for day in (subscription.delivery_days or [])
    }

    if not delivery_days:
        raise HTTPException(
            status_code=400,
            detail="No delivery days configured for subscription",
        )

    # =====================================================
    # 3. NORMALIZE START DATE
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
    # 4. NORMALIZE END DATE
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
    # 5. VALIDATE RANGE
    # =====================================================

    if end_date < start_date:
        raise HTTPException(
            status_code=400,
            detail="Invalid subscription date range",
        )

    # =====================================================
    # 6. MAXIMUM 30 CALENDAR DAYS
    # =====================================================

    maximum_end_date = start_date + timedelta(days=29)

    if end_date > maximum_end_date:
        end_date = maximum_end_date

    # =====================================================
    # 7. LOOP THROUGH EVERY SUBSCRIPTION DATE
    # =====================================================

    current_date = start_date

    while current_date <= end_date:

        weekday = current_date.strftime("%a").lower()

        # Only selected delivery days
        if weekday in delivery_days:

            # =================================================
            # SUBSCRIPTION DAY NUMBER
            # =================================================

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

            # =================================================
            # CREATE EACH MEAL
            # =================================================

            for meal_type in meals:

                # =============================================
                # GET NORMAL MENU
                # =============================================

                menu, source = get_menu_for_day(
                    db=db,
                    chef_id=subscription.chef_id,
                    target_date=current_date,
                    meal_type=meal_type,
                )

                # =============================================
                # NORMAL MENU NOT FOUND
                # =============================================

                if not menu:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"No normal {meal_type} menu "
                            f"available for {current_date}"
                        ),
                    )

                # =============================================
                # CHEF VALIDATION
                # =============================================

                if menu.chef_id != subscription.chef_id:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Invalid {meal_type} menu "
                            f"for subscription"
                        ),
                    )

                # =============================================
                # SUBSCRIPTION CUTOFF
                # =============================================

                cutoff_time = MEAL_CUTOFF_TIMES[meal_type]

                cutoff_at = datetime.combine(
                    current_date,
                    cutoff_time,
                    tzinfo=IST,
                )

                # =============================================
                # NORMAL MENU PRICE
                # =============================================

                normal_menu_price = float(
                    menu.price or 0.0
                )

                # =============================================
                # SUBSCRIPTION PRICE
                #
                # ₹100 -> ₹90
                # ₹90  -> ₹80
                # ₹70  -> ₹60
                #
                # IMPORTANT:
                # Menu.price remains unchanged.
                # =============================================

                subscription_price = max(
                    normal_menu_price - 10.0,
                    0.0,
                )

                # =============================================
                # CREATE SCHEDULE
                # =============================================

                schedule = SubscriptionMealSchedule(
                    subscription_id=subscription.id,

                    # Actual NORMAL MENU ID
                    menu_id=menu.id,

                    # Exact date
                    date=current_date,

                    # breakfast / lunch / dinner
                    meal_type=meal_type,

                    # Discounted subscription price
                    meal_price=subscription_price,

                    # Default ON
                    status="on",

                    # Subscription cutoff
                    cutoff_at=cutoff_at,
                )

                db.add(schedule)

        current_date += timedelta(days=1)
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
    user=Depends(get_current_user),
):
    # =====================================================
    # 1. BASIC VALIDATION
    # =====================================================

    if data.meals_per_day <= 0:
        raise HTTPException(
            status_code=400,
            detail="Invalid meals_per_day",
        )

    if data.duration_days not in (7, 15, 30):
        raise HTTPException(
            status_code=400,
            detail="Duration must be 7, 15 or 30 days",
        )

    if not data.start_date:
        raise HTTPException(
            status_code=400,
            detail="Start date is required",
        )

    # =====================================================
    # 2. DELIVERY DAYS
    # =====================================================

    delivery_days = [
        str(day).strip().lower()[:3]
        for day in (data.delivery_days or [])
    ]

    if not delivery_days:
        raise HTTPException(
            status_code=400,
            detail="At least one delivery day is required",
        )

    # Remove duplicates while preserving order
    delivery_days = list(dict.fromkeys(delivery_days))

    # =====================================================
    # 3. CALCULATE EXACT SUBSCRIPTION END DATE
    #
    # 7  days = start + 6
    # 15 days = start + 14
    # 30 days = start + 29
    # =====================================================

    subscription_start_date = (
        data.start_date.date()
        if isinstance(data.start_date, datetime)
        else data.start_date
    )

    calculated_end_date = (
        subscription_start_date
        + timedelta(days=data.duration_days - 1)
    )

    # =====================================================
    # 4. GET SELECTED MENU
    # =====================================================

    menu = (
        db.query(Menu)
        .filter(
            Menu.id == data.menu_id,
            Menu.is_deleted == False,
        )
        .first()
    )

    if not menu:
        raise HTTPException(
            status_code=404,
            detail="Menu not found",
        )

    # =====================================================
    # 5. CHECK PLAN
    # =====================================================

    plan = (
        db.query(SubscriptionPlan)
        .filter(
            SubscriptionPlan.id == data.plan_id,
            SubscriptionPlan.chef_id == menu.chef_id,
            SubscriptionPlan.is_active == True,
        )
        .first()
    )

    if not plan:
        raise HTTPException(
            status_code=404,
            detail="Plan not found",
        )

    # =====================================================
    # 6. ACTIVE SUBSCRIPTION CHECK
    # =====================================================

    existing = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user.id,
            Subscription.status == "active",
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Active subscription already exists",
        )

    # =====================================================
    # 7. BREAKFAST PRICE SNAPSHOT
    # =====================================================

    breakfast_price = 0.0

    if plan.breakfast_price is not None:
        breakfast_price = float(
            plan.breakfast_price
        )

    # =====================================================
    # 8. PLAN PRICE
    #
    # Keep your existing subscription plan calculation.
    # =====================================================

    daily_plan_price = float(plan.price or 0.0) / 30.0

    duration_plan_price = (
        daily_plan_price * data.duration_days
    )

    breakfast_total = 0.0

    if data.breakfast_enabled:
        breakfast_total = (
            breakfast_price
            * data.duration_days
        )

    total_price = (
        duration_plan_price
        + breakfast_total
    )

    # =====================================================
    # 9. CREATE SUBSCRIPTION
    # =====================================================

    sub = Subscription(
        user_id=user.id,
        chef_id=menu.chef_id,

        # This is only the initially selected menu.
        # Daily menus come from normal menu cycle.
        menu_id=data.menu_id,

        customer_name=user.name,
        dish_name=menu.name,

        plan_id=plan.id,

        price=total_price,

        meals_per_day=data.meals_per_day,

        # Breakfast
        breakfast_enabled=data.breakfast_enabled,
        breakfast_price=breakfast_price,

        # Delivery
        delivery_days=delivery_days,
        delivery_time=data.delivery_time,
        address=data.address,

        # IMPORTANT:
        # duration_days decides end date
        start_date=subscription_start_date,
        end_date=calculated_end_date,

        status="active",
    )

    try:

        # =================================================
        # SAVE SUBSCRIPTION
        # =================================================

        db.add(sub)
        db.flush()

        # =================================================
        # CREATE DAILY SCHEDULES
        # =================================================

        create_meal_schedules(
            db=db,
            subscription=sub,
            plan=plan,
        )

        # =================================================
        # CUSTOMER NOTIFICATION
        # =================================================

        customer_notification = Notification(
            user_id=user.id,
            type="subscription",
            title="Subscription Activated 🎉",
            message=(
                f"Your {plan.title} subscription "
                f"has been activated successfully."
            ),
        )

        # =================================================
        # CHEF NOTIFICATION
        # =================================================

        chef_notification = Notification(
            user_id=menu.chef_id,
            type="subscription",
            title="New Subscription Received 🍱",
            message=(
                f"{user.name} subscribed to "
                f"your {plan.title} plan."
            ),
        )

        db.add(customer_notification)
        db.add(chef_notification)

        # =================================================
        # COMMIT
        # =================================================

        db.commit()
        db.refresh(sub)

        # =================================================
        # CLEAR CACHE
        # =================================================

        # =====================================================
# CLEAR ALL SUBSCRIPTION CACHES
# =====================================================

        delete_cache(
           f"subscription:my:{user.id}"
        )

        delete_cache(
           f"subscription:active:{user.id}"
        )

        delete_cache(
            f"subscription:chef:{menu.chef_id}"
        )

# =====================================================
# TODAY MEALS CACHE
# =====================================================

        delete_cache(
           f"subscription:today:"
           f"{sub.id}:"
           f"{user.id}"
        )

        delete_cache(
          f"subscription:today:v2:"
          f"{sub.id}:"
          f"{user.id}"
        )

# =====================================================
# MENU CYCLE CACHE
# =====================================================

        delete_cache(
          f"subscription:menu-cycle:"
          f"{sub.id}:"
          f"{user.id}"
)

        delete_cache(
           f"subscription:menu-cycle:v2:"
           f"{sub.id}:"
           f"{user.id}"
        )

        delete_cache(
            f"subscription:menu-cycle:v3:"
            f"{sub.id}:"
            f"{user.id}"
        )

        delete_cache(         
           f"subscription:menu-cycle:v4:"
           f"{sub.id}:"
           f"{user.id}"
        )

# =====================================================
# SUBSCRIPTION MEALS CACHE
# =====================================================

        delete_cache(
            f"subscription:meals:"
            f"{sub.id}:"
            f"{user.id}:False"
        )

        delete_cache(
            f"subscription:meals:"
            f"{sub.id}:"
            f"{user.id}:True"
        )

        return {
            "success": True,
            "msg": "Subscription created",
            "id": str(sub.id),
            "duration_days": data.duration_days,
            "start_date": subscription_start_date,
            "end_date": calculated_end_date,
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        logger.exception(
            "❌ SUBSCRIPTION CREATE ERROR: %s",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to create subscription",
        )

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

# =========================================================
# GET TODAY'S MEAL SCHEDULE WITH MENU DETAILS
# =========================================================

@router.get("/{subscription_id}/meals/today")
def get_today_meals(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    TODAY'S SUBSCRIPTION MEALS

    IMPORTANT:
    - Normal Menu is the source of truth.
    - Do NOT trust schedule.menu_id for display.
    - Resolve today's menu again using:
          date + meal_type
    - Subscription price = Normal Menu price - ₹10
    """

    # =====================================================
    # CACHE
    # =====================================================

    cache_key = (
        f"subscription:today:v2:"
        f"{subscription_id}:"
        f"{user.id}"
    )

    cached = get_cache(cache_key)

    if cached is not None:
        logger.info(
            "✅ Today's Meals Cache HIT: %s",
            cache_key,
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
    # TODAY - INDIA
    # =====================================================

    today = datetime.now(IST).date()

    # =====================================================
    # GET TODAY'S SCHEDULES
    # =====================================================

    meals = (
        db.query(SubscriptionMealSchedule)
        .filter(
            SubscriptionMealSchedule.subscription_id
            == subscription.id,
            SubscriptionMealSchedule.date == today,
        )
        .all()
    )

    # =====================================================
    # MEAL ORDER
    # =====================================================

    meal_order = {
        "breakfast": 1,
        "lunch": 2,
        "dinner": 3,
    }

    meals.sort(
        key=lambda x: meal_order.get(
            x.meal_type,
            99,
        )
    )

    # =====================================================
    # RESPONSE
    # =====================================================

    result = []

    for schedule in meals:

        meal_type = (
            schedule.meal_type
            or ""
        ).lower().strip()

        # =================================================
        # IMPORTANT:
        # GET NORMAL MENU USING TODAY + MEAL TYPE
        # =================================================

        menu, source = get_menu_for_day(
            db=db,
            chef_id=subscription.chef_id,
            target_date=today,
            meal_type=meal_type,
        )

        # =================================================
        # NORMAL MENU PRICE
        # =================================================

        normal_menu_price = (
            float(menu.price)
            if menu and menu.price is not None
            else 0.0
        )

        # =================================================
        # SUBSCRIPTION PRICE
        # NORMAL PRICE - ₹10
        # =================================================

        subscription_price = max(
            normal_menu_price - 10.0,
            0.0,
        )

        # =================================================
        # IMAGE
        # =================================================

        menu_image = None

        if menu and menu.image_urls:
            menu_image = menu.image_urls[0]

        # =================================================
        # RESPONSE
        # =================================================

        result.append({
            "id": str(schedule.id),

            "subscription_id": str(
                subscription.id
            ),

            "date": today,

            "meal_type": meal_type,

            "status": schedule.status,

            "cutoff_at": schedule.cutoff_at,

            # Actual NORMAL menu
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

            # Customer sees subscription price
            "menu_price": subscription_price,

            # Original normal price
            "normal_menu_price": normal_menu_price,

            # Discounted price
            "subscription_price": subscription_price,

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

            "ingredients": (
                menu.ingredients or []
                if menu
                else []
            ),

            "image_urls": (
                menu.image_urls or []
                if menu
                else []
            ),

            "menu_image": menu_image,

            "source": source,
        })

    # =====================================================
    # CACHE
    # =====================================================

    set_cache(
        cache_key,
        result,
        ttl=30,
    )

    logger.info(
        "✅ Today's Meals Loaded from Normal Menu: "
        "subscription=%s items=%s",
        subscription_id,
        len(result),
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
    """
    CUSTOMER SUBSCRIPTION MENU

    IMPORTANT BUSINESS RULES:

    1. Normal Menu is the ONLY menu source.
    2. Subscription menu uses the SAME Normal Menu records.
    3. Normal Menu price is NEVER modified.
    4. Subscription price = Normal Menu price - ₹10.
    5. Default view = first 7 calendar days.
    6. view_all=True = complete subscription duration.
    7. 7-day subscription  = exactly 7 days.
    8. 15-day subscription = exactly 15 days.
    9. 30-day subscription = exactly 30 days.
    10. Delivery days do NOT remove dates from subscription menu.
    11. Breakfast is shown only when breakfast_enabled=True.
    12. Each date resolves its own Normal Menu using:
            date + meal_type
        through get_menu_for_day().
    13. SubscriptionMealSchedule is used only for:
            - status
            - cutoff_at
            - schedule_id
    """

    try:

        # =====================================================
        # 1. CACHE
        # =====================================================

        cache_key = (
            f"subscription:meals:v5:"
            f"{subscription_id}:"
            f"{user.id}:"
            f"{view_all}"
        )

        cached = get_cache(cache_key)

        if cached is not None:
            logger.info(
                "✅ Subscription Meals Cache HIT: %s",
                cache_key,
            )
            return cached

        logger.info(
            "🔥 Subscription Meals Cache MISS: %s",
            cache_key,
        )

        # =====================================================
        # 2. FIND SUBSCRIPTION
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
        # 3. VALIDATE DATES
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
        # 4. NORMALIZE START DATE
        # =====================================================

        subscription_start_date = (
            subscription.start_date.date()
            if isinstance(
                subscription.start_date,
                datetime,
            )
            else subscription.start_date
        )

        # =====================================================
        # 5. NORMALIZE END DATE
        # =====================================================

        subscription_end_date = (
            subscription.end_date.date()
            if isinstance(
                subscription.end_date,
                datetime,
            )
            else subscription.end_date
        )

        # =====================================================
        # 6. VALIDATE DATE RANGE
        # =====================================================

        if subscription_end_date < subscription_start_date:
            raise HTTPException(
                status_code=400,
                detail="Invalid subscription date range",
            )

        # =====================================================
        # 7. EXACT SUBSCRIPTION DURATION
        #
        # 7  days = start + 6
        # 15 days = start + 14
        # 30 days = start + 29
        # =====================================================

        subscription_duration = (
            subscription_end_date
            - subscription_start_date
        ).days + 1

        subscription_duration = min(
            max(subscription_duration, 1),
            30,
        )

        # =====================================================
        # 8. LOAD EXISTING SCHEDULES
        #
        # IMPORTANT:
        # Schedules are NOT used to decide which dates exist.
        #
        # They are used only for:
        # - status
        # - cutoff_at
        # - schedule_id
        # =====================================================

        schedules = (
            db.query(SubscriptionMealSchedule)
            .filter(
                SubscriptionMealSchedule.subscription_id
                == subscription.id,
            )
            .all()
        )

        # =====================================================
        # 9. BUILD SCHEDULE LOOKUP
        # =====================================================

        schedule_map = {}

        for schedule in schedules:

            schedule_date = (
                schedule.date.date()
                if isinstance(
                    schedule.date,
                    datetime,
                )
                else schedule.date
            )

            schedule_meal_type = (
                schedule.meal_type or ""
            ).lower().strip()

            schedule_map[
                (
                    schedule_date,
                    schedule_meal_type,
                )
            ] = schedule

        # =====================================================
        # 10. MEALS TO SHOW
        # =====================================================

        meals_to_show = [
            "lunch",
            "dinner",
        ]

        if subscription.breakfast_enabled:
            meals_to_show.insert(
                0,
                "breakfast",
            )

        # =====================================================
        # 11. MEAL ORDER
        # =====================================================

        meal_order = {
            "breakfast": 1,
            "lunch": 2,
            "dinner": 3,
        }

        # =====================================================
        # 12. HOW MANY DAYS TO DISPLAY
        #
        # DEFAULT:
        #   7 days
        #
        # VIEW ALL:
        #   complete subscription
        # =====================================================

        display_days = (
            subscription_duration
            if view_all
            else min(
                7,
                subscription_duration,
            )
        )

        # =====================================================
        # 13. BUILD DATES FROM SUBSCRIPTION START DATE
        #
        # IMPORTANT:
        #
        # DO NOT CHECK delivery_days.
        #
        # Therefore:
        #
        # 7 day subscription  -> 7 dates
        # 15 day subscription -> 15 dates
        # 30 day subscription -> 30 dates
        # =====================================================

        result_days = []

        current_date = subscription_start_date

        for day_number in range(
            1,
            display_days + 1,
        ):

            # =================================================
            # 14. BUILD MEALS
            # =================================================

            meals = []

            for meal_type in meals_to_show:

                # =============================================
                # EXISTING SCHEDULE
                # =============================================

                schedule = schedule_map.get(
                    (
                        current_date,
                        meal_type,
                    )
                )

                # =============================================
                # GET NORMAL MENU
                #
                # THIS IS THE MOST IMPORTANT PART
                #
                # Same logic as Normal Menu.
                # =============================================

                menu, source = get_menu_for_day(
                    db=db,
                    chef_id=subscription.chef_id,
                    target_date=current_date,
                    meal_type=meal_type,
                )

                # =============================================
                # NORMAL PRICE
                # =============================================

                normal_price = (
                    float(menu.price)
                    if menu
                    and menu.price is not None
                    else 0.0
                )

                # =============================================
                # SUBSCRIPTION PRICE
                #
                # NORMAL MENU:
                # ₹100
                #
                # SUBSCRIPTION:
                # ₹90
                #
                # IMPORTANT:
                # menu.price IS NEVER changed.
                # =============================================

                subscription_price = max(
                    normal_price - 10.0,
                    0.0,
                )

                # =============================================
                # IMAGE
                # =============================================

                menu_image = None

                if menu and menu.image_urls:
                    menu_image = menu.image_urls[0]

                # =============================================
                # MENU DATA
                # =============================================

                menu_data = None

                if menu:

                    menu_data = {
                        "id": str(menu.id),

                        "name": menu.name,

                        "description": menu.description,

                        # Subscription price
                        "price": subscription_price,

                        # Original Normal Menu price
                        "normal_price": normal_price,

                        # Discounted subscription price
                        "subscription_price": (
                            subscription_price
                        ),

                        "category": menu.category,

                        "food_type": menu.food_type,

                        "calories": menu.calories,

                        "protein": menu.protein,

                        "carbs": menu.carbs,

                        "fats": menu.fats,

                        "ingredients": (
                            menu.ingredients or []
                        ),

                        "image_urls": (
                            menu.image_urls or []
                        ),

                        "menu_image": menu_image,

                        "source": source,
                    }

                # =============================================
                # SCHEDULE DATA
                # =============================================

                schedule_id = (
                    str(schedule.id)
                    if schedule
                    else None
                )

                status = (
                    schedule.status
                    if schedule
                    else "on"
                )

                cutoff_at = (
                    schedule.cutoff_at
                    if schedule
                    else None
                )

                # =============================================
                # MEAL RESPONSE
                # =============================================

                meals.append(
                    {
                        "id": schedule_id,

                        "schedule_id": schedule_id,

                        "subscription_id": str(
                            subscription.id
                        ),

                        "date": current_date,

                        "meal_type": meal_type,

                        "status": status,

                        "cutoff_at": cutoff_at,

                        # Actual Normal Menu ID
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

                        # Subscription price
                        "meal_price": subscription_price,

                        "menu_price": subscription_price,

                        # Original Normal Menu price
                        "normal_menu_price": normal_price,

                        # Subscription discounted price
                        "subscription_price": (
                            subscription_price
                        ),

                        "menu": menu_data,

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

                        "ingredients": (
                            menu.ingredients or []
                            if menu
                            else []
                        ),

                        "image_urls": (
                            menu.image_urls or []
                            if menu
                            else []
                        ),

                        "menu_image": menu_image,

                        "chef_id": str(
                            subscription.chef_id
                        ),

                        "chef_name": None,

                        "source": source,
                    }
                )

            # =================================================
            # 15. BREAKFAST → LUNCH → DINNER
            # =================================================

            meals.sort(
                key=lambda meal: meal_order.get(
                    meal["meal_type"],
                    99,
                )
            )

            # =================================================
            # 16. ADD DAY
            # =================================================

            result_days.append(
                {
                    "date": current_date,

                    "day": current_date.strftime(
                        "%A"
                    ),

                    "day_number": day_number,

                    "meals": meals,
                }
            )

            # Next date
            current_date += timedelta(days=1)

        # =====================================================
        # 17. FINAL RESPONSE
        # =====================================================

        response = {
            "success": True,

            "subscription_id": str(
                subscription.id
            ),

            "start_date": (
                subscription_start_date
            ),

            "end_date": (
                subscription_end_date
            ),

            "subscription_duration": (
                subscription_duration
            ),

            "breakfast_enabled": bool(
                subscription.breakfast_enabled
            ),

            "view_all": view_all,

            "total_days": len(
                result_days
            ),

            "days": result_days,
        }

        # =====================================================
        # 18. CACHE
        # =====================================================

        set_cache(
            cache_key,
            response,
            ttl=30,
        )

        logger.info(
            "✅ Subscription Meals Loaded "
            "from NORMAL MENU: "
            "subscription=%s "
            "duration=%s "
            "view_all=%s "
            "days=%s",
            subscription_id,
            subscription_duration,
            view_all,
            len(result_days),
        )

        return response

    # =========================================================
    # HTTP EXCEPTION
    # =========================================================

    except HTTPException:
        raise

    # =========================================================
    # UNEXPECTED ERROR
    # =========================================================

    except Exception as e:

        logger.exception(
            "❌ Failed to load subscription meals: "
            "subscription_id=%s "
            "user_id=%s "
            "error=%s",
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

# =========================================================
# GET CUSTOMER SUBSCRIPTION MENU CYCLE
# =========================================================

# =========================================================
# GET CUSTOMER SUBSCRIPTION MENU CYCLE
# =========================================================

# =========================================================
# GET CUSTOMER SUBSCRIPTION MENU CYCLE
# =========================================================

@router.get("/{subscription_id}/menu-cycle")
def get_customer_subscription_menu_cycle(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    CUSTOMER SUBSCRIPTION MENU CYCLE

    PERFORMANCE OPTIMIZED VERSION

    Business rules remain unchanged:
    - Date override has highest priority
    - Configured cycle has priority
    - Latest cycle repeats every 30 days
    - Every subscription calendar date is returned
    - Breakfast only when enabled
    - Normal Menu price is never modified
    - Subscription price = Normal Menu price - ₹10

    IMPORTANT:
    This endpoint intentionally does NOT call get_menu_for_day()
    inside the date/meal loop.

    All required data is loaded in batches to avoid N+1 queries.
    """

    cache_key = (
        f"subscription:menu-cycle:v4:"
        f"{subscription_id}:"
        f"{user.id}"
    )

    cached = get_cache(cache_key)

    if cached is not None:
        logger.info(
            "✅ Subscription Menu Cycle Cache HIT: %s",
            cache_key,
        )
        return cached

    logger.info(
        "🔥 Subscription Menu Cycle Cache MISS: %s",
        cache_key,
    )

    try:

        # =====================================================
        # 1. FIND ACTIVE SUBSCRIPTION
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
        # 2. VALIDATE DATES
        # =====================================================

        if (
            not subscription.start_date
            or not subscription.end_date
        ):
            raise HTTPException(
                status_code=400,
                detail="Subscription dates are not configured",
            )

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

        if subscription_end_date < subscription_start_date:
            raise HTTPException(
                status_code=400,
                detail="Invalid subscription date range",
            )

        # =====================================================
        # 3. EXACT SUBSCRIPTION DURATION
        # =====================================================

        subscription_duration = (
            subscription_end_date
            - subscription_start_date
        ).days + 1

        subscription_duration = min(
            max(subscription_duration, 1),
            30,
        )

        # =====================================================
        # 4. LOAD ALL SUBSCRIPTION SCHEDULES — ONE QUERY
        # =====================================================

        schedules = (
            db.query(SubscriptionMealSchedule)
            .filter(
                SubscriptionMealSchedule.subscription_id
                == subscription.id,
            )
            .all()
        )

        schedule_map = {}

        for schedule in schedules:

            schedule_date = (
                schedule.date.date()
                if isinstance(
                    schedule.date,
                    datetime,
                )
                else schedule.date
            )

            schedule_meal_type = (
                schedule.meal_type or ""
            ).lower().strip()

            schedule_map[
                (
                    schedule_date,
                    schedule_meal_type,
                )
            ] = schedule

        # =====================================================
        # 5. MEALS TO SHOW
        # =====================================================

        meals_to_show = [
            "lunch",
            "dinner",
        ]

        if subscription.breakfast_enabled:
            meals_to_show.insert(
                0,
                "breakfast",
            )

        # =====================================================
        # 6. LOAD ALL MENU CYCLES — ONE QUERY
        #
        # This replaces calling resolve_cycle_and_day()
        # again and again.
        # =====================================================

        cycles = (
            db.query(MenuCycle)
            .filter(
                MenuCycle.chef_id
                == subscription.chef_id,
            )
            .order_by(
                MenuCycle.cycle_start_date.asc()
            )
            .all()
        )

        # =====================================================
        # 7. NO CYCLES
        # =====================================================

        if not cycles:

            response = {
                "success": True,
                "subscription_id": str(
                    subscription.id
                ),
                "start_date":
                    subscription_start_date,
                "end_date":
                    subscription_end_date,
                "subscription_duration":
                    subscription_duration,
                "breakfast_enabled": bool(
                    subscription.breakfast_enabled
                ),
                "total_days": 0,
                "days": [],
            }

            set_cache(
                cache_key,
                response,
                ttl=30,
            )

            return response

        # =====================================================
        # 8. CREATE CYCLE MAP
        #
        # Key:
        # (cycle_start_date, cycle_day, meal_type)
        #
        # Value:
        # MenuCycle record
        # =====================================================

        cycle_item_map = {}

        for cycle_item in cycles:

            cycle_item_map[
                (
                    cycle_item.cycle_start_date,
                    cycle_item.cycle_day,
                    (
                        cycle_item.meal_type or ""
                    ).lower().strip(),
                )
            ] = cycle_item

        # =====================================================
        # 9. LOAD DATE OVERRIDES — ONE QUERY
        #
        # Only subscription date range is required.
        # =====================================================

        overrides = (
            db.query(MenuDateOverride)
            .filter(
                MenuDateOverride.chef_id
                == subscription.chef_id,
                MenuDateOverride.menu_date
                >= subscription_start_date,
                MenuDateOverride.menu_date
                <= subscription_end_date,
            )
            .all()
        )

        override_map = {}

        for override in overrides:

            override_date = (
                override.menu_date.date()
                if isinstance(
                    override.menu_date,
                    datetime,
                )
                else override.menu_date
            )

            override_map[
                override_date
            ] = override

        # =====================================================
        # 10. DETERMINE ALL REQUIRED MENU IDS
        #
        # First resolve which MenuCycle/override applies.
        # Then fetch all actual Menu records in ONE query.
        # =====================================================

        resolved_items = []

        current_date = subscription_start_date
        day_number = 1

        while (
            current_date <= subscription_end_date
            and day_number <= subscription_duration
        ):

            # -------------------------------------------------
            # Find date override
            # -------------------------------------------------

            override = override_map.get(
                current_date
            )

            for meal_type in meals_to_show:

                cycle_item = None
                cycle_start_date = None
                cycle_day = None
                source = None

                # =================================================
                # DATE OVERRIDE
                #
                # Existing get_menu_for_day() behavior:
                # override is date-only, therefore the same
                # override applies to all meal types.
                # =================================================

                if override:

                    menu_id = override.menu_id
                    source = "date_override"

                else:

                    # =============================================
                    # FIND EXACT CONFIGURED CYCLE
                    # =============================================

                    selected_cycle = None
                    selected_cycle_day = None

                    for cycle in cycles:

                        cycle_start = (
                            cycle.cycle_start_date
                        )

                        cycle_end = (
                            cycle_start
                            + timedelta(days=29)
                        )

                        if (
                            cycle_start
                            <= current_date
                            <= cycle_end
                        ):

                            selected_cycle = cycle
                            selected_cycle_day = (
                                current_date
                                - cycle_start
                            ).days + 1

                            break

                    # =============================================
                    # NO EXACT CYCLE
                    #
                    # Repeat latest cycle every 30 days.
                    # Same logic as resolve_cycle_and_day().
                    # =============================================

                    if selected_cycle is None:

                        previous_cycles = [
                            cycle
                            for cycle in cycles
                            if cycle.cycle_start_date
                            <= current_date
                        ]

                        if previous_cycles:

                            selected_cycle = max(
                                previous_cycles,
                                key=lambda cycle:
                                    cycle.cycle_start_date,
                            )

                            days_since_cycle_start = (
                                current_date
                                - selected_cycle.cycle_start_date
                            ).days

                            selected_cycle_day = (
                                days_since_cycle_start
                                % 30
                            ) + 1

                            source = "cycle_repeat"

                    if selected_cycle is not None:

                        cycle_start_date = (
                            selected_cycle.cycle_start_date
                        )

                        cycle_day = (
                            selected_cycle_day
                        )

                        cycle_item = (
                            cycle_item_map.get(
                                (
                                    cycle_start_date,
                                    cycle_day,
                                    meal_type,
                                )
                            )
                        )

                        if cycle_item:

                            menu_id = cycle_item.menu_id

                            if source is None:
                                source = "cycle"

                        else:
                            menu_id = None

                    else:
                        menu_id = None

                resolved_items.append(
                    {
                        "date": current_date,
                        "day_number": day_number,
                        "meal_type": meal_type,
                        "menu_id": menu_id,
                        "source": source,
                    }
                )

            current_date += timedelta(days=1)
            day_number += 1

        # =====================================================
        # 11. COLLECT ALL MENU IDS
        # =====================================================

        menu_ids = {
            item["menu_id"]
            for item in resolved_items
            if item["menu_id"] is not None
        }

        # =====================================================
        # 12. LOAD ALL MENUS — ONE QUERY
        # =====================================================

        menu_map = {}

        if menu_ids:

            menus = (
                db.query(Menu)
                .filter(
                    Menu.id.in_(menu_ids),
                    Menu.chef_id
                    == subscription.chef_id,
                    Menu.is_deleted.is_(False),
                )
                .all()
            )

            menu_map = {
                menu.id: menu
                for menu in menus
            }

        # =====================================================
        # 13. MEAL ORDER
        # =====================================================

        meal_order = {
            "breakfast": 1,
            "lunch": 2,
            "dinner": 3,
        }

        # =====================================================
        # 14. BUILD RESPONSE
        # =====================================================

        result_days = []

        current_day_number = 0
        current_date = subscription_start_date

        while (
            current_date <= subscription_end_date
            and current_day_number
            < subscription_duration
        ):

            current_day_number += 1

            day_items = [
                item
                for item in resolved_items
                if item["date"] == current_date
            ]

            meals = []

            for item in day_items:

                meal_type = item["meal_type"]

                schedule = schedule_map.get(
                    (
                        current_date,
                        meal_type,
                    )
                )

                menu = menu_map.get(
                    item["menu_id"]
                )

                # =============================================
                # NORMAL PRICE
                # =============================================

                normal_price = (
                    float(menu.price)
                    if menu
                    and menu.price is not None
                    else 0.0
                )

                # =============================================
                # SUBSCRIPTION PRICE
                # =============================================

                subscription_price = max(
                    normal_price - 10.0,
                    0.0,
                )

                # =============================================
                # IMAGE
                # =============================================

                menu_image = None

                if menu and menu.image_urls:
                    menu_image = (
                        menu.image_urls[0]
                    )

                # =============================================
                # MENU DATA
                # =============================================

                menu_data = None

                if menu:

                    menu_data = {
                        "id": str(menu.id),

                        "name": menu.name,

                        "description":
                            menu.description,

                        "price":
                            subscription_price,

                        "normal_price":
                            normal_price,

                        "subscription_price":
                            subscription_price,

                        "category":
                            menu.category,

                        "food_type":
                            menu.food_type,

                        "calories":
                            menu.calories,

                        "protein":
                            menu.protein,

                        "carbs":
                            menu.carbs,

                        "fats":
                            menu.fats,

                        "ingredients":
                            menu.ingredients or [],

                        "image_urls":
                            menu.image_urls or [],

                        "menu_image":
                            menu_image,

                        "source":
                            item["source"],
                    }

                # =============================================
                # SCHEDULE DATA
                # =============================================

                schedule_id = (
                    str(schedule.id)
                    if schedule
                    else None
                )

                status = (
                    schedule.status
                    if schedule
                    else "on"
                )

                cutoff_at = (
                    schedule.cutoff_at
                    if schedule
                    else None
                )

                # =============================================
                # MEAL RESPONSE
                # =============================================

                meals.append(
                    {
                        "id":
                            schedule_id,

                        "schedule_id":
                            schedule_id,

                        "subscription_id":
                            str(subscription.id),

                        "date":
                            current_date,

                        "meal_type":
                            meal_type,

                        "status":
                            status,

                        "cutoff_at":
                            cutoff_at,

                        "menu_id":
                            (
                                str(menu.id)
                                if menu
                                else None
                            ),

                        "menu_name":
                            (
                                menu.name
                                if menu
                                else None
                            ),

                        "menu_description":
                            (
                                menu.description
                                if menu
                                else None
                            ),

                        "meal_price":
                            subscription_price,

                        "menu_price":
                            subscription_price,

                        "normal_menu_price":
                            normal_price,

                        "subscription_price":
                            subscription_price,

                        "menu":
                            menu_data,

                        "menu_category":
                            (
                                menu.category
                                if menu
                                else None
                            ),

                        "food_type":
                            (
                                menu.food_type
                                if menu
                                else None
                            ),

                        "calories":
                            (
                                menu.calories
                                if menu
                                else None
                            ),

                        "protein":
                            (
                                menu.protein
                                if menu
                                else None
                            ),

                        "carbs":
                            (
                                menu.carbs
                                if menu
                                else None
                            ),

                        "fats":
                            (
                                menu.fats
                                if menu
                                else None
                            ),

                        "ingredients":
                            (
                                menu.ingredients or []
                                if menu
                                else []
                            ),

                        "image_urls":
                            (
                                menu.image_urls or []
                                if menu
                                else []
                            ),

                        "menu_image":
                            menu_image,

                        "chef_id":
                            str(subscription.chef_id),

                        "chef_name":
                            None,

                        "source":
                            item["source"],
                    }
                )

            # =================================================
            # BREAKFAST → LUNCH → DINNER
            # =================================================

            meals.sort(
                key=lambda meal:
                    meal_order.get(
                        meal["meal_type"],
                        99,
                    )
            )

            result_days.append(
                {
                    "date":
                        current_date,

                    "day":
                        current_date.strftime(
                            "%A"
                        ),

                    "day_number":
                        current_day_number,

                    "meals":
                        meals,
                }
            )

            current_date += timedelta(days=1)

        # =====================================================
        # 15. FINAL RESPONSE
        # =====================================================

        response = {
            "success": True,

            "subscription_id":
                str(subscription.id),

            "start_date":
                subscription_start_date,

            "end_date":
                subscription_end_date,

            "subscription_duration":
                subscription_duration,

            "breakfast_enabled":
                bool(
                    subscription.breakfast_enabled
                ),

            "total_days":
                len(result_days),

            "days":
                result_days,
        }

        # =====================================================
        # 16. CACHE
        # =====================================================

        set_cache(
            cache_key,
            response,
            ttl=30,
        )

        logger.info(
            "✅ Subscription Menu Cycle "
            "Loaded with BATCH QUERIES: "
            "subscription=%s "
            "days=%s",
            subscription_id,
            len(result_days),
        )

        return response

    except HTTPException:
        raise

    except Exception as e:

        logger.exception(
            "❌ Failed to load subscription menu cycle: "
            "subscription_id=%s "
            "user_id=%s "
            "error=%s",
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

# =========================================================
# TURN MEAL OFF
# =========================================================

# =========================================================
# TURN MEAL OFF
# =========================================================

# =========================================================
# TURN MEAL OFF
# =========================================================

# =========================================================
# TURN MEAL OFF
# =========================================================

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
    # =====================================================
    # 1. VALIDATE MEAL TYPE
    # =====================================================

    meal_type = (meal_type or "").lower().strip()

    if meal_type not in MEAL_CUTOFF_TIMES:
        raise HTTPException(
            status_code=400,
            detail="Invalid meal type",
        )

    # =====================================================
    # 2. FIND SUBSCRIPTION
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
    # 3. BREAKFAST VALIDATION
    # =====================================================

    if (
        meal_type == "breakfast"
        and not subscription.breakfast_enabled
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Breakfast is not enabled "
                "for this subscription"
            ),
        )

    # =====================================================
    # 4. CURRENT TIME
    # =====================================================

    now = datetime.now(IST)
    today = now.date()

    # =====================================================
    # 5. FIND TODAY'S MEAL
    # =====================================================

    meal = (
        db.query(SubscriptionMealSchedule)
        .filter(
            SubscriptionMealSchedule.subscription_id
            == subscription.id,
            SubscriptionMealSchedule.date == today,
            SubscriptionMealSchedule.meal_type
            == meal_type,
        )
        .first()
    )

    if not meal:
        raise HTTPException(
            status_code=404,
            detail=(
                f"{meal_type.title()} "
                f"is not scheduled for today"
            ),
        )

    # =====================================================
    # 6. CUTOFF CHECK
    # =====================================================

    if now >= meal.cutoff_at:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{meal_type.title()} cutoff time "
                f"has passed. "
                f"You cannot turn this meal off now."
            ),
        )

    # =====================================================
    # 7. ALREADY OFF
    # =====================================================

    if meal.status == "off":
        return {
            "message": (
                f"{meal_type.title()} is already off"
            ),
            "subscription_id": str(subscription.id),
            "date": today,
            "meal_type": meal_type,
            "status": "off",
            "wallet_credit": 0.0,
            "cutoff_at": meal.cutoff_at,
        }

    # =====================================================
    # 8. GET TODAY'S ACTUAL NORMAL MENU
    #
    # IMPORTANT:
    # Wallet amount MUST be same as today's
    # subscription meal price.
    #
    # Normal Menu ₹180
    # Subscription ₹170
    #
    # OFF → wallet +₹170
    # =====================================================

    normal_menu, source = get_menu_for_day(
        db=db,
        chef_id=subscription.chef_id,
        target_date=today,
        meal_type=meal_type,
    )

    if not normal_menu:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Today's {meal_type.title()} "
                f"menu not found"
            ),
        )

    # =====================================================
    # 9. CALCULATE CURRENT SUBSCRIPTION PRICE
    # =====================================================

    normal_menu_price = float(
        normal_menu.price or 0.0
    )

    amount = max(
        normal_menu_price - 10.0,
        0.0,
    )

    # =====================================================
    # 10. SAFETY CHECK
    # =====================================================

    if amount <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unable to calculate wallet credit "
                f"for today's {meal_type.title()} meal."
            ),
        )

    try:

        # =================================================
        # 11. TURN TODAY'S MEAL OFF
        # =================================================

        meal.status = "off"

        # =================================================
        # 12. TOMORROW'S SAME MEAL MUST ALWAYS BE ON
        #
        # Example:
        # Today Lunch  -> OFF
        # Tomorrow Lunch -> ON
        #
        # Today Dinner -> OFF
        # Tomorrow Dinner -> ON
        #
        # Today Breakfast -> OFF
        # Tomorrow Breakfast -> ON
        # =================================================

        tomorrow = today + timedelta(days=1)

        tomorrow_meal = (
            db.query(SubscriptionMealSchedule)
            .filter(
                SubscriptionMealSchedule.subscription_id
                == subscription.id,
                SubscriptionMealSchedule.date == tomorrow,
                SubscriptionMealSchedule.meal_type
                == meal_type,
            )
            .first()
        )

        if tomorrow_meal:
            tomorrow_meal.status = "on"

        # =================================================
        # 13. CREDIT WALLET
        # =================================================

        credit_wallet(
            db=db,
            user_id=user.id,
            amount=amount,
            transaction_type="meal_off_credit",
            meal_type=meal_type,
            subscription_id=subscription.id,
            schedule_id=meal.id,
            description=(
                f"{meal_type.title()} meal "
                f"turned off for {today}"
            ),
        )

        # =================================================
        # 14. CUSTOMER NOTIFICATION
        # =================================================

        notification = Notification(
            user_id=user.id,
            type="wallet",
            title="Meal Turned Off 💰",
            message=(
                f"Your {meal_type.title()} meal "
                f"has been turned off. "
                f"₹{amount:.2f} has been added "
                f"to your wallet."
            ),
        )

        db.add(notification)

        # =================================================
        # 15. CHEF NOTIFICATION
        # =================================================

        chef_notification = Notification(
            user_id=subscription.chef_id,
            type="subscription_meal",
            title="Meal Turned Off ⚠️",
            message=(
                f"{user.name} has turned OFF "
                f"{meal_type.title()} for {today}. "
                f"₹{amount:.2f} has been credited "
                f"to the customer's wallet."
            ),
        )

        db.add(chef_notification)

        # =================================================
        # 16. COMMIT
        # =================================================

        db.commit()
        db.refresh(meal)

        wallet = (
            db.query(Wallet)
            .filter(
                Wallet.user_id == user.id
            )
            .first()
        )

        wallet_balance = (
            float(wallet.balance or 0.0)
            if wallet
            else 0.0
        )

        # =================================================
        # 17. CLEAR TODAY CACHE
        # =================================================

        delete_cache(
            f"subscription:today:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        delete_cache(
            f"subscription:today:v2:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        # =================================================
        # 18. CLEAR MENU CYCLE CACHE
        # =================================================

        delete_cache(
            f"subscription:menu-cycle:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        delete_cache(
            f"subscription:menu-cycle:v2:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        delete_cache(
            f"subscription:menu-cycle:v3:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        delete_cache(
            f"subscription:menu-cycle:v4:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        # =================================================
        # 19. CLEAR SUBSCRIPTION MEALS CACHE
        # =================================================

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
            f"subscription:meals:v5:"
            f"{subscription.id}:"
            f"{user.id}:False"
        )

        delete_cache(
            f"subscription:meals:v5:"
            f"{subscription.id}:"
            f"{user.id}:True"
        )

        # =================================================
        # IMPORTANT:
        # WhatsApp call removed from here.
        #
        # DB commit + wallet update should return
        # immediately without waiting for WhatsApp API.
        # =================================================

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        logger.exception(
            "❌ Failed to turn meal OFF: %s",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to turn meal off",
        )

    # =====================================================
    # 20. RESPONSE
    # =====================================================

    return {
        "message": (
            f"{meal_type.title()} "
            f"turned off successfully"
        ),
        "subscription_id": str(
            subscription.id
        ),
        "date": today,
        "meal_type": meal_type,
        "status": "off",
        "wallet_credit": amount,
        "wallet_balance": wallet_balance,
        "cutoff_at": meal.cutoff_at,
    }
# =========================================================
# TURN MEAL ON
# =========================================================

# =========================================================
# TURN MEAL ON
# =========================================================

# =========================================================
# TURN MEAL ON
# =========================================================

# =========================================================
# TURN MEAL ON
# =========================================================

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
    # =====================================================
    # 1. VALIDATE MEAL TYPE
    # =====================================================

    meal_type = (meal_type or "").lower().strip()

    if meal_type not in MEAL_CUTOFF_TIMES:
        raise HTTPException(
            status_code=400,
            detail="Invalid meal type",
        )

    # =====================================================
    # 2. FIND SUBSCRIPTION
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
    # 3. BREAKFAST VALIDATION
    # =====================================================

    if (
        meal_type == "breakfast"
        and not subscription.breakfast_enabled
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Breakfast is not enabled "
                "for this subscription"
            ),
        )

    # =====================================================
    # 4. CURRENT TIME
    # =====================================================

    now = datetime.now(IST)
    today = now.date()

    # =====================================================
    # 5. FIND TODAY'S MEAL
    # =====================================================

    meal = (
        db.query(SubscriptionMealSchedule)
        .filter(
            SubscriptionMealSchedule.subscription_id
            == subscription.id,
            SubscriptionMealSchedule.date == today,
            SubscriptionMealSchedule.meal_type
            == meal_type,
        )
        .first()
    )

    if not meal:
        raise HTTPException(
            status_code=404,
            detail=(
                f"{meal_type.title()} "
                f"is not scheduled for today"
            ),
        )

    # =====================================================
    # 6. CUTOFF CHECK
    # =====================================================

    if now >= meal.cutoff_at:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{meal_type.title()} cutoff time "
                f"has passed. "
                f"You cannot turn this meal on now."
            ),
        )

    # =====================================================
    # 7. ALREADY ON
    # =====================================================

    if meal.status == "on":
        return {
            "message": (
                f"{meal_type.title()} is already on"
            ),
            "subscription_id": str(
                subscription.id
            ),
            "date": today,
            "meal_type": meal_type,
            "status": "on",
            "wallet_debit": 0.0,
            "cutoff_at": meal.cutoff_at,
        }

    # =====================================================
    # 8. GET TODAY'S ACTUAL NORMAL MENU
    #
    # IMPORTANT:
    # Wallet amount MUST be same as today's
    # subscription meal price.
    #
    # Normal Menu ₹180
    # Subscription ₹170
    #
    # ON → wallet -₹170
    # =====================================================

    normal_menu, source = get_menu_for_day(
        db=db,
        chef_id=subscription.chef_id,
        target_date=today,
        meal_type=meal_type,
    )

    if not normal_menu:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Today's {meal_type.title()} "
                f"menu not found"
            ),
        )

    # =====================================================
    # 9. CALCULATE CURRENT SUBSCRIPTION PRICE
    # =====================================================

    normal_menu_price = float(
        normal_menu.price or 0.0
    )

    amount = max(
        normal_menu_price - 10.0,
        0.0,
    )

    # =====================================================
    # 10. SAFETY CHECK
    # =====================================================

    if amount <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unable to calculate wallet debit "
                f"for today's {meal_type.title()} meal."
            ),
        )

    try:

        # =================================================
        # 11. DEBIT WALLET
        # =================================================

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
                    f"{meal_type.title()} meal "
                    f"turned on for {today}"
                ),
            )

        except ValueError:
            db.rollback()

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient wallet balance. "
                    f"₹{amount:.2f} required to "
                    f"turn {meal_type.title()} "
                    f"back on."
                ),
            )

        # =================================================
        # 12. TURN MEAL ON
        # =================================================

        meal.status = "on"

        # =================================================
        # 13. CUSTOMER NOTIFICATION
        # =================================================

        notification = Notification(
            user_id=user.id,
            type="wallet",
            title="Meal Turned On 🍱",
            message=(
                f"Your {meal_type.title()} meal "
                f"has been turned on. "
                f"₹{amount:.2f} has been deducted "
                f"from your wallet."
            ),
        )

        db.add(notification)

        # =================================================
        # 14. CHEF NOTIFICATION
        # =================================================

        chef_notification = Notification(
            user_id=subscription.chef_id,
            type="subscription_meal",
            title="Meal Turned On 🍱",
            message=(
                f"{user.name} has turned ON "
                f"{meal_type.title()} for {today}. "
                f"₹{amount:.2f} has been deducted "
                f"from the customer's wallet."
            ),
        )

        db.add(chef_notification)

        # =================================================
        # 15. COMMIT
        # =================================================

        db.commit()
        db.refresh(meal)
        
                # =================================================
        # GET UPDATED WALLET BALANCE
        # =================================================

        wallet = (
            db.query(Wallet)
            .filter(
                Wallet.user_id == user.id
            )
            .first()
        )

        wallet_balance = (
            float(wallet.balance or 0.0)
            if wallet
            else 0.0
        )

        # =================================================
        # 16. CLEAR TODAY CACHE
        # =================================================

        delete_cache(
            f"subscription:today:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        delete_cache(
            f"subscription:today:v2:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        # =================================================
        # 17. CLEAR MENU CYCLE CACHE
        # =================================================

        delete_cache(
            f"subscription:menu-cycle:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        delete_cache(
            f"subscription:menu-cycle:v2:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        delete_cache(
            f"subscription:menu-cycle:v3:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        delete_cache(
            f"subscription:menu-cycle:v4:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        # =================================================
        # 18. CLEAR SUBSCRIPTION MEALS CACHE
        # =================================================

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
            f"subscription:meals:v5:"
            f"{subscription.id}:"
            f"{user.id}:False"
        )

        delete_cache(
            f"subscription:meals:v5:"
            f"{subscription.id}:"
            f"{user.id}:True"
        )

        # =================================================
        # IMPORTANT:
        # WhatsApp call removed from here.
        #
        # DB commit + wallet update should return
        # immediately without waiting for WhatsApp API.
        # =================================================

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        logger.exception(
            "❌ Failed to turn meal ON: %s",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to turn meal on",
        )

    # =====================================================
    # 19. RESPONSE
    # =====================================================

    return {
        "message": (
            f"{meal_type.title()} "
            f"turned on successfully"
        ),
        "subscription_id": str(
            subscription.id
        ),
        "date": today,
        "meal_type": meal_type,
        "status": "on",

        # Wallet
        "wallet_debit": amount,
        "wallet_balance": wallet_balance,

        # Price
        "normal_menu_price": normal_menu_price,
        "subscription_price": amount,

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
        # 1. RAZORPAY SECRET
        # =========================================

        key_secret = os.getenv("RAZORPAY_KEY_SECRET")

        if not key_secret:
            raise HTTPException(
                status_code=500,
                detail="Razorpay key missing",
            )

        # =========================================
        # 2. FIND SUBSCRIPTION
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
        # 3. ACTIVE CHECK
        # =========================================

        if subscription.status != "active":
            raise HTTPException(
                status_code=400,
                detail="Subscription is not active",
            )

        # =========================================
        # 4. ALREADY ENABLED
        # =========================================

        if subscription.breakfast_enabled:
            raise HTTPException(
                status_code=400,
                detail="Breakfast already enabled",
            )

        # =========================================
        # 5. FIND PLAN
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
        # 6. BREAKFAST AVAILABILITY
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
        # 7. USE LOCKED SUBSCRIPTION PRICE
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
        # 8. VERIFY RAZORPAY SIGNATURE
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
        # 9. ENABLE BREAKFAST
        # =========================================

        subscription.breakfast_enabled = True
        subscription.breakfast_price = breakfast_price

        # =========================================
        # 10. SUBSCRIPTION DATES
        # =========================================

        today = datetime.now(IST).date()

        start = (
            subscription.start_date.date()
            if isinstance(
                subscription.start_date,
                datetime,
            )
            else subscription.start_date
        )

        end = (
            subscription.end_date.date()
            if isinstance(
                subscription.end_date,
                datetime,
            )
            else subscription.end_date
        )

        # =========================================
        # 11. BREAKFAST START DATE
        # =========================================

        calculation_start = max(
            today,
            start,
        )

        # =========================================
        # 12. DELIVERY DAY MAP
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
        # 13. CREATE BREAKFAST SCHEDULES
        # =========================================

        current_date = calculation_start

        while current_date <= end:

            # -----------------------------------------
            # ONLY SELECTED DELIVERY DAYS
            # -----------------------------------------

            if current_date.weekday() in delivery_weekdays:

                # -----------------------------------------
                # CHECK EXISTING BREAKFAST SCHEDULE
                # -----------------------------------------

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
                    # GET BREAKFAST MENU FOR EXACT DATE
                    #
                    # Priority inside get_menu_for_day():
                    # 1. Date override
                    # 2. 30-day cycle
                    # 3. Repeating cycle
                    # =========================================

                    menu, source = get_menu_for_day(
                        db=db,
                        chef_id=subscription.chef_id,
                        target_date=current_date,
                        meal_type="breakfast",
                    )

                    # =========================================
                    # MENU MUST EXIST
                    # =========================================

                    if not menu:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"No breakfast menu configured "
                                f"for "
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

                            # Exact menu for this date
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
        # 14. SAVE DATABASE
        # =========================================
        customer_notification = Notification(
            user_id=user.id,
            type="subscription",
            title="Breakfast Added 🍳",
            message=(
             f"Breakfast has been added to your subscription "
             f"for ₹{breakfast_price:.2f} per day."
            ),
        )
        
        chef_notification = Notification(
            user_id=subscription.chef_id,
            type="subscription",
            title="Breakfast Add-on Received 🍳",
            message=(
               f"{user.name} added Breakfast to their subscription "
               f"for ₹{breakfast_price:.2f} per day."
            ),
        )
        db.add(customer_notification)
        db.add(chef_notification)
        db.commit()

        db.refresh(subscription)

        # =========================================
        # 15. CLEAR MY SUBSCRIPTION CACHE
        # =========================================

        delete_cache(
            f"subscription:my:{user.id}"
        )

        # =========================================
        # 16. CLEAR ACTIVE SUBSCRIPTION CACHE
        # =========================================

        delete_cache(
            f"subscription:active:{user.id}"
        )

        # =========================================
        # 17. CLEAR TODAY CACHE
        # =========================================

        delete_cache(
            f"subscription:today:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        delete_cache(
            f"subscription:today:v2:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        # =========================================
        # 18. CLEAR SUBSCRIPTION MEALS CACHE
        # =========================================

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

        # =========================================
        # 19. CLEAR MENU CYCLE CACHE
        # =========================================

        delete_cache(
            f"subscription:menu-cycle:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        delete_cache(
            f"subscription:menu-cycle:v2:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        delete_cache(
            f"subscription:menu-cycle:v3:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        delete_cache(
            f"subscription:menu-cycle:v4:"
            f"{subscription.id}:"
            f"{user.id}"
        )

        # =========================================
        # 20. SUCCESS RESPONSE
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

    # =============================================
    # HTTP EXCEPTION
    # =============================================

    except HTTPException:
        raise

    # =============================================
    # GENERAL EXCEPTION
    # =============================================

    except Exception as e:

        db.rollback()

        logger.exception(
            "❌ BREAKFAST VERIFY ERROR: %s",
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
    
# =========================================================
# ADMIN — GET ALL SUBSCRIPTIONS
# =========================================================

# =========================================================
# ADMIN — GET ALL SUBSCRIPTIONS
# =========================================================

@router.get("/admin/all")
def get_all_subscriptions_admin(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # -----------------------------------------------------
    # ADMIN ACCESS CHECK
    # -----------------------------------------------------

    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )

    # -----------------------------------------------------
    # LOAD SUBSCRIPTIONS
    # -----------------------------------------------------

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
            User.id == Subscription.user_id,
        )
        .order_by(
            Subscription.start_date.desc()
        )
        .all()
    )

    # -----------------------------------------------------
    # BUILD RESPONSE
    # -----------------------------------------------------

    result = []

    # Today's date — India
    today = datetime.now(IST).date()

    for subscription, plan, customer in rows:

        # -------------------------------------------------
        # EXACT SUBSCRIPTION DURATION
        # -------------------------------------------------

        duration_days = 0

        start_date = None
        end_date = None

        if (
            subscription.start_date
            and subscription.end_date
        ):
            start_date = (
                subscription.start_date.date()
                if isinstance(
                    subscription.start_date,
                    datetime,
                )
                else subscription.start_date
            )

            end_date = (
                subscription.end_date.date()
                if isinstance(
                    subscription.end_date,
                    datetime,
                )
                else subscription.end_date
            )

            duration_days = (
                end_date - start_date
            ).days + 1

        # -------------------------------------------------
        # TODAY'S DIET STATUS
        # -------------------------------------------------
        #
        # IMPORTANT:
        # subscription.status != diet status
        #
        # Diet ON/OFF is controlled by today's
        # SubscriptionMealSchedule.
        # -------------------------------------------------

        today_schedule = (
            db.query(SubscriptionMealSchedule)
            .filter(
                SubscriptionMealSchedule.subscription_id
                == subscription.id,
                SubscriptionMealSchedule.date
                == today,
            )
            .first()
        )

        diet_on = (
            today_schedule.status == "on"
            if today_schedule
            else False
        )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        result.append(
            {
                "id": str(subscription.id),

                # Customer
                "customer_id": (
                    str(subscription.user_id)
                    if subscription.user_id
                    else None
                ),

                "customer_name": (
                    customer.name
                    if customer
                    else subscription.customer_name
                ),

                "customer_phone": (
                    getattr(customer, "phone", None)
                    if customer
                    else None
                ),

                "customer_email": (
                    getattr(customer, "email", None)
                    if customer
                    else None
                ),

                # Chef
                "chef_id": (
                    str(subscription.chef_id)
                    if subscription.chef_id
                    else None
                ),

                # Plan
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

                # Subscription
                "duration_days": duration_days,

                "start_date": start_date,

                "end_date": end_date,

                "status": subscription.status,

                "price": float(
                    subscription.price or 0
                ),

                # Delivery
                "delivery_time": (
                    subscription.delivery_time
                ),

                "delivery_days": (
                    subscription.delivery_days or []
                ),

                # Meals
                "meals_per_day": (
                    subscription.meals_per_day or 0
                ),

                # Breakfast
                "breakfast_enabled": bool(
                    subscription.breakfast_enabled
                ),

                "breakfast_price": float(
                    subscription.breakfast_price or 0
                ),

                # Today's Diet ON / OFF
                "diet_on": diet_on,
            }
        )

    return {
        "success": True,
        "total": len(result),
        "subscriptions": result,
    }
    
    
    
    
# =========================================================
# ADMIN — SUBSCRIPTION CONTROLS
# =========================================================
#
# Admin can:
# 1. Activate / deactivate subscription
# 2. Turn today's diet ON / OFF
# 3. Turn breakfast ON / OFF
#
# IMPORTANT:
# - Subscription status controls subscription itself.
# - Diet ON/OFF controls today's SubscriptionMealSchedule.
# - Breakfast controls subscription.breakfast_enabled.
# =========================================================


# =========================================================
# ADMIN — SUBSCRIPTION CONTROLS
# =========================================================

class AdminSubscriptionStatusUpdate(BaseModel):
    status: str


class AdminDietUpdate(BaseModel):
    diet_on: bool


class AdminBreakfastUpdate(BaseModel):
    breakfast_enabled: bool


# =========================================================
# ADMIN — UPDATE SUBSCRIPTION STATUS
# =========================================================

# =========================================================
# ADMIN — UPDATE SUBSCRIPTION STATUS
# =========================================================

@router.put("/admin/{subscription_id}/status")
def admin_update_subscription_status(
    subscription_id: UUID,
    data: AdminSubscriptionStatusUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # ---------------------------------------------------------
    # ADMIN CHECK
    # ---------------------------------------------------------
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )

    # ---------------------------------------------------------
    # NORMALIZE STATUS
    # ---------------------------------------------------------
    status = data.status.lower().strip()

    if status not in ("active", "inactive"):
        raise HTTPException(
            status_code=400,
            detail="Status must be active or inactive",
        )

    # ---------------------------------------------------------
    # GET SUBSCRIPTION
    # ---------------------------------------------------------
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id == subscription_id
        )
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    # ---------------------------------------------------------
    # UPDATE SUBSCRIPTION STATUS
    # ---------------------------------------------------------
    subscription.status = status

    # ---------------------------------------------------------
    # UPDATE ALL MEAL SCHEDULES
    #
    # INACTIVE:
    #   All schedules -> OFF
    #
    # ACTIVE:
    #   All schedules -> ON
    # ---------------------------------------------------------
    schedules = (
        db.query(SubscriptionMealSchedule)
        .filter(
            SubscriptionMealSchedule.subscription_id
            == subscription.id
        )
        .all()
    )

    for schedule in schedules:
        if status == "inactive":
            schedule.status = "off"
        else:
            schedule.status = "on"

    # ---------------------------------------------------------
    # SAVE CHANGES
    # ---------------------------------------------------------
    db.commit()
    db.refresh(subscription)

    # ---------------------------------------------------------
    # CLEAR CUSTOMER SUBSCRIPTION CACHES
    # ---------------------------------------------------------
    if subscription.user_id:

        delete_cache(
            f"subscription:my:{subscription.user_id}"
        )

        delete_cache(
            f"subscription:active:{subscription.user_id}"
        )

        delete_cache(
            f"subscription:today:"
            f"{subscription.id}:"
            f"{subscription.user_id}"
        )

        delete_cache(
            f"subscription:today:v2:"
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

        # -----------------------------------------------------
        # IMPORTANT:
        # Latest subscription meals cache
        # -----------------------------------------------------
        delete_cache(
            f"subscription:meals:v5:"
            f"{subscription.id}:"
            f"{subscription.user_id}:False"
        )

        delete_cache(
            f"subscription:meals:v5:"
            f"{subscription.id}:"
            f"{subscription.user_id}:True"
        )

    # ---------------------------------------------------------
    # RESPONSE
    # ---------------------------------------------------------
    return {
        "success": True,
        "subscription_id": str(subscription.id),
        "status": subscription.status,
    }


# =========================================================
# ADMIN — TODAY DIET ON / OFF
# =========================================================

@router.put("/admin/{subscription_id}/diet")
def admin_update_subscription_diet(
    subscription_id: UUID,
    data: AdminDietUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )

    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id == subscription_id
        )
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    if subscription.status != "active":
        raise HTTPException(
            status_code=400,
            detail="Subscription is inactive",
        )

    today = datetime.now(IST).date()

    schedules = (
        db.query(SubscriptionMealSchedule)
        .filter(
            SubscriptionMealSchedule.subscription_id
            == subscription.id,
            SubscriptionMealSchedule.date == today,
        )
        .all()
    )

    if not schedules:
        raise HTTPException(
            status_code=404,
            detail="No meal schedule found for today",
        )

    new_status = "on" if data.diet_on else "off"

    for schedule in schedules:
        schedule.status = new_status

    db.commit()

    # Clear caches
    if subscription.user_id:
        delete_cache(
            f"subscription:today:"
            f"{subscription.id}:"
            f"{subscription.user_id}"
        )

        delete_cache(
            f"subscription:today:v2:"
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
        "subscription_id": str(subscription.id),
        "date": today,
        "diet_on": data.diet_on,
    }


# =========================================================
# ADMIN — BREAKFAST ON / OFF
# =========================================================

@router.put("/admin/{subscription_id}/breakfast")
def admin_update_subscription_breakfast(
    subscription_id: UUID,
    data: AdminBreakfastUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )

    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id == subscription_id
        )
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    subscription.breakfast_enabled = (
        data.breakfast_enabled
    )

    # If breakfast is OFF,
    # today's breakfast schedule must also be OFF.
    if not data.breakfast_enabled:

        today = datetime.now(IST).date()

        breakfast_schedules = (
            db.query(SubscriptionMealSchedule)
            .filter(
                SubscriptionMealSchedule.subscription_id
                == subscription.id,
                SubscriptionMealSchedule.date == today,
                SubscriptionMealSchedule.meal_type
                == "breakfast",
            )
            .all()
        )

        for schedule in breakfast_schedules:
            schedule.status = "off"

    db.commit()
    db.refresh(subscription)

    # Clear caches
    if subscription.user_id:
        delete_cache(
            f"subscription:my:{subscription.user_id}"
        )

        delete_cache(
            f"subscription:active:{subscription.user_id}"
        )

        delete_cache(
            f"subscription:today:"
            f"{subscription.id}:"
            f"{subscription.user_id}"
        )

        delete_cache(
            f"subscription:today:v2:"
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
        "subscription_id": str(subscription.id),
        "breakfast_enabled": bool(
            subscription.breakfast_enabled
        ),
    }