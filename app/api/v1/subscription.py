import logging
logger = logging.getLogger(__name__)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from uuid import UUID
import uuid
from app.models.notification import Notification
from app.models.subscription_meal_schedule import SubscriptionMealSchedule
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
from app.models.user import User
from math import radians, cos, sin, asin, sqrt
from fastapi import Query

import os
import base64
import hmac
import hashlib
import requests
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

from pydantic import BaseModel


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
    Create meal schedules for every delivery date
    of the subscription.
    """

    # Plan ke meals
    meals = {
     "lunch",
     "dinner",
    }
    if subscription.breakfast_enabled:
        meals.add("breakfast")
        
    # Customer ke selected delivery days
    delivery_days = {
        day.strip().lower()[:3]
        for day in (subscription.delivery_days or [])
    }

    current_date = subscription.start_date.date()
    end_date = subscription.end_date.date()

    while current_date <= end_date:

        weekday = current_date.strftime("%a").lower()

        if weekday in delivery_days:

            for meal_type in meals:

                cutoff_time = MEAL_CUTOFF_TIMES[meal_type]

                cutoff_at = datetime.combine(
                    current_date,
                    cutoff_time,
                    tzinfo=IST,
                )
                
                if meal_type == "breakfast":
                    meal_price = plan.breakfast_price or 0.0  
                elif meal_type == "lunch":
                    meal_price = plan.lunch_price or 0.0
                elif meal_type == "dinner":
                    meal_price = plan.dinner_price or 0.0
                else:
                    meal_price = 0.0

                schedule = SubscriptionMealSchedule(
                    subscription_id=subscription.id,
                    date=current_date,
                    meal_type=meal_type,
                    meal_price=meal_price,
                    status="on",
                    cutoff_at=cutoff_at,
                )

                db.add(schedule)

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
        
        chef = db.query(User).filter(
          User.id == s.chef_id
          ).first()

        result.append({
            "id": str(s.id),

            "plan": plan.title if plan else "Subscription Plan",

            "plan_type": plan.plan_type if plan else None,

            "chefName": chef.name if chef else "Chef",

            "startDate": s.start_date.strftime("%b %d, %Y"),

            "endDate": s.end_date.strftime("%b %d, %Y"),

            "time": s.delivery_time,

            "days": s.delivery_days or [],

            "status": s.status,

            "price": s.price,

            # BREAKFAST
            "breakfast_enabled": s.breakfast_enabled,

            "breakfast_price": s.breakfast_price,

            # MEALS
            "meals_per_day": s.meals_per_day,
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

    delivery_days = ALL_DELIVERY_DAYS.copy()

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

    # ========= CREATE =========
    # =========================================================
# BREAKFAST VALIDATION
# =========================================================

        # ========= CREATE =========
    # =========================================================
    # BREAKFAST VALIDATION
    # =========================================================
    # =========================================================
# BREAKFAST PRICE SNAPSHOT
# =========================================================

    breakfast_price = None

    if plan.breakfast_available:

        if not plan.breakfast_price or plan.breakfast_price <= 0:
            raise HTTPException(
               status_code=400,
               detail="Breakfast price is not configured for this plan",
            )

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
    plans = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.chef_id == user.id
    ).all()

    return plans

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
    active = db.query(Subscription).filter(
        Subscription.user_id == user.id,
        Subscription.status == "active"
    ).first()

    if not active:
        return {
            "has_active_subscription": False
        }

    return {
        "has_active_subscription": True,
        "end_date": active.end_date
    }

@router.get("/my")
def my_subscriptions(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    subs = db.query(Subscription).filter(
        Subscription.user_id == user.id
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

             "plan": plan.title if plan else "Subscription Plan",

             "plan_type": plan.plan_type if plan else None,

             "chefName": chef.name if chef else "Chef",

             "startDate": s.start_date.strftime("%b %d, %Y"),

             "endDate": s.end_date.strftime("%b %d, %Y"),

             "time": s.delivery_time,

             "days": s.delivery_days or [],

             "status": s.status,

             "price": s.price,

             "breakfast_enabled": s.breakfast_enabled,
             "breakfast_price": s.breakfast_price,

    
             "meals_per_day": s.meals_per_day,
            })

    return result

IST = ZoneInfo("Asia/Kolkata")

MEAL_CUTOFF_TIMES = {
    "breakfast": time(8, 0),
    "lunch": time(10, 0),
    "dinner": time(17, 0),
}

def get_meal_wallet_amount(
    meal: SubscriptionMealSchedule,
) -> float:

    amount = meal.meal_price

    if amount is None or amount <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Price is not configured for {meal.meal_type}.",
        )

    return amount


# =========================================================
# GET TODAY'S MEAL SCHEDULE
# =========================================================

@router.get("/{subscription_id}/meals/today")
def get_today_meals(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
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

    today = datetime.now(IST).date()

    meals = (
        db.query(SubscriptionMealSchedule)
        .filter(
            SubscriptionMealSchedule.subscription_id == subscription.id,
            SubscriptionMealSchedule.date == today,
        )
        .order_by(SubscriptionMealSchedule.meal_type)
        .all()
    )

    return [
        {
            "id": str(meal.id),
            "subscription_id": str(meal.subscription_id),
            "date": meal.date,
            "meal_type": meal.meal_type,
            "meal_price": meal.meal_price,
            "status": meal.status,
            "cutoff_at": meal.cutoff_at,
            
        }
        for meal in meals
    ]


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

    amount = get_meal_wallet_amount(
     meal=meal,
    )

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

    amount = get_meal_wallet_amount(
     meal=meal,
    )

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

        if not getattr(plan, "breakfast_available", False):
            raise HTTPException(
                status_code=400,
                detail="Breakfast is not available for this plan",
            )

        # =========================================
        # BREAKFAST PRICE
        # =========================================

        # =========================================
# LOCKED BREAKFAST PRICE
# =========================================

        if (
            subscription.breakfast_price is None
            or subscription.breakfast_price <= 0
             ):
            raise HTTPException(
               status_code=400,
               detail="Breakfast price is not configured for this subscription",
            )

    # IMPORTANT:
    # Existing subscription ki locked price use hogi.
    # Current plan.breakfast_price use nahi karna hai.
        breakfast_price = float(
         subscription.breakfast_price
        )

        # =========================================
        # CALCULATE REMAINING DAYS
        # =========================================

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
        # PLAN MUST SUPPORT BREAKFAST
        # =========================================

        if not getattr(plan, "breakfast_available", False):
            raise HTTPException(
                status_code=400,
                detail="Breakfast is not available for this plan",
            )

        # =========================================
        # BREAKFAST PRICE
        # =========================================

        # =========================================
# LOCKED BREAKFAST PRICE
# =========================================

        if (
           subscription.breakfast_price is None
            or subscription.breakfast_price <= 0
           ):
            raise HTTPException(
             status_code=400,
             detail="Breakfast price is not configured for this subscription",
             )

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
        # CREATE BREAKFAST SCHEDULES
        # =========================================

        current_date = calculation_start

        while current_date <= end:

            if current_date.weekday() in delivery_weekdays:

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
                    # BREAKFAST CUTOFF
                    # =========================================

                    cutoff_at = datetime.combine(
                        current_date,
                        MEAL_CUTOFF_TIMES["breakfast"],
                        tzinfo=IST,
                    )

                    db.add(
                        SubscriptionMealSchedule(
                            subscription_id=subscription.id,
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