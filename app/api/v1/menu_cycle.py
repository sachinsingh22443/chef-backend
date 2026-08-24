from datetime import date, datetime, timedelta, time
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.core.timezone import today_india
# =========================================================
# INDIA TIMEZONE
# =========================================================

IST = ZoneInfo("Asia/Kolkata")
from app.models.menu import Menu
from app.models.menu_cycle import MenuCycle
from app.models.menu_date_override import MenuDateOverride
from app.models.user import User
from app.schemas.menu_cycle import (
    MenuCycleBulkCreate,
    MenuCycleItemCreate,
    MenuCycleItemResponse,
    MenuDateOverrideCreate,
    MenuDateOverrideResponse,
)


router = APIRouter()

# =========================================================
# MEAL CONFIGURATION
# =========================================================

VALID_MEALS = {
    "breakfast",
    "lunch",
    "dinner",
}


MEAL_CUTOFF_TIMES = {
    "breakfast": time(8, 30),
    "lunch": time(11, 0),
    "dinner": time(18, 0),
}
# =========================================================
# HELPERS
# =========================================================


def get_verified_chef(
    db: Session,
    chef_id: UUID,
) -> User:
    """
    Return only an active + verified chef.
    """

    chef = (
        db.query(User)
        .filter(
            User.id == chef_id,
            User.role == "chef",
            User.is_active.is_(True),
            User.is_verified.is_(True),
        )
        .first()
    )

    if not chef:
        raise HTTPException(
            status_code=404,
            detail="Verified chef not found",
        )

    return chef


def validate_cycle_start_date(
    start_date: date,
    today: date,
) -> None:
    """
    A new cycle cannot start in the past.
    """

    if start_date < today:
        raise HTTPException(
            status_code=400,
            detail="Cycle start date cannot be in the past",
        )


def get_cycle_end_date(
    start_date: date,
) -> date:
    """
    A 30-day cycle includes start_date as Day 1.

    Day 1  = start_date
    Day 30 = start_date + 29 days
    """

    return start_date + timedelta(days=29)


def validate_cycle_items(
    items,
) -> None:
    """
    Validate that exactly 30 days × 3 meals
    are provided.

    Total required entries = 90.

    Day 1:
        breakfast
        lunch
        dinner

    ...

    Day 30:
        breakfast
        lunch
        dinner
    """

    # -----------------------------------------------------
    # EXACTLY 90 RECORDS
    # -----------------------------------------------------

    if len(items) != 90:
        raise HTTPException(
            status_code=400,
            detail=(
                "Exactly 90 menu entries are required "
                "(30 days × 3 meals)"
            ),
        )

    # -----------------------------------------------------
    # VALIDATE EACH ITEM
    # -----------------------------------------------------

    combinations = set()

    for item in items:

        # -------------------------------
        # DAY
        # -------------------------------

        if item.cycle_day < 1 or item.cycle_day > 30:
            raise HTTPException(
                status_code=400,
                detail=(
                    "cycle_day must be between 1 and 30"
                ),
            )

        # -------------------------------
        # MEAL TYPE
        # -------------------------------

        meal_type = (
            item.meal_type
            .lower()
            .strip()
        )

        if meal_type not in VALID_MEALS:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid meal_type. "
                    "Use breakfast, lunch or dinner."
                ),
            )

        # -------------------------------
        # DUPLICATE CHECK
        # -------------------------------

        key = (
            item.cycle_day,
            meal_type,
        )

        if key in combinations:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Duplicate entry for "
                    f"Day {item.cycle_day} "
                    f"{meal_type}"
                ),
            )

        combinations.add(key)

    # -----------------------------------------------------
    # EXPECTED 90 COMBINATIONS
    # -----------------------------------------------------

    expected_combinations = {
        (
            day,
            meal,
        )
        for day in range(1, 31)
        for meal in VALID_MEALS
    }

    # -----------------------------------------------------
    # FINAL CHECK
    # -----------------------------------------------------

    if combinations != expected_combinations:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cycle must contain breakfast, lunch "
                "and dinner for every day from 1 to 30."
            ),
        )

def validate_chef_menus(
    db: Session,
    chef_id: UUID,
    menu_ids,
):
    """
    Every menu used in a cycle must belong to the same chef.
    """

    unique_menu_ids = set(menu_ids)

    menus = (
        db.query(Menu)
        .filter(
            Menu.id.in_(unique_menu_ids),
            Menu.chef_id == chef_id,
            Menu.is_deleted.is_(False),
        )
        .all()
    )

    menu_map = {
        menu.id: menu
        for menu in menus
    }

    missing = [
        str(menu_id)
        for menu_id in unique_menu_ids
        if menu_id not in menu_map
    ]

    if missing:
        raise HTTPException(
            status_code=404,
            detail={
                "message": (
                    "One or more menus were not found "
                    "or do not belong to this chef"
                ),
                "menu_ids": missing,
            },
        )

    return menu_map


def check_cycle_overlap(
    db: Session,
    chef_id: UUID,
    start_date: date,
    exclude_cycle_start: date | None = None,
) -> None:
    """
    Prevent overlapping 30-day cycles for the same chef.

    Cycle A:
        start -> start + 29

    Cycle B:
        start -> start + 29

    They must not overlap.
    """

    end_date = get_cycle_end_date(start_date)

    query = (
        db.query(MenuCycle.cycle_start_date)
        .filter(
            MenuCycle.chef_id == chef_id,
        )
        .distinct()
    )

    existing_starts = [
        row[0]
        for row in query.all()
    ]

    for existing_start in existing_starts:

        if (
            exclude_cycle_start is not None
            and existing_start == exclude_cycle_start
        ):
            continue

        existing_end = get_cycle_end_date(
            existing_start
        )

        overlaps = (
            start_date <= existing_end
            and end_date >= existing_start
        )

        if overlaps:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Cycle overlaps with existing cycle "
                    f"starting on {existing_start}"
                ),
            )


# =========================================================
# CYCLE RESOLUTION
# =========================================================


def resolve_cycle_and_day(
    db: Session,
    chef_id: UUID,
    target_date: date,
):
    """
    Resolve which cycle template should be used for target_date.

    IMPORTANT BUSINESS RULE:

    1. If a real configured cycle contains target_date:
           use that cycle.

    2. If target_date is after the latest configured cycle:
           automatically repeat the latest completed cycle
           every 30 days.

    3. If there is a future cycle configured:
           that future cycle will automatically take priority
           when its date range starts.

    Example:

        Cycle 1
        19 Aug -> 17 Sep

        No Cycle 2

        18 Sep -> Cycle 1 Day 1
        19 Sep -> Cycle 1 Day 2
        ...
        17 Oct -> Cycle 1 Day 30
        18 Oct -> Cycle 1 Day 1 again

    If Cycle 2 exists:

        Cycle 1
        19 Aug -> 17 Sep

        Cycle 2
        18 Sep -> 17 Oct

        18 Sep -> Cycle 2 Day 1
        19 Sep -> Cycle 2 Day 2
        etc.
    """

    # -----------------------------------------------------
    # Get all cycles for this chef
    # -----------------------------------------------------

    cycles = (
        db.query(MenuCycle)
        .filter(
            MenuCycle.chef_id == chef_id,
        )
        .order_by(
            MenuCycle.cycle_start_date.asc()
        )
        .all()
    )

    if not cycles:
        return None, None

    # -----------------------------------------------------
    # 1. Exact configured cycle
    #
    # If target date is inside an actual stored cycle,
    # always use that cycle.
    # -----------------------------------------------------

    for cycle in cycles:

        cycle_start = cycle.cycle_start_date
        cycle_end = get_cycle_end_date(
            cycle_start
        )

        if (
            cycle_start
            <= target_date
            <= cycle_end
        ):
            cycle_day = (
                target_date - cycle_start
            ).days + 1

            return cycle, cycle_day

    # -----------------------------------------------------
    # 2. Target date before first cycle
    #
    # No menu should be shown before the chef's first
    # configured cycle.
    # -----------------------------------------------------

    first_cycle = cycles[0]

    if target_date < first_cycle.cycle_start_date:
        return None, None

    # -----------------------------------------------------
    # 3. No exact cycle.
    #
    # Find the latest cycle whose start date is before
    # target_date.
    #
    # This becomes our repeating template.
    # -----------------------------------------------------

    previous_cycles = [
        cycle
        for cycle in cycles
        if cycle.cycle_start_date <= target_date
    ]

    if not previous_cycles:
        return None, None

    latest_cycle = max(
        previous_cycles,
        key=lambda cycle: cycle.cycle_start_date,
    )

    # -----------------------------------------------------
    # 4. Automatically repeat latest cycle every 30 days.
    # -----------------------------------------------------

    days_since_cycle_start = (
        target_date
        - latest_cycle.cycle_start_date
    ).days

    repeated_cycle_day = (
        days_since_cycle_start % 30
    ) + 1

    return latest_cycle, repeated_cycle_day


def get_cycle_for_date(
    db: Session,
    chef_id: UUID,
    target_date: date,
):
    """
    Backward-compatible helper.

    Returns the cycle template that should be used
    for target_date.
    """

    cycle, _ = resolve_cycle_and_day(
        db=db,
        chef_id=chef_id,
        target_date=target_date,
    )

    return cycle


def get_cycle_day(
    cycle_start_date: date,
    target_date: date,
) -> int:
    """
    Calculate Day 1-30 for a normal cycle.

    Used only where the date belongs directly to the
    stored cycle range.
    """

    difference = (
        target_date - cycle_start_date
    ).days

    return difference + 1


# =========================================================
# MENU RESOLUTION
# =========================================================


def get_menu_for_day(
    db: Session,
    chef_id: UUID,
    target_date: date,
    meal_type: str,
):
    """
    Resolve final menu for a specific date + meal.

    Priority:

    1. Date override
    2. Explicit configured cycle
    3. Automatic repeating cycle
    """

    # -----------------------------------------------------
    # NORMALIZE MEAL
    # -----------------------------------------------------

    meal_type = meal_type.lower().strip()

    if meal_type not in VALID_MEALS:
        return None, None

    # -----------------------------------------------------
    # 1. DATE OVERRIDE
    #
    # NOTE:
    # Current MenuDateOverride model is date-only,
    # so existing override applies to the date.
    # -----------------------------------------------------

    override = (
        db.query(MenuDateOverride)
        .filter(
            MenuDateOverride.chef_id == chef_id,
            MenuDateOverride.menu_date == target_date,
        )
        .first()
    )

    if override:

        menu = (
            db.query(Menu)
            .filter(
                Menu.id == override.menu_id,
                Menu.chef_id == chef_id,
                Menu.is_deleted.is_(False),
            )
            .first()
        )

        if menu:
            return menu, "date_override"

    # -----------------------------------------------------
    # 2. RESOLVE CYCLE + DAY
    # -----------------------------------------------------

    cycle, cycle_day = resolve_cycle_and_day(
        db=db,
        chef_id=chef_id,
        target_date=target_date,
    )

    if not cycle:
        return None, None

    # -----------------------------------------------------
    # 3. FIND MENU FOR DAY + MEAL
    # -----------------------------------------------------

    cycle_item = (
        db.query(MenuCycle)
        .filter(
            MenuCycle.chef_id == chef_id,
            MenuCycle.cycle_start_date
            == cycle.cycle_start_date,
            MenuCycle.cycle_day == cycle_day,
            MenuCycle.meal_type == meal_type,
        )
        .first()
    )

    if not cycle_item:
        return None, None

    # -----------------------------------------------------
    # 4. GET ACTUAL MENU
    # -----------------------------------------------------

    menu = (
        db.query(Menu)
        .filter(
            Menu.id == cycle_item.menu_id,
            Menu.chef_id == chef_id,
            Menu.is_deleted.is_(False),
        )
        .first()
    )

    if not menu:
        return None, None

    # -----------------------------------------------------
    # DETERMINE SOURCE
    # -----------------------------------------------------

    actual_cycle_end = get_cycle_end_date(
        cycle.cycle_start_date
    )

    if (
        cycle.cycle_start_date
        <= target_date
        <= actual_cycle_end
    ):
        source = "cycle"
    else:
        source = "cycle_repeat"

    return menu, source


def serialize_menu(menu: Menu):
    """
    Convert Menu model into customer-safe response.
    """

    if not menu:
        return None

    return {
        "id": str(menu.id),
        "name": menu.name,
        "description": menu.description,
        "price": menu.price,
        "prep_time": menu.prep_time,
        "quantity": menu.quantity,
        "category": menu.category,
        "food_type": menu.food_type,
        "calories": menu.calories,
        "protein": menu.protein,
        "carbs": menu.carbs,
        "fats": menu.fats,
        "ingredients": menu.ingredients or [],
        "image_urls": menu.image_urls or [],
        "is_available": menu.is_available,
    }


# =========================================================
# CHEF
# CREATE NEW 30-DAY CYCLE
# =========================================================



@router.post(
    "/",
)
def create_menu_cycle(
    payload: MenuCycleBulkCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["chef"])),
):
    today = today_india()

    cycle_start_date = payload.cycle_start_date

    # -----------------------------------------------------
    # Chef must be active + verified
    # -----------------------------------------------------

    if not current_user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Chef account is inactive",
        )

    if not current_user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="Chef account is not verified",
        )

    # -----------------------------------------------------
    # Validate start date
    # -----------------------------------------------------

    validate_cycle_start_date(
        cycle_start_date,
        today,
    )

    # -----------------------------------------------------
    # Validate exactly 30 days
    # -----------------------------------------------------

    validate_cycle_items(
        payload.items
    )

    # -----------------------------------------------------
    # Validate menus belong to chef
    # -----------------------------------------------------

    menu_ids = [
        item.menu_id
        for item in payload.items
    ]

    validate_chef_menus(
        db,
        current_user.id,
        menu_ids,
    )

    # -----------------------------------------------------
    # Prevent overlapping cycles
    # -----------------------------------------------------

    check_cycle_overlap(
        db,
        current_user.id,
        cycle_start_date,
    )

    # -----------------------------------------------------
    # Create all 30 records in one transaction
    # -----------------------------------------------------

    try:

        cycle_rows = [
          MenuCycle(
            chef_id=current_user.id,
            menu_id=item.menu_id,
            cycle_day=item.cycle_day,
            cycle_start_date=cycle_start_date,
            meal_type=item.meal_type,
          )
          for item in payload.items
        ]

        db.add_all(cycle_rows)

        db.commit()

        for row in cycle_rows:
            db.refresh(row)

        return {
            "success": True,
            "message": "30-day menu cycle created successfully",
            "cycle_start_date": cycle_start_date,
            "cycle_end_date": get_cycle_end_date(
                cycle_start_date
            ),
            "days": [
                MenuCycleItemResponse.model_validate(row)
                for row in sorted(
                    cycle_rows,
                    key=lambda x: x.cycle_day,
                )
            ],
        }

    except Exception:
        db.rollback()
        raise


# =========================================================
# CHEF
# GET ALL CYCLES
# =========================================================


@router.get(
    "/",
)
def get_menu_cycles(
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["chef"])),
):
    cycles = (
        db.query(MenuCycle)
        .filter(
            MenuCycle.chef_id == current_user.id,
        )
        .order_by(
            MenuCycle.cycle_start_date.desc(),
            MenuCycle.cycle_day.asc(),
        )
        .all()
    )

    grouped = {}

    for cycle in cycles:
        key = cycle.cycle_start_date.isoformat()

        if key not in grouped:
            grouped[key] = {
                "cycle_start_date": cycle.cycle_start_date,
                "cycle_end_date": get_cycle_end_date(
                    cycle.cycle_start_date
                ),
                "items": [],
            }

        grouped[key]["items"].append(
            MenuCycleItemResponse.model_validate(cycle)
        )

    return {
        "success": True,
        "cycles": list(grouped.values()),
    }

# =========================================================
# CHEF
# GET ONE CYCLE
# =========================================================


@router.get(
    "/cycle/{cycle_start_date}",
)
def get_single_cycle(
    cycle_start_date: date,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["chef"])),
):
    cycles = (
        db.query(MenuCycle)
        .filter(
            MenuCycle.chef_id == current_user.id,
            MenuCycle.cycle_start_date == cycle_start_date,
        )
        .order_by(
            MenuCycle.cycle_day.asc()
        )
        .all()
    )

    if not cycles:
        raise HTTPException(
            status_code=404,
            detail="Menu cycle not found",
        )

    return {
        "success": True,
        "cycle_start_date": cycle_start_date,
        "cycle_end_date": get_cycle_end_date(
            cycle_start_date
        ),
        "days": [
            MenuCycleItemResponse.model_validate(
                cycle
            )
            for cycle in cycles
        ],
    }


# =========================================================
# CHEF
# UPDATE ONE DAY OF A FUTURE CYCLE
# =========================================================
# =========================================================
# CHEF
# UPDATE COMPLETE FUTURE 30-DAY CYCLE
# =========================================================

@router.put(
    "/cycle/{cycle_start_date}",
)
def update_menu_cycle(
    cycle_start_date: date,
    payload: MenuCycleBulkCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["chef"])),
):
    today = today_india()

    # -----------------------------------------------------
    # CHEF VALIDATION
    # -----------------------------------------------------

    if not current_user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Chef account is inactive",
        )

    if not current_user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="Chef account is not verified",
        )

    # -----------------------------------------------------
    # ONLY FUTURE CYCLE CAN BE UPDATED
    # -----------------------------------------------------

    if cycle_start_date <= today:
        raise HTTPException(
            status_code=409,
            detail=(
                "Started or completed cycles cannot be modified."
            ),
        )

    # -----------------------------------------------------
    # BODY START DATE MUST MATCH URL
    # -----------------------------------------------------

    if payload.cycle_start_date != cycle_start_date:
        raise HTTPException(
            status_code=400,
            detail=(
                "cycle_start_date in URL and body must match"
            ),
        )

    # -----------------------------------------------------
    # VALIDATE 90 ITEMS
    # -----------------------------------------------------

    validate_cycle_items(payload.items)

    # -----------------------------------------------------
    # VERIFY ALL MENUS BELONG TO CHEF
    # -----------------------------------------------------

    menu_ids = [
        item.menu_id
        for item in payload.items
    ]

    validate_chef_menus(
        db=db,
        chef_id=current_user.id,
        menu_ids=menu_ids,
    )

    # -----------------------------------------------------
    # FIND EXISTING CYCLE
    # -----------------------------------------------------

    existing_rows = (
        db.query(MenuCycle)
        .filter(
            MenuCycle.chef_id == current_user.id,
            MenuCycle.cycle_start_date == cycle_start_date,
        )
        .all()
    )

    if not existing_rows:
        raise HTTPException(
            status_code=404,
            detail="Menu cycle not found",
        )

    # -----------------------------------------------------
    # CREATE LOOKUP
    # -----------------------------------------------------

    existing_map = {
        (
            row.cycle_day,
            row.meal_type.lower().strip(),
        ): row
        for row in existing_rows
    }

    payload_map = {
        (
            item.cycle_day,
            item.meal_type.lower().strip(),
        ): item
        for item in payload.items
    }

    # -----------------------------------------------------
    # UPDATE EXISTING 90 RECORDS
    #
    # IMPORTANT:
    # We DO NOT delete/recreate rows.
    #
    # This keeps the same MenuCycle records and only
    # changes their menu_id / meal_type data.
    #
    # Orders and carts are NOT touched.
    # -----------------------------------------------------

    try:
        for key, row in existing_map.items():

            item = payload_map.get(key)

            if not item:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Missing cycle entry for "
                        f"Day {row.cycle_day} "
                        f"{row.meal_type}"
                    ),
                )

            row.menu_id = item.menu_id
            row.meal_type = (
                item.meal_type.lower().strip()
            )

        # -------------------------------------------------
        # SAFETY CHECK
        # -------------------------------------------------

        if len(existing_map) != 90:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Existing cycle is incomplete. "
                    "Expected 90 menu entries."
                ),
            )

        db.commit()

        # -------------------------------------------------
        # REFRESH
        # -------------------------------------------------

        for row in existing_rows:
            db.refresh(row)

        return {
            "success": True,
            "message": (
                "Future 30-day menu cycle "
                "updated successfully"
            ),
            "cycle_start_date": cycle_start_date,
            "cycle_end_date": get_cycle_end_date(
                cycle_start_date
            ),
            "days": [
                MenuCycleItemResponse.model_validate(row)
                for row in sorted(
                    existing_rows,
                    key=lambda x: (
                        x.cycle_day,
                        x.meal_type,
                    ),
                )
            ],
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise
    
    
    
# =========================================================
# CHEF
# DELETE COMPLETE FUTURE 30-DAY CYCLE
# =========================================================

@router.delete(
    "/cycle/{cycle_start_date}",
)
def delete_menu_cycle(
    cycle_start_date: date,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["chef"])),
):
    today = today_india()

    # -----------------------------------------------------
    # CHEF VALIDATION
    # -----------------------------------------------------

    if not current_user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Chef account is inactive",
        )

    if not current_user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="Chef account is not verified",
        )

    # -----------------------------------------------------
    # NEVER DELETE STARTED / CURRENT / PAST CYCLE
    # -----------------------------------------------------

    if cycle_start_date <= today:
        raise HTTPException(
            status_code=409,
            detail=(
                "Started or completed cycles cannot be deleted."
            ),
        )

    # -----------------------------------------------------
    # FIND CYCLE
    # -----------------------------------------------------

    cycle_rows = (
        db.query(MenuCycle)
        .filter(
            MenuCycle.chef_id == current_user.id,
            MenuCycle.cycle_start_date == cycle_start_date,
        )
        .all()
    )

    if not cycle_rows:
        raise HTTPException(
            status_code=404,
            detail="Menu cycle not found",
        )

    # -----------------------------------------------------
    # DELETE ONLY MENU CYCLE RECORDS
    #
    # IMPORTANT:
    # Orders are NOT deleted.
    # Cart is NOT deleted.
    # Menu records are NOT deleted.
    # -----------------------------------------------------

    try:
        deleted_count = len(cycle_rows)

        for row in cycle_rows:
            db.delete(row)

        db.commit()

        return {
            "success": True,
            "mesdefsage": (
                "Future menu cycle deleted successfully"
            ),
            "cycle_start_date": cycle_start_date,
            "deleted_entries": deleted_count,
        }

    except Exception:
        db.rollback()
        raise

@router.put(
    "/cycle/{cycle_start_date}/day/{cycle_day}/{meal_type}",
    response_model=MenuCycleItemResponse,
)
def update_cycle_day(
    cycle_start_date: date,
    cycle_day: int,
    meal_type: str,
    payload: MenuCycleItemCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["chef"])),
):
    today = today_india()

    if cycle_day < 1 or cycle_day > 30:
        raise HTTPException(
            status_code=400,
            detail="cycle_day must be between 1 and 30",
        )

    if payload.cycle_day != cycle_day:
        raise HTTPException(
            status_code=400,
            detail="cycle_day in URL and body must match",
        )

    # -----------------------------------------------------
    # Never modify a cycle that has already started.
    # -----------------------------------------------------

    if cycle_start_date <= today:
        raise HTTPException(
            status_code=409,
            detail=(
                "Started or completed cycles cannot be modified. "
                "Use a date override for a future date."
            ),
        )

    # -----------------------------------------------------
    # Verify menu ownership
    # -----------------------------------------------------

    menu = (
        db.query(Menu)
        .filter(
            Menu.id == payload.menu_id,
            Menu.chef_id == current_user.id,
            Menu.is_deleted.is_(False),
        )
        .first()
    )

    if not menu:
        raise HTTPException(
            status_code=404,
            detail="Menu not found or does not belong to this chef",
        )

    # -----------------------------------------------------
    # Find cycle day
    # -----------------------------------------------------

    cycle = (
      db.query(MenuCycle)
      .filter(
        MenuCycle.chef_id == current_user.id,
        MenuCycle.cycle_start_date == cycle_start_date,
        MenuCycle.cycle_day == cycle_day,
        MenuCycle.meal_type == meal_type,
        )
        .first()
    )

    if not cycle:
        raise HTTPException(
            status_code=404,
            detail="Cycle day not found",
        )

    cycle.menu_id = payload.menu_id

    try:
        db.commit()
        db.refresh(cycle)

        return cycle

    except Exception:
        db.rollback()
        raise


# =========================================================
# CHEF
# CREATE / UPDATE DATE OVERRIDE
# =========================================================


@router.post(
    "/override",
    response_model=MenuDateOverrideResponse,
)
def create_date_override(
    payload: MenuDateOverrideCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["chef"])),
):
    today = today_india()

    # -----------------------------------------------------
    # Override cannot be for past date
    # -----------------------------------------------------

    if payload.menu_date < today:
        raise HTTPException(
            status_code=400,
            detail="Past dates cannot be overridden",
        )

    # -----------------------------------------------------
    # Verify menu ownership
    # -----------------------------------------------------

    menu = (
        db.query(Menu)
        .filter(
            Menu.id == payload.menu_id,
            Menu.chef_id == current_user.id,
            Menu.is_deleted.is_(False),
        )
        .first()
    )

    if not menu:
        raise HTTPException(
            status_code=404,
            detail="Menu not found or does not belong to this chef",
        )

    # -----------------------------------------------------
    # Check existing override
    # -----------------------------------------------------

    override = (
        db.query(MenuDateOverride)
        .filter(
            MenuDateOverride.chef_id == current_user.id,
            MenuDateOverride.menu_date == payload.menu_date,
        )
        .first()
    )

    try:

        if override:

            override.menu_id = payload.menu_id

        else:

            override = MenuDateOverride(
                chef_id=current_user.id,
                menu_id=payload.menu_id,
                menu_date=payload.menu_date,
            )

            db.add(override)

        db.commit()
        db.refresh(override)

        return override

    except Exception:
        db.rollback()
        raise


# =========================================================
# CHEF
# GET DATE OVERRIDES
# =========================================================


@router.get(
    "/overrides",
    response_model=list[MenuDateOverrideResponse],
)
def get_date_overrides(
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["chef"])),
):
    overrides = (
        db.query(MenuDateOverride)
        .filter(
            MenuDateOverride.chef_id == current_user.id,
        )
        .order_by(
            MenuDateOverride.menu_date.asc()
        )
        .all()
    )

    return overrides


# =========================================================
# CHEF
# DELETE FUTURE DATE OVERRIDE
# =========================================================


@router.delete(
    "/override/{override_id}",
)
def delete_date_override(
    override_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["chef"])),
):
    today = today_india()

    override = (
        db.query(MenuDateOverride)
        .filter(
            MenuDateOverride.id == override_id,
            MenuDateOverride.chef_id == current_user.id,
        )
        .first()
    )

    if not override:
        raise HTTPException(
            status_code=404,
            detail="Date override not found",
        )

    if override.menu_date < today:
        raise HTTPException(
            status_code=409,
            detail="Past overrides cannot be modified",
        )

    try:

        db.delete(override)
        db.commit()

        return {
            "success": True,
            "message": "Date override removed",
        }

    except Exception:
        db.rollback()
        raise


# =========================================================
# CUSTOMER
# GET NEXT 7 DAYS FOR VERIFIED CHEF
# =========================================================


# =========================================================
# CUSTOMER
# GET NEXT 7 DAYS FOR VERIFIED CHEF
# =========================================================

@router.get(
    "/customer/{chef_id}",
)
def get_customer_7_day_menu(
    chef_id: UUID,
    db: Session = Depends(get_db),
):
    today = today_india()
    now = datetime.now(IST)

    # -----------------------------------------------------
    # ONLY VERIFIED + ACTIVE CHEF
    # -----------------------------------------------------

    get_verified_chef(
        db,
        chef_id,
    )

    # -----------------------------------------------------
    # BUILD NEXT 7 DAYS
    # -----------------------------------------------------

    days = []

    for offset in range(7):

        target_date = (
            today + timedelta(days=offset)
        )

        cycle, cycle_day = resolve_cycle_and_day(
            db=db,
            chef_id=chef_id,
            target_date=target_date,
        )

        meals = []

        # -------------------------------------------------
        # BREAKFAST / LUNCH / DINNER
        # -------------------------------------------------

        for meal_type in (
            "breakfast",
            "lunch",
            "dinner",
        ):

            # ---------------------------------------------
            # GET MENU FOR DATE + MEAL
            # ---------------------------------------------

            menu, source = get_menu_for_day(
                db=db,
                chef_id=chef_id,
                target_date=target_date,
                meal_type=meal_type,
            )

            # ---------------------------------------------
            # CUTOFF TIME
            # ---------------------------------------------

            cutoff_at = datetime.combine(
                target_date,
                MEAL_CUTOFF_TIMES[meal_type],
            ).replace(
                tzinfo=IST
            )

            # ---------------------------------------------
            # ORDER AVAILABILITY
            # ---------------------------------------------

            can_order = (
                target_date == today
                and now < cutoff_at
                and menu is not None
                and menu.is_available is True
                and menu.quantity is not None
                and menu.quantity > 0
            )

            # ---------------------------------------------
            # MEAL STATUS
            # ---------------------------------------------

            if target_date < today:

                meal_status = "past"

            elif target_date > today:

                meal_status = "upcoming"

            elif now >= cutoff_at:

                meal_status = "cutoff_passed"

            elif menu is None:

                meal_status = "unavailable"

            elif menu.is_available is not True:

                meal_status = "out_of_stock"

            elif menu.quantity is None or menu.quantity <= 0:

                meal_status = "out_of_stock"

            else:

                meal_status = "available"

            # ---------------------------------------------
            # MEAL RESPONSE
            # ---------------------------------------------

            meals.append(
                {
                    "meal_type": meal_type,

                    "cutoff_time": (
                        MEAL_CUTOFF_TIMES[
                            meal_type
                        ].strftime("%I:%M %p")
                    ),

                    "meal_status": meal_status,

                    "can_order": can_order,

                    "menu": serialize_menu(menu),

                    "source": source,
                }
            )

        # -------------------------------------------------
        # DAY RESPONSE
        # -------------------------------------------------

        days.append(
            {
                "date": target_date,

                "cycle_day": cycle_day,

                "is_today": (
                    target_date == today
                ),

                "is_past": (
                    target_date < today
                ),

                "is_upcoming": (
                    target_date > today
                ),

                "meals": meals,
            }
        )

    # -----------------------------------------------------
    # FINAL RESPONSE
    # -----------------------------------------------------

    return {
        "success": True,

        "chef_id": chef_id,

        "start_date": today,

        "end_date": (
            today + timedelta(days=6)
        ),

        "days": days,
    }
# =========================================================
# CUSTOMER
# GET MENU DETAILS FOR A SPECIFIC DATE
# =========================================================


# =========================================================
# CUSTOMER
# GET MENU DETAILS FOR A SPECIFIC DATE + MEAL
# =========================================================

@router.get(
    "/customer/{chef_id}/date/{menu_date}/{meal_type}",
)
def get_customer_menu_details(
    chef_id: UUID,
    menu_date: date,
    meal_type: str,
    db: Session = Depends(get_db),
):
    today = today_india()

    # -----------------------------------------------------
    # NORMALIZE MEAL TYPE
    # -----------------------------------------------------

    meal_type = meal_type.lower().strip()

    if meal_type not in VALID_MEALS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid meal type. "
                "Use breakfast, lunch or dinner."
            ),
        )

    now = datetime.now(IST)

    # -----------------------------------------------------
    # ONLY VERIFIED + ACTIVE CHEF
    # -----------------------------------------------------

    get_verified_chef(
        db,
        chef_id,
    )

    # -----------------------------------------------------
    # PAST DATE NOT ALLOWED
    # -----------------------------------------------------

    if menu_date < today:
        raise HTTPException(
            status_code=400,
            detail=(
                "Past menu dates are not available "
                "for ordering"
            ),
        )

    # -----------------------------------------------------
    # ONLY NEXT 7 DAYS
    # -----------------------------------------------------

    if menu_date > today + timedelta(days=6):
        raise HTTPException(
            status_code=400,
            detail=(
                "Menu date must be within "
                "the next 7 days"
            ),
        )

    # -----------------------------------------------------
    # GET MENU
    # -----------------------------------------------------

    menu, source = get_menu_for_day(
        db=db,
        chef_id=chef_id,
        target_date=menu_date,
        meal_type=meal_type,
    )

    # -----------------------------------------------------
    # NO MENU
    # -----------------------------------------------------

    if not menu:
        raise HTTPException(
            status_code=404,
            detail="No menu is scheduled for this date",
        )

    # -----------------------------------------------------
    # RESOLVE CYCLE
    # -----------------------------------------------------

    cycle, cycle_day = resolve_cycle_and_day(
        db=db,
        chef_id=chef_id,
        target_date=menu_date,
    )

    # -----------------------------------------------------
    # CUTOFF TIME
    # -----------------------------------------------------

    cutoff_at = datetime.combine(
        menu_date,
        MEAL_CUTOFF_TIMES[meal_type],
    ).replace(
        tzinfo=IST
    )

    # -----------------------------------------------------
    # ORDER AVAILABILITY
    # -----------------------------------------------------

    can_order = (
        menu_date == today
        and now < cutoff_at
        and menu.is_available is True
        and menu.quantity is not None
        and menu.quantity > 0
    )

    # -----------------------------------------------------
    # MEAL STATUS
    # -----------------------------------------------------

    if menu_date < today:

        meal_status = "past"

    elif menu_date > today:

        meal_status = "upcoming"

    elif now >= cutoff_at:

        meal_status = "cutoff_passed"

    elif menu.is_available is not True:

        meal_status = "out_of_stock"

    elif menu.quantity is None or menu.quantity <= 0:

        meal_status = "out_of_stock"

    else:

        meal_status = "available"

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return {
        "success": True,

        "chef_id": chef_id,

        "date": menu_date,

        "cycle_day": cycle_day,

        "meal_type": meal_type,

        "cutoff_time": (
            MEAL_CUTOFF_TIMES[
                meal_type
            ].strftime("%I:%M %p")
        ),

        "meal_status": meal_status,

        "is_today": (
            menu_date == today
        ),

        "is_upcoming": (
            menu_date > today
        ),

        "can_order": can_order,

        "source": source,

        "menu": serialize_menu(menu),
    }