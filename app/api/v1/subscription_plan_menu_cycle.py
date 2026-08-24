from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.subscription_plan import SubscriptionPlan
from app.models.subscription_plan_menu_cycle import (
    SubscriptionPlanMenuCycle,
)
from app.models.menu import Menu
from app.schemas.subscription_plan_menu_cycle import (
    SubscriptionPlanMenuCycleBulkSave,
    SubscriptionPlanMenuCycleOut,
)

router = APIRouter(
    prefix="/subscriptions/chef/plans",
    tags=["Subscription Plan Menu Cycle"],
)


VALID_MEAL_TYPES = {
    "breakfast",
    "lunch",
    "dinner",
}


def get_chef_plan_or_404(
    db: Session,
    plan_id: str,
    current_user,
) -> SubscriptionPlan:

    plan = (
        db.query(SubscriptionPlan)
        .filter(
            SubscriptionPlan.id == plan_id,
            SubscriptionPlan.chef_id == current_user.id,
        )
        .first()
    )

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found.",
        )

    return plan


# =========================================================
# GET CURRENT 30-DAY MENU MAPPING
# =========================================================

@router.get(
    "/{plan_id}/menu-cycle",
    response_model=List[SubscriptionPlanMenuCycleOut],
)
def get_subscription_plan_menu_cycle(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    get_chef_plan_or_404(
        db=db,
        plan_id=plan_id,
        current_user=current_user,
    )

    mappings = (
        db.query(SubscriptionPlanMenuCycle)
        .filter(
            SubscriptionPlanMenuCycle.plan_id == plan_id
        )
        .order_by(
            SubscriptionPlanMenuCycle.day_number.asc(),
            SubscriptionPlanMenuCycle.meal_type.asc(),
        )
        .all()
    )

    return mappings


# =========================================================
# SAVE / REPLACE COMPLETE 30-DAY MENU MAPPING
# =========================================================

@router.put(
    "/{plan_id}/menu-cycle",
    response_model=List[SubscriptionPlanMenuCycleOut],
)
def save_subscription_plan_menu_cycle(
    plan_id: str,
    payload: SubscriptionPlanMenuCycleBulkSave,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    # -----------------------------------------------------
    # 1. VERIFY PLAN OWNERSHIP
    # -----------------------------------------------------

    get_chef_plan_or_404(
        db=db,
        plan_id=plan_id,
        current_user=current_user,
    )

    # -----------------------------------------------------
    # 2. BASIC VALIDATION
    # -----------------------------------------------------

    if not payload.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one menu mapping is required.",
        )

    if len(payload.items) > 90:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 90 menu mappings are allowed.",
        )

    # -----------------------------------------------------
    # 3. CHECK DUPLICATES
    # -----------------------------------------------------

    seen = set()

    for item in payload.items:

        key = (
            item.day_number,
            item.meal_type,
        )

        if key in seen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Duplicate mapping for "
                    f"Day {item.day_number} "
                    f"{item.meal_type}."
                ),
            )

        seen.add(key)

        # Defensive validation
        if item.day_number < 1 or item.day_number > 30:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid day number: "
                    f"{item.day_number}. "
                    f"Allowed range is 1-30."
                ),
            )

        if item.meal_type not in VALID_MEAL_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid meal type: "
                    f"{item.meal_type}."
                ),
            )

    # -----------------------------------------------------
    # 4. VERIFY ALL MENUS BELONG TO THIS CHEF
    # -----------------------------------------------------

    menu_ids = {
        item.menu_id
        for item in payload.items
    }

    menus = (
        db.query(Menu)
        .filter(
            Menu.id.in_(menu_ids),
            Menu.chef_id == current_user.id,
            Menu.is_deleted.is_(False),
        )
        .all()
    )

    valid_menu_ids = {
        menu.id
        for menu in menus
    }

    invalid_menu_ids = menu_ids - valid_menu_ids

    if invalid_menu_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "One or more selected menus do not "
                "belong to this chef or have been deleted."
            ),
        )

    # -----------------------------------------------------
    # 5. TRANSACTION
    # -----------------------------------------------------

    try:

        # Replace previous mapping completely.
        (
            db.query(SubscriptionPlanMenuCycle)
            .filter(
                SubscriptionPlanMenuCycle.plan_id == plan_id
            )
            .delete(
                synchronize_session=False
            )
        )

        # -------------------------------------------------
        # 6. CREATE NEW MAPPINGS
        # -------------------------------------------------

        new_mappings = []

        for item in payload.items:

            mapping = SubscriptionPlanMenuCycle(
                plan_id=plan_id,
                day_number=item.day_number,
                meal_type=item.meal_type,
                menu_id=item.menu_id,
            )

            db.add(mapping)
            new_mappings.append(mapping)

        db.commit()

        # -------------------------------------------------
        # 7. REFRESH
        # -------------------------------------------------

        for mapping in new_mappings:
            db.refresh(mapping)

        return new_mappings

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Unable to save subscription menu cycle. "
                "Please try again."
            ),
        )