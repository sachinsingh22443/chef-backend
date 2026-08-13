from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
import cloudinary.uploader
from datetime import datetime
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
def is_valid_special(s):
    try:
        cutoff_datetime = datetime.strptime(
            f"{s.created_at.date()} {s.cutoff_time}",
            "%Y-%m-%d %H:%M"
        )
        return datetime.now() <= cutoff_datetime
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

        # 🖼️ Image
        "image_url": s.image_url,

        # 🌱 Food
        "food_type": s.food_type,

        "is_active": s.is_active,
     }
     for s in specials if is_valid_special(s)
    ]


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
        
    updated = False
    data = []

    for s in specials:
        if not is_valid_special(s):
            continue

        remaining = s.max_plates - s.pre_orders

        # 🔥 auto sold out
        if remaining <= 0:
            if s.is_active != 0:
                s.is_active = 0
                updated = True
            continue

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

            # ⏰ Timing
            "cutoff_time": s.cutoff_time,

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
        if updated:
            db.commit()

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

    remaining = special.max_plates - special.pre_orders

    if data.quantity > remaining:
        raise HTTPException(
          status_code=400,
          detail=f"Only {remaining} left"
        )

    # 🔥 update
    special.pre_orders += data.quantity

    if special.pre_orders >= special.max_plates:
        special.is_active = 0

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

        if remaining <= 0:
            continue

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

            # ⏰ Timing
            "cutoff_time": s.cutoff_time,

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