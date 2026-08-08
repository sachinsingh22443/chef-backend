from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from uuid import UUID
import uuid
from app.models.notification import Notification
from app.models.subscription_meal_schedule import SubscriptionMealSchedule
from app.services.wallet import credit_wallet, debit_wallet
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
router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])






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
    meals = set()

    for meal in (plan.meal_type or []):
        meal = meal.strip().lower()

        if meal in ("breakfast", "lunch", "dinner"):
            meals.add(meal)

    # Breakfast subscription mein separately enabled hai
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

                schedule = SubscriptionMealSchedule(
                    subscription_id=subscription.id,
                    date=current_date,
                    meal_type=meal_type,
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
            "plan_type": plan.plan_type if plan else None,
            "plan": plan.title if plan else s.plan_id,
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

    if data.breakfast_enabled:
        if not plan.breakfast_available:
            raise HTTPException(
                status_code=400,
                detail="Breakfast is not available for this plan",
            )

        breakfast_price = plan.breakfast_price or 0.0
    else:
        breakfast_price = 0.0

    # =========================================================
    # SUBSCRIPTION PRICE
    # =========================================================

    total_price = plan.price + breakfast_price

    # =========================================================
    # CREATE SUBSCRIPTION
    # =========================================================

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
        breakfast_price=(
            breakfast_price
            if data.breakfast_enabled
            else None
        ),

        # =====================================================
        # DELIVERY
        # =====================================================

        delivery_days=data.delivery_days,
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

                 "price": s.price
               })

    return result




# =========================================================
# MEAL CUTOFF TIMES
# =========================================================

IST = ZoneInfo("Asia/Kolkata")

MEAL_CUTOFF_TIMES = {
    "breakfast": time(7, 0),
    "lunch": time(10, 0),
    "dinner": time(16, 0),
}

def get_meal_wallet_amount(
    subscription: Subscription,
    plan: SubscriptionPlan,
    meal_type: str,
) -> float:
    """
    Final fixed daily meal pricing.

    Lunch     = ₹80
    Dinner    = ₹80
    Breakfast = ₹30

    Ye amount wallet credit/debit dono ke liye same rahega.
    """

    meal_prices = {
        "breakfast": 30.0,
        "lunch": 80.0,
        "dinner": 80.0,
    }

    return meal_prices.get(meal_type, 0.0)


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
            "status": meal.status,
            "cutoff_at": meal.cutoff_at,
        }
        for meal in meals
    ]


# =========================================================
# TURN MEAL OFF
# =========================================================

@router.post("/{subscription_id}/meals/{meal_type}/off")
def turn_meal_off(
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
        subscription=subscription,
        plan=plan,
        meal_type=meal_type,
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
        # COMMIT
        # -------------------------------------------------

        db.commit()
        db.refresh(meal)
        
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
def turn_meal_on(
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
        subscription=subscription,
        plan=plan,
        meal_type=meal_type,
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
        # COMMIT
        # -------------------------------------------------

        db.commit()
        db.refresh(meal)

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