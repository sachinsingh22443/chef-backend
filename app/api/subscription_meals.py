from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.subscription import Subscription
from app.models.subscription_meal_schedule import SubscriptionMealSchedule
from app.schemas.subscription_meal_schedule import (
    MealOffResponse,
    SubscriptionMealScheduleOut,
)


router = APIRouter(
    prefix="/subscriptions",
    tags=["Subscription Meals"],
)


VALID_MEALS = {
    "breakfast",
    "lunch",
    "dinner",
}


@router.get(
    "/{subscription_id}/meals",
    response_model=list[SubscriptionMealScheduleOut],
)
def get_subscription_meals(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
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

    meals = (
        db.query(SubscriptionMealSchedule)
        .filter(
            SubscriptionMealSchedule.subscription_id
            == subscription_id
        )
        .order_by(
            SubscriptionMealSchedule.date,
            SubscriptionMealSchedule.meal_type,
        )
        .all()
    )

    return meals


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
    # ---------------------------------------------------------
    # VALIDATE MEAL
    # ---------------------------------------------------------

    meal_type = meal_type.lower().strip()

    if meal_type not in VALID_MEALS:
        raise HTTPException(
            status_code=400,
            detail="Invalid meal type. Use breakfast, lunch or dinner.",
        )

    # ---------------------------------------------------------
    # FIND SUBSCRIPTION
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # CHECK SUBSCRIPTION STATUS
    # ---------------------------------------------------------

    if subscription.status != "active":
        raise HTTPException(
            status_code=400,
            detail="Subscription is not active.",
        )

    # ---------------------------------------------------------
    # CHECK DATE
    # ---------------------------------------------------------

    today = date.today()

    # ---------------------------------------------------------
    # FIND TODAY'S MEAL
    # ---------------------------------------------------------

    meal = (
        db.query(SubscriptionMealSchedule)
        .filter(
            SubscriptionMealSchedule.subscription_id
            == subscription_id,
            SubscriptionMealSchedule.date == today,
            SubscriptionMealSchedule.meal_type
            == meal_type,
        )
        .first()
    )

    # ---------------------------------------------------------
    # MEAL DOES NOT EXIST
    # ---------------------------------------------------------

    if not meal:
        raise HTTPException(
            status_code=404,
            detail=f"{meal_type.capitalize()} is not scheduled for today.",
        )

    # ---------------------------------------------------------
    # ALREADY OFF
    # ---------------------------------------------------------

    if meal.status == "off":
        raise HTTPException(
            status_code=400,
            detail=f"{meal_type.capitalize()} is already OFF for today.",
        )

    # ---------------------------------------------------------
    # TURN OFF
    # ---------------------------------------------------------

    meal.status = "off"

    db.commit()
    db.refresh(meal)

    return MealOffResponse(
        message=f"{meal_type.capitalize()} has been turned OFF for today.",
        subscription_id=subscription_id,
        date=today,
        meal_type=meal_type,
        status="off",
    )