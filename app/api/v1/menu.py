from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, Form, File
from sqlalchemy.orm import Session
from typing import Optional, List
import cloudinary.uploader

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
                    folder="menu_items"
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
    db.refresh(menu)

    return menu


# ✅ UPDATE MENU
@router.put("/{menu_id}")
async def update_menu(
    menu_id: str,
    name: str = Form(None),
    description: str = Form(None),
    price: float = Form(None),
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
                    folder="menu_items"
                )

                image_urls.append(result["secure_url"])

            except Exception as e:
                print("❌ CLOUDINARY ERROR:", str(e))
                raise HTTPException(status_code=500, detail=str(e))

        menu.image_urls = image_urls

    db.commit()
    db.refresh(menu)

    return {"msg": "Menu updated", "images": menu.image_urls}


# ✅ DELETE MENU
@router.delete("/{menu_id}")
def delete_menu(
    menu_id: str,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    menu = db.query(Menu).filter(Menu.id == menu_id).first()

    if not menu:
        raise HTTPException(status_code=404, detail="Menu not found")

    if menu.chef_id != user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    db.delete(menu)
    db.commit()

    return {"msg": "Menu deleted"}


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
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Menu)

    if category:
        query = query.filter(Menu.category == category)

    if min_price:
        query = query.filter(Menu.price >= min_price)

    if max_price:
        query = query.filter(Menu.price <= max_price)

    return query.all()