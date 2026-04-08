from fastapi import APIRouter, Depends, HTTPException, Query,UploadFile,Form,File
from sqlalchemy.orm import Session
from typing import Optional
import shutil
import uuid
from app.models.order import Order
from app.models.menu import Menu
from typing import List
from app.models.menu import Menu
from app.api.deps import get_db, get_current_user
from app.schemas.menu import MenuCreate, MenuUpdate

router = APIRouter()

# ✅ Create Menu
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

    if images:
        for img in images:
            filename = f"{uuid.uuid4()}_{img.filename}"
            path = f"uploads/{filename}"

            with open(path, "wb") as buffer:
                shutil.copyfileobj(img.file, buffer)

            image_urls.append(filename)

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
        ingredients=ingredients.split(",") if ingredients else [],
        image_urls=image_urls
    )

    db.add(menu)
    db.commit()
    db.refresh(menu)

    return menu

# ✅ Get Menu (with filters)
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


# ✅ Update Menu
@router.put("/{menu_id}")
def update_menu(
    menu_id: str,
    data: MenuUpdate,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    menu = db.query(Menu).filter(Menu.id == menu_id).first()

    if not menu:
        raise HTTPException(status_code=404, detail="Menu not found")

    if menu.chef_id != user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(menu, key, value)

    db.commit()
    db.refresh(menu)

    return {"msg": "Menu updated"}


# ✅ Delete Menu
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


from sqlalchemy import func
from app.models.order_item import OrderItem  # import check karo
from app.models.menu import Menu

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