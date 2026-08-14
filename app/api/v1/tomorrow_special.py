from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
import cloudinary.uploader
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
import logging
from app.api.deps import get_db, get_current_user
from app.models.tomorrow_special import TomorrowSpecial
from app.models.user import User
from app.schemas.tomorrow_special import PreOrderCreate

router = APIRouter(prefix="/tomorrow-special", tags=["Tomorrow Special"])

logger = logging.getLogger(__name__)
# =============================
# ✅ CREATE
# =============================
@router.post("/")
async def create_special(
    dish_name: str = Form(...),
    description: str = Form(None),

    price: float = Form(...),
    original_price: float = Form(None),

    max_plates: int = Form(...),
    cutoff_time: str = Form(...),

    calories: int = Form(None),
    protein: float = Form(None),
    carbs: float = Form(None),
    fats: float = Form(None),

    preparation_time: int = Form(None),
    ingredients: str = Form(None),

    image: UploadFile = File(None),
    food_type: str = Form(...),

    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if user.role != "chef":
        raise HTTPException(
         status_code=403,
         detail="Only chefs can create tomorrow specials"
        )
        
    if price <= 0:
        raise HTTPException(
         status_code=400,
         detail="Price must be greater than 0"
        )

    if original_price is not None and original_price < price:
        raise HTTPException(
         status_code=400,
         detail="Original price must be greater than or equal to special price"
        )

    if max_plates <= 0:
        raise HTTPException(
         status_code=400,
         detail="Maximum plates must be greater than 0"
        )

    if calories is not None and calories < 0:
        raise HTTPException(
         status_code=400,
         detail="Calories cannot be negative"
        )

    if preparation_time is not None and preparation_time < 0:
        raise HTTPException(
          status_code=400,
          detail="Preparation time cannot be negative"
        )
    india_now = datetime.now(
      ZoneInfo("Asia/Kolkata")
    )
    special_date = (
      india_now + timedelta(days=1)
    ).date()
    image_url = None

    if image:
        try:
            contents = await image.read()

            result = cloudinary.uploader.upload(
                contents,
                folder="tomorrow_specials"
            )

            image_url = result["secure_url"]

        except Exception:
            logger.exception("Tomorrow special image upload failed")

            raise HTTPException(
               status_code=500,
               detail="Image upload failed"
               )

    special = TomorrowSpecial(
       chef_id=user.id,

       dish_name=dish_name,
       description=description,

       # 💰 Pricing
       price=price,
       original_price=original_price,

       # 📦 Quantity
       max_plates=max_plates,

       # ⏰ Timing
       cutoff_time=cutoff_time,
       special_date=special_date,

       # 🥗 Nutrition
       calories=calories,
       protein=protein,
       carbs=carbs,
       fats=fats,

       # 🍳 Preparation
       preparation_time=preparation_time,

       # 🧂 Ingredients
       ingredients=ingredients,

       # 🖼️ Image
       image_url=image_url,

       # 🌱 Food Type
       food_type=food_type,
    )

    db.add(special)
    db.commit()
    db.refresh(special)

    return {"msg": "Created", "id": str(special.id)}


# =============================
# 🔥 COMMON FILTER FUNCTION
# =============================
# =============================
# 🔥 COMMON SPECIAL VALIDATION
# =============================
def is_valid_special(s):
    try:
        if not s.special_date:
            return False

        if not s.cutoff_time:
            return False

        cutoff_datetime = datetime.strptime(
            f"{s.special_date} {s.cutoff_time}",
            "%Y-%m-%d %H:%M"
        ).replace(
            tzinfo=ZoneInfo("Asia/Kolkata")
        )

        current_time = datetime.now(
            ZoneInfo("Asia/Kolkata")
        )

        # Cutoff ke baad customer listing se hide
        if current_time >= cutoff_datetime:
            return False

        return True

    except Exception:
        return False


# =============================
# ✅ GET MY SPECIALS
# =============================
@router.get("/")
def get_my_specials(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    specials = (
       db.query(TomorrowSpecial)
       .filter(
        TomorrowSpecial.chef_id == user.id,
        TomorrowSpecial.is_active == 1
        )
         .order_by(TomorrowSpecial.created_at.desc())
         .all()
        )

    return [
     {
        "id": str(s.id),

        "dish_name": s.dish_name,
        "description": s.description,

        # 💰 Pricing
        "price": s.price,
        "original_price": s.original_price,

        # 🥗 Nutrition
        "calories": s.calories,
        "protein": s.protein,
        "carbs": s.carbs,
        "fats": s.fats,

        # 🍳 Preparation
        "preparation_time": s.preparation_time,

        # 🧂 Ingredients
        "ingredients": s.ingredients,

        # 📦 Quantity
        "max_plates": s.max_plates,
        "pre_orders": s.pre_orders,
        "remaining": s.max_plates - s.pre_orders,

        # ⏰ Timing
        "cutoff_time": s.cutoff_time,
        "special_date": s.special_date.isoformat() if s.special_date else None,
    
        # 🖼️ Image
        "image_url": s.image_url,

        # 🌱 Food
        "food_type": s.food_type,

        "is_active": s.is_active,
     }
     for s in specials
    ]


# =============================
# 👨‍🍳 CHEF - MY SPECIAL HISTORY
# =============================
@router.get("/history")
def get_special_history(
    date_filter: date = None,
    from_date: date = None,
    to_date: date = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # =============================
    # 🔐 ONLY CHEF
    # =============================
    if user.role != "chef":
        raise HTTPException(
            status_code=403,
            detail="Only chefs can access special history"
        )

    # =============================
    # 🔎 BASE QUERY
    # =============================
    query = db.query(TomorrowSpecial).filter(
        TomorrowSpecial.chef_id == user.id
    )

    # =============================
    # 📅 SPECIFIC DATE
    # =============================
    if date_filter:
        query = query.filter(
            TomorrowSpecial.special_date == date_filter
        )

    # =============================
    # 📅 DATE RANGE
    # =============================
    elif from_date and to_date:

        if from_date > to_date:
            raise HTTPException(
                status_code=400,
                detail="from_date cannot be greater than to_date"
            )

        query = query.filter(
            TomorrowSpecial.special_date >= from_date,
            TomorrowSpecial.special_date <= to_date
        )

    # =============================
    # 📅 ONLY FROM DATE
    # =============================
    elif from_date:
        query = query.filter(
            TomorrowSpecial.special_date >= from_date
        )

    # =============================
    # 📅 ONLY TO DATE
    # =============================
    elif to_date:
        query = query.filter(
            TomorrowSpecial.special_date <= to_date
        )

    # =============================
    # 🔽 LATEST SPECIAL DATE FIRST
    # =============================
    specials = query.order_by(
        TomorrowSpecial.special_date.desc(),
        TomorrowSpecial.created_at.desc()
    ).all()

    result = []

    for special in specials:

        remaining = max(
            special.max_plates - special.pre_orders,
            0
        )

        sold_out = remaining <= 0

        result.append({
            "id": str(special.id),

            "dish_name": special.dish_name,
            "description": special.description,

            "price": special.price,
            "original_price": special.original_price,

            "calories": special.calories,
            "protein": special.protein,
            "carbs": special.carbs,
            "fats": special.fats,

            "preparation_time": special.preparation_time,
            "ingredients": special.ingredients,

            "image_url": special.image_url,
            "food_type": special.food_type,

            # 📦 PLATES
            "max_plates": special.max_plates,
            "pre_orders": special.pre_orders,
            "remaining": remaining,
            "sold_out": sold_out,

            # ⏰ TIMING
            "cutoff_time": special.cutoff_time,
            "special_date": (
                special.special_date.isoformat()
                if special.special_date
                else None
            ),

            # 📊 STATUS
            "is_active": special.is_active,

            "created_at": (
                special.created_at.isoformat()
                if special.created_at
                else None
            ),
        })

    return {
        "total": len(result),
        "specials": result
    }

# =============================
# 🔥 GET ALL (OPTIMIZED)
# =============================
@router.get("/all")
def get_all_specials(db: Session = Depends(get_db)):
    specials = (
       db.query(TomorrowSpecial)
       .options(joinedload(TomorrowSpecial.chef))
       .filter(TomorrowSpecial.is_active == 1)
       .order_by(TomorrowSpecial.created_at.desc())
       .all()
       )
        
    data = []

    for s in specials:
        if not is_valid_special(s):
            continue

        remaining = s.max_plates - s.pre_orders
        sold_out = remaining <= 0

        data.append({
            "id": str(s.id),

            "dish_name": s.dish_name,
            "description": s.description,

            # 💰 Pricing
            "price": s.price,
            "original_price": s.original_price,

            # 🥗 Nutrition
            "calories": s.calories,
            "protein": s.protein,
            "carbs": s.carbs,
            "fats": s.fats,

            # 🍳 Preparation
            "preparation_time": s.preparation_time,

            # 🧂 Ingredients
            "ingredients": s.ingredients,

            # 📦 Quantity
            "max_plates": s.max_plates,
            "pre_orders": s.pre_orders,
            "remaining": remaining,
            "sold_out": sold_out,

            # ⏰ Timing
            "cutoff_time": s.cutoff_time,
            "special_date": s.special_date.isoformat() if s.special_date else None,

            # 🖼️ Image
            "image_url": s.image_url,

            # 👨‍🍳 Chef
            "chef_id": str(s.chef_id),
            "chef_name": s.chef.name if s.chef else "Chef",

            # 🌱 Food
            "food_type": s.food_type,

            # 📊 Status
            "is_active": s.is_active,

            "created_at": s.created_at.isoformat(),
           })
    return data

@router.post("/pre-order")
def create_pre_order(
    data: PreOrderCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    special = db.query(TomorrowSpecial)\
        .filter(TomorrowSpecial.id == data.special_id)\
        .with_for_update()\
        .first()
        
    if not special:
        raise HTTPException(
          status_code=404,
          detail="Special not found"
        )
    if data.quantity <= 0:
        raise HTTPException(
         status_code=400,
         detail="Quantity must be at least 1"
        )
    if special.is_active == 0:
        raise HTTPException(status_code=400, detail="Sold out")
    try:
        if not special.special_date:
            raise HTTPException(
             status_code=400,
             detail="Special date is not configured"
            )

        if not special.cutoff_time:
            raise HTTPException(
             status_code=400,
             detail="Special ordering time is not configured"
            )

        cutoff_datetime = datetime.strptime(
         f"{special.special_date} {special.cutoff_time}",
         "%Y-%m-%d %H:%M"
        ).replace(
         tzinfo=ZoneInfo("Asia/Kolkata")
        )
        current_time = datetime.now(
          ZoneInfo("Asia/Kolkata")
        )
        if current_time >= cutoff_datetime:
            raise HTTPException(
                status_code=400,
                detail=(
                 f"Tomorrow Special ordering closed. "
                 f"Order by {special.cutoff_time}"
                )
            )

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
         status_code=400,
         detail="Invalid special date or cutoff time"
        )

    remaining = special.max_plates - special.pre_orders

    if data.quantity > remaining:
        raise HTTPException(
          status_code=400,
          detail=f"Only {remaining} left"
        )

    # 🔥 update
    special.pre_orders += data.quantity
    db.commit()
    db.refresh(special)

    return {
        "msg": "Pre-order successful",
        "pre_orders": special.pre_orders,
        "remaining": special.max_plates - special.pre_orders
    }
    
    
from math import radians, cos, sin, asin, sqrt

# 🔥 DISTANCE FUNCTION (same जैसा menu में है)
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    return R * c


@router.get("/nearby")
def get_nearby_specials(
    lat: float,
    lng: float,
    category: str = None,
    db: Session = Depends(get_db)
):
    specials = (
      db.query(TomorrowSpecial)
      .options(joinedload(TomorrowSpecial.chef))
      .filter(TomorrowSpecial.is_active == 1)
      .order_by(TomorrowSpecial.created_at.desc())
      .all()
    )

    result = []

    for s in specials:

        # 🔥 VALID SPECIAL
        if not is_valid_special(s):
            continue

        chef = s.chef

        if not chef or not chef.chef_profile:
            continue

        profile = chef.chef_profile

        if profile.latitude is None or profile.longitude is None:
            continue

        # 🔥 DISTANCE FILTER
        distance = calculate_distance(
            lat,
            lng,
            profile.latitude,
            profile.longitude
        )

        if distance > 50:
            continue

        # 🔥 CATEGORY FILTER (FIXED)
        if category:
            if category.lower() not in s.dish_name.lower():
                continue

        remaining = s.max_plates - s.pre_orders
        sold_out = remaining <= 0

        result.append({
            "id": str(s.id),

            "dish_name": s.dish_name,
            "description": s.description,

            # 💰 Pricing
            "price": s.price,
            "original_price": s.original_price,

            # 🥗 Nutrition
            "calories": s.calories,
            "protein": s.protein,
            "carbs": s.carbs,
            "fats": s.fats,

            # 🍳 Preparation
            "preparation_time": s.preparation_time,

            # 🧂 Ingredients
            "ingredients": s.ingredients,

            # 📦 Quantity
            "max_plates": s.max_plates,
            "pre_orders": s.pre_orders,
            "remaining": remaining,
            "sold_out": sold_out,

            # ⏰ Timing
            "cutoff_time": s.cutoff_time,
            "special_date": s.special_date.isoformat() if s.special_date else None,
            

            # 🖼️ Image
            "image_url": s.image_url,

            # 👨‍🍳 Chef
            "chef_id": str(s.chef_id),
            "chef_name": chef.name,

            # 📍 Distance
            "distance": round(distance, 2),

            # 🌱 Food
            "food_type": s.food_type,
        })

    return result