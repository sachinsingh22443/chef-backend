from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.menu import Menu
from app.models.cart import Cart, CartItem
from app.models.tomorrow_special import TomorrowSpecial

router = APIRouter(prefix="/cart", tags=["Cart"])


# =============================
# ✅ GET CART
# =============================
@router.get("/")
def get_cart(db: Session = Depends(get_db), user=Depends(get_current_user)):
    cart = db.query(Cart).filter(Cart.user_id == user.id).first()

    if not cart:
        return {"items": []}

    items = []

    for item in cart.items:
        items.append({
        "id": str(item.menu_id or item.special_id),
        "name": item.name,
        "price": item.price,
        "image": item.image,
        "quantity": item.quantity,
        "type": "menu" if item.menu_id else "special"   # 🔥🔥 MOST IMPORTANT
    })

    return {"items": items}


# =============================
# ✅ ADD TO CART
# =============================
from pydantic import BaseModel

class CartItemCreate(BaseModel):
    type: str
    item_id: str
    quantity: int


@router.post("/add")
def add_to_cart(
    data: CartItemCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    if data.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be > 0")

    cart = db.query(Cart).filter(Cart.user_id == user.id).first()

    if not cart:
        cart = Cart(user_id=user.id)
        db.add(cart)
        db.commit()
        db.refresh(cart)

    # =========================
    # 🔥 MENU ITEM
    # =========================
    if data.type == "menu":
        menu = db.query(Menu).filter(Menu.id == data.item_id).first()

        if not menu:
            raise HTTPException(status_code=404, detail="Menu not found")

        item = db.query(CartItem).filter(
            CartItem.cart_id == cart.id,
            CartItem.menu_id == data.item_id
        ).first()

        if item:
            item.quantity += data.quantity
        else:
            item = CartItem(
                cart_id=cart.id,
                menu_id=menu.id,
                quantity=data.quantity,
                name=menu.name,
                price=menu.price,
                image=menu.image_urls[0] if menu.image_urls else "",
                food_type=menu.food_type
            )
            db.add(item)

    # =========================
    # 🔥 SPECIAL ITEM
    # =========================
    elif data.type == "special":
        special = db.query(TomorrowSpecial).filter(TomorrowSpecial.id == data.item_id).first()

        if not special:
            raise HTTPException(status_code=404, detail="Special not found")

        remaining = special.max_plates - special.pre_orders

        if remaining <= 0:
            raise HTTPException(status_code=400, detail="Out of stock")

        item = db.query(CartItem).filter(
            CartItem.cart_id == cart.id,
            CartItem.special_id == data.item_id
        ).first()

        if item:
            if item.quantity + data.quantity > remaining:
                raise HTTPException(status_code=400, detail="Not enough stock")
            item.quantity += data.quantity
        else:
            if data.quantity > remaining:
                raise HTTPException(status_code=400, detail="Not enough stock")

            item = CartItem(
                cart_id=cart.id,
                special_id=special.id,
                quantity=data.quantity,
                name=special.dish_name,
                price=special.price,
                image=special.image_url,
                food_type=special.food_type
            )
            db.add(item)

    else:
        raise HTTPException(status_code=400, detail="Invalid type")

    db.commit()

    return {"msg": "Added to cart"}


# =============================
# ✅ UPDATE CART
# =============================
@router.put("/update")
def update_cart(
    type: str,
    item_id: str,
    quantity: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    cart = db.query(Cart).filter(Cart.user_id == user.id).first()

    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    if type == "menu":
        item = db.query(CartItem).filter(
            CartItem.cart_id == cart.id,
            CartItem.menu_id == item_id
        ).first()

    elif type == "special":
        item = db.query(CartItem).filter(
            CartItem.cart_id == cart.id,
            CartItem.special_id == item_id
        ).first()

    else:
        raise HTTPException(status_code=400, detail="Invalid type")

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if quantity <= 0:
        db.delete(item)
    else:
        item.quantity = quantity

    db.commit()

    return {"msg": "Cart updated"}


# =============================
# ✅ REMOVE ITEM
# =============================
@router.delete("/remove/{type}/{item_id}")
def remove_item(
    type: str,
    item_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    cart = db.query(Cart).filter(Cart.user_id == user.id).first()

    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    if type == "menu":
        item = db.query(CartItem).filter(
            CartItem.cart_id == cart.id,
            CartItem.menu_id == item_id
        ).first()

    elif type == "special":
        item = db.query(CartItem).filter(
            CartItem.cart_id == cart.id,
            CartItem.special_id == item_id
        ).first()

    else:
        raise HTTPException(status_code=400, detail="Invalid type")

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    db.delete(item)
    db.commit()

    return {"msg": "Removed"}