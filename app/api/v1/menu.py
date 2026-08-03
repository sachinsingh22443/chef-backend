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
from sqlalchemy import func

router = APIRouter()

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



@router.get("/chef/{chef_id}")
def get_chef_with_menu(
    chef_id: UUID,
    db: Session = Depends(get_db)
):
    # =========================
    # Redis Cache
    # =========================
    cache_key = f"menu:{chef_id}"

    cached = get_cache(cache_key)

    if cached:
        print("✅ Chef Menu Cache Hit")
        return cached

    # =========================
    # Chef
    # =========================
    chef = (
        db.query(User)
        .options(selectinload(User.chef_profile))
        .filter(
            User.id == chef_id,
            User.role == "chef"
        )
        .first()
    )

    if not chef:
        raise HTTPException(
            status_code=404,
            detail="Chef not found"
        )

    # =========================
    # Menus
    # =========================
    menus = (
        db.query(Menu)
        .filter(
            Menu.chef_id == chef_id,
            Menu.is_available == True,
            Menu.is_deleted == False
        )
        .order_by(Menu.name.asc())
        .all()
    )

    # =========================
    # JSON Serializable Menu
    # =========================
    menu_data = []

    for menu in menus:
        menu_data.append({
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
            "is_available": menu.is_available
        })

    # =========================
    # Response
    # =========================
    response = {
        "chef": {
            "id": str(chef.id),
            "name": chef.name,
            "bio": chef.chef_profile.bio if chef.chef_profile else None,
            "location": chef.chef_profile.location if chef.chef_profile else None,
            "specialties": chef.chef_profile.specialties if chef.chef_profile else None,
            "profile_image": chef.chef_profile.profile_image if chef.chef_profile else None,
        },
        "menus": menu_data
    }

    # =========================
    # Save Cache
    # =========================
    set_cache(cache_key, response, ttl=300)

    return response
    
# get all chefs 

@router.get("/chefs")
def get_all_chefs(db: Session = Depends(get_db)):
    chefs = (
        db.query(User)
        .options(selectinload(User.chef_profile))
        .filter(User.role == "chef")
        .order_by(User.name.asc())
        .all()
    )

    return [
        {
            "id": str(chef.id),
            "name": chef.name,
            "profile_image": (
                chef.chef_profile.profile_image
                if chef.chef_profile
                else None
            ),
            "specialties": (
                chef.chef_profile.specialties
                if chef.chef_profile
                else None
            ),
        }
        for chef in chefs
    ]
    
    
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
from app.models.user import ChefProfile, User
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