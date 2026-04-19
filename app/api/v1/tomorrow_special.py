from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
import cloudinary.uploader
from datetime import datetime

from app.api.deps import get_db, get_current_user
from app.models.tomorrow_special import TomorrowSpecial
from app.models.user import User
from app.schemas.tomorrow_special import PreOrderCreate

router = APIRouter(prefix="/tomorrow-special", tags=["Tomorrow Special"])


# =============================
# ✅ CREATE
# =============================
@router.post("/")
async def create_special(
    dish_name: str = Form(...),
    description: str = Form(None),
    price: float = Form(...),
    max_plates: int = Form(...),
    cutoff_time: str = Form(...),
    image: UploadFile = File(None),
    food_type: str = Form(...), 

    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    image_url = None

    if image:
        try:
            contents = await image.read()

            result = cloudinary.uploader.upload(
                contents,
                folder="tomorrow_specials"
            )

            image_url = result["secure_url"]

        except Exception as e:
            raise HTTPException(status_code=500, detail="Image upload failed")

    special = TomorrowSpecial(
        chef_id=user.id,
        dish_name=dish_name,
        description=description,
        price=price,
        max_plates=max_plates,
        cutoff_time=cutoff_time,
        image_url=image_url,
        food_type=food_type
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
    except:
        return False


# =============================
# ✅ GET MY SPECIALS
# =============================
@router.get("/")
def get_my_specials(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    specials = db.query(TomorrowSpecial)\
        .filter(TomorrowSpecial.chef_id == user.id)\
        .order_by(TomorrowSpecial.created_at.desc())\
        .all()

    return [
        {
            "id": str(s.id),
            "dish_name": s.dish_name,
            "description": s.description,
            "price": s.price,
            "max_plates": s.max_plates,
            "cutoff_time": s.cutoff_time,
            "image_url": s.image_url,
        }
        for s in specials if is_valid_special(s)
    ]


# =============================
# 🔥 GET ALL (OPTIMIZED)
# =============================
@router.get("/all")
def get_all_specials(db: Session = Depends(get_db)):
    specials = db.query(TomorrowSpecial)\
        .options(joinedload(TomorrowSpecial.chef))\
        .order_by(TomorrowSpecial.created_at.desc())\
        .all()

    data = []

    for s in specials:
        if not is_valid_special(s):
            continue

        remaining = s.max_plates - s.pre_orders

        # 🔥 auto sold out
        if remaining <= 0:
            s.is_active = 0
            db.commit()
            continue

        data.append({
            "id": str(s.id),
            "dish_name": s.dish_name,
            "description": s.description,
            "price": s.price,
            "max_plates": s.max_plates,
            "pre_orders": s.pre_orders,          # 🔥 NEW
            "remaining": remaining,              # 🔥 NEW
            "cutoff_time": s.cutoff_time,
            "image_url": s.image_url,
            "chef_id": str(s.chef_id),
            "chef_name": s.chef.name if s.chef else "Chef",
            "is_active": s.is_active    ,
            "created_at": s.created_at.isoformat(),# 🔥 NEW
        })

    return data

@router.post("/pre-order")
def create_pre_order(
    data: PreOrderCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    special = db.query(TomorrowSpecial)\
        .filter(TomorrowSpecial.id == data.special_id)\
        .with_for_update()\
        .first()

    if not special:
        raise HTTPException(status_code=404, detail="Special not found")

    if special.is_active == 0:
        raise HTTPException(status_code=400, detail="Sold out")

    remaining = special.max_plates - special.pre_orders

    if data.quantity > remaining:
        raise HTTPException(status_code=400, detail="Only {remaining} left")

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
    specials = db.query(TomorrowSpecial)\
        .options(joinedload(TomorrowSpecial.chef))\
        .order_by(TomorrowSpecial.created_at.desc())\
        .all()

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
            "price": s.price,

            # 🔥 IMPORTANT FIX (frontend crash solve)
            "max_plates": s.max_plates,
            "pre_orders": s.pre_orders,

            "remaining": remaining,
            "cutoff_time": s.cutoff_time,
            "image_url": s.image_url,
            "chef_id": str(s.chef_id),
            "chef_name": chef.name,
            "distance": round(distance, 2),
            "food_type": s.food_type
        })

    return result