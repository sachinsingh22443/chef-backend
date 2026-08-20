from datetime import date, datetime, time
from uuid import UUID
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.subscription import Subscription
from app.models.subscription_meal_schedule import (
    SubscriptionMealSchedule,
)
from app.schemas.subscription_meal_schedule import (
    MealOffResponse,
    SubscriptionMealScheduleOut,
)


# =========================================================
# ROUTER
# =========================================================

router = APIRouter(
    prefix="/subscriptions",
    tags=["Subscription Meals"],
)


# =========================================================
# TIMEZONE
# =========================================================

IST = ZoneInfo("Asia/Kolkata")


# =========================================================
# VALID MEALS
# =========================================================

VALID_MEALS = {
    "breakfast",
    "lunch",
    "dinner",
}


# =========================================================
# GET ALL SUBSCRIPTION MEALS
# =========================================================

@router.get(
    "/{subscription_id}/meals",
    response_model=list[SubscriptionMealScheduleOut],
)
def get_subscription_meals(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # =====================================================
    # FIND SUBSCRIPTION
    # =====================================================

    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id == subscription_id,
            Subscription.user_id == current_user.id,
        )
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    # =====================================================
    # GET ALL MEAL SCHEDULES
    # =====================================================

    meals = (
        db.query(SubscriptionMealSchedule)
        .filter(
            SubscriptionMealSchedule.subscription_id
            == subscription.id
        )
        .order_by(
            SubscriptionMealSchedule.date,
            SubscriptionMealSchedule.meal_type,
        )
        .all()
    )

    return meals


# =========================================================
# TURN TODAY'S MEAL OFF
# =========================================================

@router.post(
    "/{subscription_id}/meals/{meal_type}/off",
    response_model=MealOffResponse,
)
def turn_meal_off(
    subscription_id: UUID,
    meal_type: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # =====================================================
    # VALIDATE MEAL TYPE
    # =====================================================

    meal_type = meal_type.lower().strip()

    if meal_type not in VALID_MEALS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid meal type. "
                "Use breakfast, lunch or dinner."
            ),
        )

    # =====================================================
    # FIND SUBSCRIPTION
    # =====================================================

    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id == subscription_id,
            Subscription.user_id == current_user.id,
        )
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    # =====================================================
    # CHECK SUBSCRIPTION STATUS
    # =====================================================

    if subscription.status != "active":
        raise HTTPException(
            status_code=400,
            detail="Subscription is not active.",
        )

    # =====================================================
    # TODAY IN INDIA
    # =====================================================

    today = datetime.now(IST).date()

    # =====================================================
    # FIND TODAY'S MEAL
    # =====================================================

    meal = (
        db.query(SubscriptionMealSchedule)
        .filter(
            SubscriptionMealSchedule.subscription_id
            == subscription.id,

            SubscriptionMealSchedule.date
            == today,

            SubscriptionMealSchedule.meal_type
            == meal_type,
        )
        .first()
    )

    # =====================================================
    # MEAL NOT SCHEDULED
    # =====================================================

    if not meal:
        raise HTTPException(
            status_code=404,
            detail=(
                f"{meal_type.capitalize()} "
                "is not scheduled for today."
            ),
        )

    # =====================================================
    # ALREADY OFF
    # =====================================================

    if meal.status == "off":
        raise HTTPException(
            status_code=400,
            detail=(
                f"{meal_type.capitalize()} "
                "is already OFF for today."
            ),
        )

    # =====================================================
    # USE SERVER-SAVED CUTOFF
    # =====================================================

    now = datetime.now(IST)

    cutoff_at = meal.cutoff_at

    # =====================================================
    # NORMALIZE CUTOFF TIMEZONE
    # =====================================================

    if cutoff_at.tzinfo is None:
        cutoff_at = cutoff_at.replace(
            tzinfo=IST
        )
    else:
        cutoff_at = cutoff_at.astimezone(IST)

    # =====================================================
    # CUTOFF CHECK
    # =====================================================

    if now >= cutoff_at:
        cutoff_display = cutoff_at.strftime(
            "%I:%M %p"
        )

        raise HTTPException(
            status_code=400,
            detail=(
                f"{meal_type.capitalize()} cutoff time "
                f"has passed. You cannot turn OFF "
                f"{meal_type} after {cutoff_display}."
            ),
        )

    # =====================================================
    # TURN OFF
    # =====================================================

    meal.status = "off"

    db.commit()
    db.refresh(meal)

    # =====================================================
    # RESPONSE
    # =====================================================

    return MealOffResponse(
        message=(
            f"{meal_type.capitalize()} "
            "has been turned OFF for today."
        ),
        subscription_id=subscription_id,
        date=today,
        meal_type=meal_type,
        status="off",
    )