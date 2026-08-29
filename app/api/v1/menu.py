from app.models.user import ChefProfile, User
from app.core.cache import get_cache, set_cache
from app.core.cache import delete_cache
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, Form, File
from sqlalchemy.orm import Session, selectinload
from typing import Optional, List
import cloudinary.uploader
from app.models.user import User
from uuid import UUID
from app.models.menu import Menu
from app.models.order_item import OrderItem
from app.api.deps import get_db, get_current_user
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.api.deps import get_db, get_current_user, require_role

from app.schemas.menu_cycle import (
    MenuCycleBulkCreate,
    MenuCycleItemResponse,
    MenuCycleResponse,
    MenuDateOverrideCreate,
    MenuDateOverrideResponse,
)

from sqlalchemy import func, and_

from app.models.menu_cycle import MenuCycle
from app.models.menu_date_override import MenuDateOverride

router = APIRouter()

INDIA_TZ = ZoneInfo("Asia/Kolkata")
MENU_CYCLE_DAYS = 30
CUSTOMER_MENU_DAYS = 7

def get_cycle_menu_for_date(
    db: Session,
    chef_id,
    target_date: date,
    meal_type: str,
):
    """
    Resolve menu for a specific date + meal type.

    Priority:
    1. Date override
    2. Latest applicable 30-day cycle
    """

    meal_type = meal_type.lower().strip()

    allowed_meals = {"breakfast", "lunch", "dinner"}

    if meal_type not in allowed_meals:
        return None

    # =====================================================
    # 1. DATE OVERRIDE
    # =====================================================

    # IMPORTANT:
    # Current MenuDateOverride model is date-only.
    # Therefore we keep override behavior unchanged.
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
                Menu.is_deleted == False,
                Menu.is_available == True,
            )
            .first()
        )

        if menu:
            return menu

    # =====================================================
    # 2. FIND LATEST APPLICABLE CYCLE
    # =====================================================

    cycle_start_result = (
        db.query(MenuCycle.cycle_start_date)
        .filter(
            MenuCycle.chef_id == chef_id,
            MenuCycle.cycle_start_date <= target_date,
        )
        .order_by(
            MenuCycle.cycle_start_date.desc()
        )
        .first()
    )

    if not cycle_start_result:
        return None

    cycle_start_date = cycle_start_result[0]

    # =====================================================
    # 3. CALCULATE CYCLE DAY
    # =====================================================

    days_elapsed = (
        target_date - cycle_start_date
    ).days

    cycle_day = (
        days_elapsed % MENU_CYCLE_DAYS
    ) + 1

    # =====================================================
    # 4. EXACT CYCLE + DAY + MEAL TYPE
    # =====================================================

    cycle = (
        db.query(MenuCycle)
        .filter(
            MenuCycle.chef_id == chef_id,
            MenuCycle.cycle_start_date == cycle_start_date,
            MenuCycle.cycle_day == cycle_day,
            MenuCycle.meal_type == meal_type,
        )
        .first()
    )

    if not cycle:
        return None

    # =====================================================
    # 5. FETCH MENU
    # =====================================================

    menu = (
        db.query(Menu)
        .filter(
            Menu.id == cycle.menu_id,
            Menu.chef_id == chef_id,
            Menu.is_deleted == False,
            Menu.is_available == True,
        )
        .first()
    )

    return menu

# ✅ CREATE MENU
@router.post("/")
async def create_menu(
    name: str = Form(...),
    description: str = Form(None),
    price: float = Form(...),
    prep_time: int = Form(None),
    quantity: int = Form(1),
    category: str = Form(None),
    food_type: str = Form(None),

    calories: int = Form(None),
    protein: float = Form(None),
    carbs: float = Form(None),
    fats: float = Form(None),

    ingredients: str = Form(None),
    images: List[UploadFile] = File(None),

    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    image_urls = []

    # 🔥 FIXED CLOUDINARY UPLOAD
    if images:
        for img in images:
            try:
                contents = await img.read()   # 🔥 IMPORTANT FIX

                result = cloudinary.uploader.upload(
                   contents,
                   folder="menu_items",
                   resource_type="image",
                   quality="auto",
                   fetch_format="auto",
                   transformation=[
                    {
                     "width": 800,
                     "height": 800,
                     "crop": "limit"
                    }
                    ]
                )

                image_urls.append(result["secure_url"])

            except Exception as e:
                print("❌ CLOUDINARY ERROR:", str(e))
                raise HTTPException(status_code=500, detail=f"Image upload failed: {str(e)}")

    # 🔥 INGREDIENTS SAFE FIX
    ingredient_list = (
        ingredients.split(",") if ingredients and ingredients.strip() else []
    )

    menu = Menu(
        chef_id=user.id,
        name=name,
        description=description,
        price=price,
        prep_time=prep_time,
        quantity=quantity,
        category=category,
        food_type=food_type,
        calories=calories,
        protein=protein,
        carbs=carbs,
        fats=fats,
        ingredients=ingredient_list,
        image_urls=image_urls
    )

    db.add(menu)
    db.commit()
    delete_cache(f"menu:{user.id}")
    current_date = datetime.now(INDIA_TZ).date()
    delete_cache(
     f"chef:7day-menu:{user.id}:{current_date.isoformat()}"
    )
    db.refresh(menu)

    return menu


# ✅ UPDATE MENU
@router.put("/{menu_id}")
async def update_menu(
    menu_id: str,
    name: str = Form(None),
    description: str = Form(None),
    price: float = Form(None),
    is_available: bool = Form(None),

    prep_time: int = Form(None),
    quantity: int = Form(None),
    category: str = Form(None),
    food_type: str = Form(None),

    calories: int = Form(None),
    protein: float = Form(None),
    carbs: float = Form(None),
    fats: float = Form(None),

    ingredients: str = Form(None),
    images: List[UploadFile] = File(None),

    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    menu = db.query(Menu).filter(Menu.id == menu_id).first()

    if not menu:
        raise HTTPException(status_code=404, detail="Menu not found")

    if menu.chef_id != user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    # 🔹 update fields
    if name:
        menu.name = name
    if description:
        menu.description = description
    if price:
        menu.price = price
    if prep_time:
        menu.prep_time = prep_time
    if quantity:
        menu.quantity = quantity
    if category:
        menu.category = category
    if food_type:
        menu.food_type = food_type
    if is_available is not None:
        menu.is_available = is_available
    if calories:
        menu.calories = calories
    if protein:
        menu.protein = protein
    if carbs:
        menu.carbs = carbs
    if fats:
        menu.fats = fats

    if ingredients and ingredients.strip():
        menu.ingredients = ingredients.split(",")

    # 🔥 FIXED IMAGE UPDATE
    if images:
        image_urls = []

        for img in images:
            try:
                contents = await img.read()

                result = cloudinary.uploader.upload(
                   contents,
                   folder="menu_items",
                   resource_type="image",
                   quality="auto",
                   fetch_format="auto",
                   transformation=[
                    {
                     "width": 800,
                     "height": 800,
                     "crop": "limit"
                    }
                    ]
                )

                image_urls.append(result["secure_url"])

            except Exception as e:
                print("❌ CLOUDINARY ERROR:", str(e))
                raise HTTPException(status_code=500, detail=str(e))

        menu.image_urls = image_urls

    db.commit()
    delete_cache(f"menu:{user.id}")
    current_date = datetime.now(INDIA_TZ).date()
    delete_cache(
     f"chef:7day-menu:{user.id}:{current_date.isoformat()}"
    )
    db.refresh(menu)

    return {"msg": "Menu updated", "images": menu.image_urls}


# ✅ DELETE MENU
@router.delete("/{menu_id}")
def delete_menu(
    menu_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    menu = db.query(Menu).filter(
     Menu.id == menu_id,
     Menu.is_deleted == False
    ).first()

    if not menu:
        raise HTTPException(status_code=404, detail="Menu not found")

    if menu.chef_id != user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    menu.is_deleted = True
    menu.is_available = False
    

    db.commit()
    delete_cache(f"menu:{user.id}")
    current_date = datetime.now(INDIA_TZ).date()
    delete_cache(
      f"chef:7day-menu:{user.id}:{current_date.isoformat()}"
    )
    return {"msg": "Menu deleted successfully"}


# ✅ TOP DISHES
@router.get("/top-dishes")
def get_top_dishes(
    limit: int = 5,
    db: Session = Depends(get_db)
):
    results = db.query(
        Menu.id,
        Menu.name,
        Menu.price,
        Menu.image_urls,
        func.sum(OrderItem.quantity).label("total_sold")
    )\
    .join(OrderItem, OrderItem.menu_id == Menu.id)\
    .group_by(Menu.id)\
    .order_by(func.sum(OrderItem.quantity).desc())\
    .limit(limit)\
    .all()

    return results


# ✅ GET MENUS
@router.get("/")
def get_menus(
    category: Optional[str] = Query(None),
    food_type: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),

    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),

    db: Session = Depends(get_db),
):
    query = (
        db.query(Menu)
        .filter(
            Menu.is_available == True,
            Menu.is_deleted == False,
        )
    )

    if category:
        query = query.filter(Menu.category == category)

    if food_type:
        query = query.filter(Menu.food_type == food_type)

    if min_price is not None:
        query = query.filter(Menu.price >= min_price)

    if max_price is not None:
        query = query.filter(Menu.price <= max_price)

    menus = (
        query
        .order_by(Menu.name.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return menus

# =========================================================
# CUSTOMER - CHEF 7 DAY MENU
# =========================================================

# =========================================================
# CUSTOMER - CHEF 7 DAY MENU
# =========================================================

# =========================================================
# CUSTOMER - CHEF 7 DAY MENU
# =========================================================

@router.get("/chef/{chef_id}/7-days")
def get_chef_7_day_menu(
    chef_id: UUID,
    db: Session = Depends(get_db),
):
    """
    CUSTOMER

    Returns:
        Today + next 6 days

    Optimized production version:
        - Redis cache
        - Single query for chef
        - Single query for date overrides
        - Single query for all applicable menu cycles
        - Single query for required menus
        - No repeated DB queries inside 7 x 3 meal loops

    Rules:
        - Only 7 days are returned
        - Today's meals can be ordered before cutoff
        - Future meals are visible
        - Future meals cannot be ordered
        - Menu is resolved from chef's 30-day cycle
    """

    # =====================================================
    # INDIA DATE / TIME
    # =====================================================

    now = datetime.now(INDIA_TZ)
    today = now.date()
    end_date = today + timedelta(days=CUSTOMER_MENU_DAYS - 1)

    # =====================================================
    # REDIS CACHE
    # =====================================================

    cache_key = (
        f"chef:7day-menu:"
        f"{chef_id}:"
        f"{today.isoformat()}"
    )

    cached = get_cache(cache_key)

    if cached is not None:
        return cached

    # =====================================================
    # VERIFY CHEF
    # =====================================================

    chef_exists = (
        db.query(User.id)
        .filter(
            User.id == chef_id,
            User.role == "chef",
        )
        .first()
    )

    if not chef_exists:
        raise HTTPException(
            status_code=404,
            detail="Chef not found",
        )

    # =====================================================
    # 1. LOAD ALL DATE OVERRIDES FOR 7 DAYS
    # =====================================================

    overrides = (
        db.query(MenuDateOverride)
        .filter(
            MenuDateOverride.chef_id == chef_id,
            MenuDateOverride.menu_date >= today,
            MenuDateOverride.menu_date <= end_date,
        )
        .all()
    )

    override_map = {
        override.menu_date: override.menu_id
        for override in overrides
    }

    # =====================================================
    # 2. LOAD ALL APPLICABLE MENU CYCLES
    #
    # We load cycles whose start date is <= end_date.
    # Later, Python selects the latest applicable cycle
    # for each target date.
    # =====================================================

    cycles = (
        db.query(MenuCycle)
        .filter(
            MenuCycle.chef_id == chef_id,
            MenuCycle.cycle_start_date <= end_date,
            MenuCycle.meal_type.in_(
                ["breakfast", "lunch", "dinner"]
            ),
        )
        .order_by(
            MenuCycle.cycle_start_date.desc()
        )
        .all()
    )

    # =====================================================
    # 3. RESOLVE MENU IDS FIRST
    # =====================================================

    required_menu_ids = set()

    # Mapping:
    # (target_date, meal_type) -> menu_id
    resolved_menu_ids = {}

    meal_types = (
        "breakfast",
        "lunch",
        "dinner",
    )

    # Group cycles by cycle start date
    cycles_by_start_date = {}

    for cycle in cycles:
        cycles_by_start_date.setdefault(
            cycle.cycle_start_date,
            []
        ).append(cycle)

    cycle_start_dates = sorted(
        cycles_by_start_date.keys(),
        reverse=True,
    )

    # =====================================================
    # RESOLVE EACH DATE + MEAL
    # =====================================================

    for offset in range(CUSTOMER_MENU_DAYS):

        target_date = today + timedelta(days=offset)

        for meal_type in meal_types:

            # -------------------------------------------------
            # PRIORITY 1: DATE OVERRIDE
            # -------------------------------------------------

            override_menu_id = override_map.get(target_date)

            if override_menu_id is not None:
                resolved_menu_ids[
                    (target_date, meal_type)
                ] = override_menu_id

                required_menu_ids.add(
                    override_menu_id
                )

                continue

            # -------------------------------------------------
            # PRIORITY 2: LATEST APPLICABLE CYCLE
            # -------------------------------------------------

            selected_cycle_start = None

            for cycle_start_date in cycle_start_dates:

                if cycle_start_date <= target_date:
                    selected_cycle_start = cycle_start_date
                    break

            if selected_cycle_start is None:
                resolved_menu_ids[
                    (target_date, meal_type)
                ] = None
                continue

            # -------------------------------------------------
            # CALCULATE CYCLE DAY
            # -------------------------------------------------

            days_elapsed = (
                target_date - selected_cycle_start
            ).days

            cycle_day = (
                days_elapsed % MENU_CYCLE_DAYS
            ) + 1

            # -------------------------------------------------
            # FIND EXACT CYCLE ENTRY
            # -------------------------------------------------

            selected_menu_id = None

            for cycle in cycles_by_start_date.get(
                selected_cycle_start,
                []
            ):
                if (
                    cycle.cycle_day == cycle_day
                    and cycle.meal_type.lower().strip()
                    == meal_type
                ):
                    selected_menu_id = cycle.menu_id
                    break

            resolved_menu_ids[
                (target_date, meal_type)
            ] = selected_menu_id

            if selected_menu_id is not None:
                required_menu_ids.add(
                    selected_menu_id
                )

    # =====================================================
    # 4. LOAD ALL REQUIRED MENUS IN ONE QUERY
    # =====================================================

    menu_map = {}

    if required_menu_ids:

        menus = (
            db.query(Menu)
            .filter(
                Menu.id.in_(required_menu_ids),
                Menu.chef_id == chef_id,
                Menu.is_deleted == False,
                Menu.is_available == True,
            )
            .all()
        )

        menu_map = {
            menu.id: menu
            for menu in menus
        }

    # =====================================================
    # 5. BUILD 7 DAY RESPONSE
    # =====================================================

    days = []

    cutoff_times = {
        "breakfast": (9, 0),
        "lunch": (13, 0),
        "dinner": (20, 0),
    }

    for offset in range(CUSTOMER_MENU_DAYS):

        target_date = today + timedelta(days=offset)

        meals = []

        for meal_type in meal_types:

            # -------------------------------------------------
            # GET RESOLVED MENU
            # -------------------------------------------------

            menu_id = resolved_menu_ids.get(
                (target_date, meal_type)
            )

            menu = (
                menu_map.get(menu_id)
                if menu_id is not None
                else None
            )

            # -------------------------------------------------
            # CUTOFF TIME
            # -------------------------------------------------

            cutoff_hour, cutoff_minute = (
                cutoff_times[meal_type]
            )

            cutoff_at = datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                cutoff_hour,
                cutoff_minute,
                tzinfo=INDIA_TZ,
            )

            # -------------------------------------------------
            # STATUS
            # -------------------------------------------------

            if menu is None:

                meal_status = "not_available"
                can_order = False

            elif target_date > today:

                meal_status = "upcoming"
                can_order = False

            elif now >= cutoff_at:

                meal_status = "cutoff_passed"
                can_order = False

            elif not menu.is_available:

                meal_status = "out_of_stock"
                can_order = False

            elif (
                menu.quantity is None
                or menu.quantity <= 0
            ):

                meal_status = "out_of_stock"
                can_order = False

            else:

                meal_status = "available"
                can_order = True

            # -------------------------------------------------
            # SERIALIZE MENU
            # -------------------------------------------------

            menu_data = None

            if menu:

                menu_data = {
                    "id": str(menu.id),
                    "chef_id": str(menu.chef_id),
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
                    "ingredients": menu.ingredients,
                    "image_urls": menu.image_urls,
                    "is_available": menu.is_available,
                }

            # -------------------------------------------------
            # MEAL RESPONSE
            # -------------------------------------------------

            meals.append(
                {
                    "meal_type": meal_type,
                    "cutoff_time": (
                        f"{cutoff_hour:02d}:"
                        f"{cutoff_minute:02d}"
                    ),
                    "meal_status": meal_status,
                    "can_order": can_order,
                    "menu": menu_data,
                }
            )

        # =====================================================
        # DAY RESPONSE
        # =====================================================

        days.append(
            {
                "date": target_date.isoformat(),
                "is_today": target_date == today,
                "is_past": target_date < today,
                "is_upcoming": target_date > today,
                "meals": meals,
            }
        )

    # =====================================================
    # FINAL RESPONSE
    #
    # IMPORTANT:
    # Dates are converted to ISO strings so Redis
    # json.dumps() can safely serialize the response.
    # =====================================================

    response = {
        "success": True,
        "chef_id": str(chef_id),
        "start_date": today.isoformat(),
        "end_date": end_date.isoformat(),
        "days": days,
    }

    # =====================================================
    # SAVE REDIS CACHE
    # =====================================================

    set_cache(
        cache_key,
        response,
        ttl=60,
    )

    return response
    
@router.get("/chef/{chef_id}")
def get_chef_with_menu(
    chef_id: UUID,
    db: Session = Depends(get_db)
):
    """
    CUSTOMER - GET CHEF WITH MENU

    Production optimized:
    - Redis first
    - Only required User fields are loaded
    - Chef profile loaded in the same DB query
    - Only required Menu columns are loaded
    - JSON-ready response is cached
    """

    # =====================================================
    # REDIS CACHE
    # =====================================================

    cache_key = f"menu:v2:chef:{chef_id}"

    cached = get_cache(cache_key)

    if cached is not None:
        return cached

    # =====================================================
    # CHEF + CHEF PROFILE
    # =====================================================

    chef = (
        db.query(
            User.id,
            User.name,
            ChefProfile.bio,
            ChefProfile.location,
            ChefProfile.specialties,
            ChefProfile.profile_image,
        )
        .outerjoin(
            ChefProfile,
            ChefProfile.user_id == User.id,
        )
        .filter(
            User.id == chef_id,
            User.role == "chef",
            User.is_active == True,
        )
        .first()
    )

    if not chef:
        raise HTTPException(
            status_code=404,
            detail="Chef not found",
        )

    # =====================================================
    # MENUS
    # =====================================================

    menus = (
        db.query(
            Menu.id,
            Menu.chef_id,
            Menu.name,
            Menu.description,
            Menu.price,
            Menu.prep_time,
            Menu.quantity,
            Menu.category,
            Menu.food_type,
            Menu.calories,
            Menu.protein,
            Menu.carbs,
            Menu.fats,
            Menu.ingredients,
            Menu.image_urls,
            Menu.is_available,
        )
        .filter(
            Menu.chef_id == chef_id,
            Menu.is_available == True,
            Menu.is_deleted == False,
        )
        .order_by(Menu.name.asc())
        .all()
    )

    # =====================================================
    # SERIALIZE MENU
    # =====================================================

    menu_data = [
        {
            "id": str(menu.id),
            "chef_id": str(menu.chef_id),
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
            "ingredients": menu.ingredients,
            "image_urls": menu.image_urls,
            "is_available": menu.is_available,
        }
        for menu in menus
    ]

    # =====================================================
    # RESPONSE
    # =====================================================

    response = {
        "chef": {
            "id": str(chef.id),
            "name": chef.name,
            "bio": chef.bio,
            "location": chef.location,
            "specialties": chef.specialties,
            "profile_image": chef.profile_image,
        },
        "menus": menu_data,
    }

    # =====================================================
    # SAVE REDIS CACHE
    # =====================================================

    set_cache(
        cache_key,
        response,
        ttl=300,
    )

    return response
    
# get all chefs 

@router.get("/chefs")
def get_all_chefs(
    db: Session = Depends(get_db)
):
    """
    CUSTOMER - GET ALL CHEFS

    Production optimized:
    - Redis cache
    - Only required columns fetched
    - No unnecessary ORM relationship loading
    - Existing API behavior preserved
    """

    # =====================================================
    # REDIS CACHE
    # =====================================================

    cache_key = "chefs:v1:all"

    cached = get_cache(cache_key)

    if cached is not None:
        return cached

    # =====================================================
    # FETCH CHEFS
    # =====================================================

    chefs = (
        db.query(
            User.id,
            User.name,
            ChefProfile.profile_image,
            ChefProfile.specialties,
        )
        .outerjoin(
            ChefProfile,
            ChefProfile.user_id == User.id,
        )
        .filter(
            User.role == "chef",
        )
        .order_by(User.name.asc())
        .all()
    )

    # =====================================================
    # BUILD RESPONSE
    # =====================================================

    response = [
        {
            "id": str(chef.id),
            "name": chef.name,
            "profile_image": chef.profile_image,
            "specialties": chef.specialties,
        }
        for chef in chefs
    ]

    # =====================================================
    # SAVE CACHE
    # =====================================================

    set_cache(
        cache_key,
        response,
        ttl=300,
    )

    return response
    
    
from math import radians, cos, sin, asin, sqrt
# from app.database import get_db


# 🔥 DISTANCE FUNCTION
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # km

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    return R * c


# 🔥 MAIN API
from sqlalchemy.orm import selectinload

@router.get("/nearby-chefs")
def get_nearby_chefs(
    lat: float,
    lng: float,
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    
    cache_key = f"nearby:{round(lat,2)}:{round(lng,2)}:{category or 'all'}"

    cached = get_cache(cache_key)

    if cached:
      print("✅ Nearby Cache Hit")
      return cached
    # Chef Profile ko ek hi batch me load karo
    chefs = (
        db.query(User)
        .options(selectinload(User.chef_profile))
        .filter(User.role == "chef")
        .all()
    )

    chef_ids = [chef.id for chef in chefs]

    # Sab menus ek hi query me
    menus_query = db.query(Menu).filter(
        Menu.chef_id.in_(chef_ids),
        Menu.is_available == True,
        Menu.is_deleted == False,
    )

    if category:
        menus_query = menus_query.filter(
            func.lower(Menu.category) == category.lower()
        )

    all_menus = menus_query.all()

    # Chef wise menu map
    menu_map = {}

    for menu in all_menus:
        menu_map.setdefault(menu.chef_id, []).append(menu)

    nearby_chefs = []

    for chef in chefs:

        profile = chef.chef_profile

        if not profile:
            continue

        if profile.latitude is None or profile.longitude is None:
            continue

        distance = calculate_distance(
            lat,
            lng,
            profile.latitude,
            profile.longitude,
        )

        if distance > 50:
            continue

        menus = menu_map.get(chef.id, [])

        menu_data = []

        for menu in menus:
            menu_data.append({
             "id": str(menu.id),
             "name": menu.name,
             "price": menu.price,
             "category": menu.category,
             "food_type": menu.food_type,
             "prep_time": menu.prep_time,
             "quantity": menu.quantity,
             "image_urls": menu.image_urls,
             "is_available": menu.is_available,
            })

        nearby_chefs.append({
           "id": str(chef.id),
           "name": chef.name,
           "profile_image": profile.profile_image,
           "specialties": profile.specialties,
           "distance": round(distance, 2),
           "menus": menu_data,
          })

    nearby_chefs.sort(key=lambda x: x["distance"])

    set_cache(cache_key, nearby_chefs, ttl=120)

    return nearby_chefs

# set location
# from fastapi import APIRouter, Depends, Form, HTTPException
# from sqlalchemy.orm import Session


from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session
# from app.database import get_db
# from app.models.user import ChefProfile, User
# from app.dependencies.auth import get_current_user
import logging

logger = logging.getLogger(__name__)

@router.post("/chef/set-location")
async def set_kitchen_location(
    latitude: float = Form(...),
    longitude: float = Form(...),
    location: str = Form(...),

    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # 🔴 ROLE CHECK
        if current_user.role != "chef":
            raise HTTPException(status_code=403, detail="Only chefs can set location")

        # 🔴 VALIDATION
        if not (-90 <= latitude <= 90):
            raise HTTPException(status_code=400, detail="Invalid latitude")

        if not (-180 <= longitude <= 180):
            raise HTTPException(status_code=400, detail="Invalid longitude")

        if not location.strip():
            raise HTTPException(status_code=400, detail="Location cannot be empty")

        # 🔍 FETCH CHEF PROFILE
        chef = db.query(ChefProfile).filter(
            ChefProfile.user_id == current_user.id
        ).first()

        if not chef:
            raise HTTPException(status_code=404, detail="Chef profile not found")

        # 🔥 SAVE LOCATION
        chef.latitude = latitude
        chef.longitude = longitude
        chef.location = location.strip()

        db.commit()
        db.refresh(chef)

        return {
            "msg": "Kitchen location saved successfully",
            "latitude": chef.latitude,
            "longitude": chef.longitude,
            "location": chef.location
        }

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        logger.error(f"❌ LOCATION SAVE ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    
    

# search chefs 
@router.get("/search-chefs")
def search_chefs(
    query: str,
    lat: float,
    lng: float,
    db: Session = Depends(get_db)
):
    chefs = (
        db.query(User)
        .options(selectinload(User.chef_profile))
        .filter(User.role == "chef")
        .order_by(User.name.asc())
        .all()
    )

    results = []

    for chef in chefs:

        profile = chef.chef_profile

        if not profile:
            continue

        if profile.latitude is None or profile.longitude is None:
            continue

        distance = calculate_distance(
            lat,
            lng,
            profile.latitude,
            profile.longitude
        )

        if distance > 10:
            continue

        if (
            query.lower() in chef.name.lower()
            or (
                profile.specialties
                and query.lower() in profile.specialties.lower()
            )
        ):
            results.append({
                "id": str(chef.id),
                "name": chef.name,
                "profile_image": profile.profile_image,
                "specialties": profile.specialties,
                "distance": round(distance, 2)
            })

    results.sort(key=lambda x: x["distance"])

    return results


@router.put("/{menu_id}/availability")
def toggle_menu(
    menu_id: str,
    is_available: bool,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    menu = db.query(Menu).filter(
     Menu.id == menu_id,
     Menu.is_deleted == False
    ).first()

    if not menu:
        raise HTTPException(404, "Menu not found")
    
    if menu.chef_id != user.id:
        raise HTTPException(
         status_code=403,
         detail="Not allowed"
        )

    menu.is_available = is_available

    db.commit()
    delete_cache(f"menu:{user.id}")
    current_date = datetime.now(INDIA_TZ).date()
    delete_cache(
      f"chef:7day-menu:{user.id}:{current_date.isoformat()}"
    )
    return {
        "success": True,
        "is_available": menu.is_available
    }
    
    
@router.get("/my")
def get_my_menus(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    return (
        db.query(Menu)
        .filter(
            Menu.chef_id == user.id,
            Menu.is_deleted == False
        )
        .order_by(Menu.name.asc())
        .all()
    )
    
    


# =========================================================
# CHEF - CREATE / UPDATE 30 DAY MENU CYCLE
# =========================================================

@router.post(
    "/cycle",
    response_model=MenuCycleResponse,
)
def create_or_update_menu_cycle(
    data: MenuCycleBulkCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(["chef"])),
):
    # =====================================================
    # 1. VALIDATION
    # =====================================================

    if not data.items:
        raise HTTPException(
            status_code=400,
            detail="At least one menu entry is required",
        )

    # Maximum:
    # 30 days × 3 meals = 90 entries
    if len(data.items) > 90:
        raise HTTPException(
            status_code=400,
            detail=(
                "Maximum 90 entries are allowed "
                "(30 days × 3 meals)"
            ),
        )

    # =====================================================
    # 2. VALIDATE DAY + MEAL TYPE
    # =====================================================

    valid_meals = {
        "breakfast",
        "lunch",
        "dinner",
    }

    combinations = set()

    for item in data.items:

        if item.cycle_day < 1 or item.cycle_day > 30:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"cycle_day must be between 1 and 30"
                ),
            )

        meal_type = (
            str(item.meal_type)
            .lower()
            .strip()
        )

        if meal_type not in valid_meals:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid meal_type. "
                    "Use breakfast, lunch or dinner."
                ),
            )

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

    # =====================================================
    # 3. MENU IDS
    # =====================================================

    menu_ids = [
        item.menu_id
        for item in data.items
    ]

    menus = (
        db.query(Menu)
        .filter(
            Menu.id.in_(menu_ids),
            Menu.chef_id == user.id,
            Menu.is_deleted == False,
        )
        .all()
    )

    menu_map = {
        menu.id: menu
        for menu in menus
    }

    # =====================================================
    # 4. VERIFY MENU OWNERSHIP
    # =====================================================

    for item in data.items:

        menu = menu_map.get(item.menu_id)

        if not menu:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Menu {item.menu_id} "
                    "does not belong to this chef"
                ),
            )

    # =====================================================
    # 5. EXISTING CYCLE
    # =====================================================

    existing_cycles = (
        db.query(MenuCycle)
        .filter(
            MenuCycle.chef_id == user.id,
            MenuCycle.cycle_start_date
            == data.cycle_start_date,
        )
        .all()
    )

    # IMPORTANT:
    # Key must be:
    # (day, meal_type)
    #
    # NOT only:
    # day
    # =====================================================

    existing_map = {
        (
            cycle.cycle_day,
            (
                cycle.meal_type
                or ""
            ).lower().strip(),
        ): cycle
        for cycle in existing_cycles
    }

    # =====================================================
    # 6. UPSERT
    # =====================================================

    for item in data.items:

        meal_type = (
            str(item.meal_type)
            .lower()
            .strip()
        )

        key = (
            item.cycle_day,
            meal_type,
        )

        existing = existing_map.get(key)

        if existing:

            existing.menu_id = item.menu_id
            existing.meal_type = meal_type

        else:

            cycle = MenuCycle(
                chef_id=user.id,
                menu_id=item.menu_id,
                cycle_day=item.cycle_day,
                cycle_start_date=data.cycle_start_date,
                meal_type=meal_type,
            )

            db.add(cycle)

    # =====================================================
    # 7. COMMIT
    # =====================================================

    try:

        db.commit()

        current_date = datetime.now(
            INDIA_TZ
        ).date()

        delete_cache(
            f"chef:7day-menu:"
            f"{user.id}:"
            f"{current_date.isoformat()}"
        )

        delete_cache(
            f"menu:{user.id}"
        )

    except Exception as e:

        db.rollback()

        logger.exception(
            "❌ MENU CYCLE SAVE ERROR: %s",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to save menu cycle",
        )

    # =====================================================
    # 8. RETURN COMPLETE CYCLE
    # =====================================================

    cycles = (
        db.query(MenuCycle)
        .filter(
            MenuCycle.chef_id == user.id,
            MenuCycle.cycle_start_date
            == data.cycle_start_date,
        )
        .order_by(
            MenuCycle.cycle_day.asc(),
            MenuCycle.meal_type.asc(),
        )
        .all()
    )

    response_items = []

    for cycle in cycles:

        menu = (
            db.query(Menu)
            .filter(
                Menu.id == cycle.menu_id,
                Menu.chef_id == user.id,
                Menu.is_deleted == False,
            )
            .first()
        )

        if not menu:
            continue

        response_items.append(
            MenuCycleItemResponse(
                id=cycle.id,
                chef_id=cycle.chef_id,
                menu_id=cycle.menu_id,
                cycle_day=cycle.cycle_day,
                cycle_start_date=cycle.cycle_start_date,
                meal_type=cycle.meal_type,
            )
        )

    return MenuCycleResponse(
        cycle_start_date=data.cycle_start_date,
        total_days=len(
            set(
                item.cycle_day
                for item in response_items
            )
        ),
        items=response_items,
    )
    
    
# =========================================================
# CHEF - GET 30 DAY CYCLE
# =========================================================

@router.get(
    "/cycle",
    response_model=MenuCycleResponse,
)
def get_menu_cycle(
    cycle_start_date: date,
    db: Session = Depends(get_db),
    user=Depends(require_role(["chef"])),
):
    cycles = (
        db.query(MenuCycle)
        .filter(
            MenuCycle.chef_id == user.id,
            MenuCycle.cycle_start_date
            == cycle_start_date,
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

    response_items = []

    for cycle in cycles:

        response_items.append(
            MenuCycleItemResponse(
                id=cycle.id,
                chef_id=cycle.chef_id,
                menu_id=cycle.menu_id,
                cycle_day=cycle.cycle_day,
                cycle_start_date=cycle.cycle_start_date,
            )
        )

    return MenuCycleResponse(
        cycle_start_date=cycle_start_date,
        total_days=len(response_items),
        items=response_items,
    )
    
# =========================================================
# CHEF - DATE OVERRIDE
# =========================================================

@router.post(
    "/date-override",
    response_model=MenuDateOverrideResponse,
)
def create_or_update_date_override(
    data: MenuDateOverrideCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(["chef"])),
):
    # =====================================================
    # VERIFY MENU BELONGS TO CHEF
    # =====================================================

    menu = (
        db.query(Menu)
        .filter(
            Menu.id == data.menu_id,
            Menu.chef_id == user.id,
            Menu.is_deleted == False,
        )
        .first()
    )

    if not menu:
        raise HTTPException(
            status_code=404,
            detail="Menu not found for this chef",
        )

    # =====================================================
    # FIND EXISTING OVERRIDE
    # =====================================================

    override = (
        db.query(MenuDateOverride)
        .filter(
            MenuDateOverride.chef_id == user.id,
            MenuDateOverride.menu_date
            == data.menu_date,
        )
        .first()
    )

    if override:

        override.menu_id = data.menu_id

    else:

        override = MenuDateOverride(
            chef_id=user.id,
            menu_id=data.menu_id,
            menu_date=data.menu_date,
        )

        db.add(override)

    try:

        db.commit()
        current_date = datetime.now(INDIA_TZ).date()

        delete_cache(
          f"chef:7day-menu:{user.id}:{current_date.isoformat()}"
        )

    # Clear normal chef menu cache
        delete_cache(
          f"menu:{user.id}"
        )
        db.refresh(override)
        

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to save menu override",
        )

    return override




# =========================================================
# CHEF - DELETE DATE OVERRIDE
# =========================================================

@router.delete(
    "/date-override/{override_id}"
)
def delete_date_override(
    override_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(require_role(["chef"])),
):
    override = (
        db.query(MenuDateOverride)
        .filter(
            MenuDateOverride.id == override_id,
            MenuDateOverride.chef_id == user.id,
        )
        .first()
    )

    if not override:
        raise HTTPException(
            status_code=404,
            detail="Menu override not found",
        )

    db.delete(override)

    try:

        db.commit()
        current_date = datetime.now(INDIA_TZ).date()

        delete_cache(
         f"chef:7day-menu:{user.id}:{current_date.isoformat()}"
        )

    # Clear normal chef menu cache
        delete_cache(
           f"menu:{user.id}"
        )

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to delete menu override",
        )

    return {
        "message": "Menu override removed successfully"
    }