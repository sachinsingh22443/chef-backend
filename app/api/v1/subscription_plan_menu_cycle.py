from typing import List
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db,
    get_current_user,
)

from app.models.subscription_plan import (
    SubscriptionPlan,
)

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


REQUIRED_DAYS = 30

REQUIRED_MEALS_PER_DAY = 3

REQUIRED_TOTAL_MAPPINGS = (
    REQUIRED_DAYS *
    REQUIRED_MEALS_PER_DAY
)


# =========================================================
# CHEF PLAN OWNERSHIP
# =========================================================

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
    response_model=List[
        SubscriptionPlanMenuCycleOut
    ],
)
def get_subscription_plan_menu_cycle(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    # -----------------------------------------------------
    # VERIFY PLAN OWNERSHIP
    # -----------------------------------------------------

    get_chef_plan_or_404(
        db=db,
        plan_id=plan_id,
        current_user=current_user,
    )

    # -----------------------------------------------------
    # GET MAPPINGS
    # -----------------------------------------------------

    mappings = (
        db.query(
            SubscriptionPlanMenuCycle
        )
        .filter(
            SubscriptionPlanMenuCycle.plan_id
            == plan_id
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
    response_model=List[
        SubscriptionPlanMenuCycleOut
    ],
)
def save_subscription_plan_menu_cycle(
    plan_id: str,
    payload: SubscriptionPlanMenuCycleBulkSave,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    # =====================================================
    # 1. VERIFY PLAN OWNERSHIP
    # =====================================================

    get_chef_plan_or_404(
        db=db,
        plan_id=plan_id,
        current_user=current_user,
    )

    # =====================================================
    # 2. BASIC VALIDATION
    # =====================================================

    if not payload.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Complete 30-day menu cycle is required."
            ),
        )

    if len(payload.items) != REQUIRED_TOTAL_MAPPINGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Complete 30-day menu cycle is required. "
                "Exactly 90 mappings are required "
                "(30 days × breakfast, lunch and dinner). "
                f"Received {len(payload.items)}."
            ),
        )

    # =====================================================
    # 3. VALIDATE DAY + MEAL TYPE + DUPLICATES
    # =====================================================

    seen = set()

    for item in payload.items:

        # -------------------------------------------------
        # DAY
        # -------------------------------------------------

        if (
            item.day_number < 1
            or item.day_number > 30
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid day number: "
                    f"{item.day_number}. "
                    "Allowed range is 1-30."
                ),
            )

        # -------------------------------------------------
        # MEAL TYPE
        # -------------------------------------------------

        if (
            item.meal_type
            not in VALID_MEAL_TYPES
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid meal type: "
                    f"{item.meal_type}. "
                    "Allowed values are "
                    "breakfast, lunch and dinner."
                ),
            )

        # -------------------------------------------------
        # DUPLICATE
        # -------------------------------------------------

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

    # =====================================================
    # 4. VERIFY EXACT 30 × 3 COMBINATION
    # =====================================================

    expected_keys = {
        (
            day_number,
            meal_type,
        )
        for day_number in range(1, 31)
        for meal_type in VALID_MEAL_TYPES
    }

    received_keys = seen

    missing_keys = (
        expected_keys -
        received_keys
    )

    extra_keys = (
        received_keys -
        expected_keys
    )

    if missing_keys:
        formatted_missing = ", ".join(
            f"Day {day} {meal}"
            for day, meal in sorted(
                missing_keys,
                key=lambda value: (
                    value[0],
                    value[1],
                ),
            )
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Incomplete subscription menu cycle. "
                f"Missing: {formatted_missing}"
            ),
        )

    if extra_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid subscription menu cycle."
            ),
        )

    # =====================================================
    # 5. VERIFY ALL MENUS BELONG TO THIS CHEF
    # =====================================================

    menu_ids = {
        item.menu_id
        for item in payload.items
    }

    if not menu_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No menu selected.",
        )

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

    invalid_menu_ids = (
        menu_ids -
        valid_menu_ids
    )

    if invalid_menu_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "One or more selected menus do not "
                "belong to this chef, are deleted, "
                "or are invalid."
            ),
        )

    # =====================================================
    # 6. TRANSACTION
    # =====================================================

    try:

        # -------------------------------------------------
        # DELETE OLD MAPPING
        # -------------------------------------------------

        (
            db.query(
                SubscriptionPlanMenuCycle
            )
            .filter(
                SubscriptionPlanMenuCycle.plan_id
                == plan_id
            )
            .delete(
                synchronize_session=False
            )
        )

        # -------------------------------------------------
        # CREATE NEW MAPPINGS
        # -------------------------------------------------

        new_mappings = []

        for item in payload.items:

            mapping = (
                SubscriptionPlanMenuCycle(
                    plan_id=plan_id,
                    day_number=item.day_number,
                    meal_type=item.meal_type,
                    menu_id=item.menu_id,
                )
            )

            db.add(mapping)

            new_mappings.append(
                mapping
            )

        # -------------------------------------------------
        # COMMIT
        # -------------------------------------------------

        db.commit()

        # -------------------------------------------------
        # REFRESH
        # -------------------------------------------------

        for mapping in new_mappings:
            db.refresh(mapping)

        # -------------------------------------------------
        # RETURN SORTED RESULT
        # -------------------------------------------------

        new_mappings.sort(
            key=lambda item: (
                item.day_number,
                item.meal_type,
            )
        )

        return new_mappings

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Unable to save subscription menu cycle. "
                "Please try again."
            ),
        )