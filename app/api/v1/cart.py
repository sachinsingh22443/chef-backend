from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, date
from zoneinfo import ZoneInfo

from app.api.deps import get_db, get_current_user
from app.models.menu import Menu
from app.models.cart import Cart, CartItem
from app.models.tomorrow_special import TomorrowSpecial
from app.models.menu_cycle import MenuCycle
from app.models.menu_date_override import MenuDateOverride

from pydantic import BaseModel


router = APIRouter(prefix="/cart", tags=["Cart"])

INDIA_TZ = ZoneInfo("Asia/Kolkata")
MENU_CYCLE_DAYS = 30

def get_today_menu_for_chef(
    db: Session,
    chef_id,
    requested_menu_id=None,
    target_date: date | None = None,
):
    """
    Production-safe menu resolver.

    Priority:
    1. Exact date override
    2. Latest applicable cycle
    3. 30-day cycle calculation
    """

    if target_date is None:
        target_date = datetime.now(INDIA_TZ).date()

    # ==========================================
    # 1. DATE OVERRIDE
    # ==========================================

    override = (
        db.query(MenuDateOverride)
        .filter(
            MenuDateOverride.chef_id == chef_id,
            MenuDateOverride.menu_date == target_date,
        )
        .first()
    )

    if override:
        if (
            requested_menu_id is not None
            and override.menu_id != requested_menu_id
        ):
            return None

        return override.menu_id

    # ==========================================
    # 2. LATEST ACTIVE CYCLE
    # ==========================================

    active_cycle = (
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

    if not active_cycle:
        return None

    cycle_start_date = active_cycle[0]

    # ==========================================
    # 3. CALCULATE CYCLE DAY
    # ==========================================

    days_elapsed = (
        target_date - cycle_start_date
    ).days

    cycle_day = (
        days_elapsed % MENU_CYCLE_DAYS
    ) + 1

    # ==========================================
    # 4. EXACT CYCLE MENU
    # ==========================================

    cycle_menu = (
        db.query(MenuCycle)
        .filter(
            MenuCycle.chef_id == chef_id,
            MenuCycle.cycle_start_date == cycle_start_date,
            MenuCycle.cycle_day == cycle_day,
        )
        .first()
    )

    if not cycle_menu:
        return None

    if (
        requested_menu_id is not None
        and cycle_menu.menu_id != requested_menu_id
    ):
        return None

    return cycle_menu.menu_id


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
    # =====================================================
    # QUANTITY VALIDATION
    # =====================================================

    if data.quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be greater than 0"
        )

    # =====================================================
    # GET / CREATE CART
    # =====================================================

    cart = (
        db.query(Cart)
        .filter(Cart.user_id == user.id)
        .first()
    )

    if not cart:
        cart = Cart(user_id=user.id)
        db.add(cart)
        db.flush()

    # =====================================================
    # 🍽️ NORMAL MENU ITEM
    # =====================================================

    if data.type == "menu":

        # -------------------------------------------------
        # FETCH MENU
        # -------------------------------------------------

        menu = (
            db.query(Menu)
            .filter(
                Menu.id == data.item_id,
                Menu.is_available == True,
                Menu.is_deleted == False,
            )
            .first()
        )

        if not menu:
            raise HTTPException(
                status_code=404,
                detail="Menu not found or unavailable"
            )

        # -------------------------------------------------
        # TODAY'S DATE - INDIA
        # -------------------------------------------------

        today = datetime.now(INDIA_TZ).date()

        # -------------------------------------------------
        # VERIFY TODAY'S SCHEDULED MENU
        #
        # Date Override has priority.
        # Otherwise 30-day cycle is used.
        # -------------------------------------------------

        scheduled_menu_id = get_today_menu_for_chef(
            db=db,
            chef_id=menu.chef_id,
            requested_menu_id=menu.id,
            target_date=today,
        )

        if scheduled_menu_id is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "This menu is not available for ordering today. "
                    "Please select today's menu."
                )
            )

        # -------------------------------------------------
        # QUANTITY / STOCK
        # -------------------------------------------------

        if menu.quantity is not None and menu.quantity <= 0:
            raise HTTPException(
                status_code=400,
                detail="Menu is out of stock"
            )

        # -------------------------------------------------
        # EXISTING CART ITEM
        # -------------------------------------------------

        item = (
            db.query(CartItem)
            .filter(
                CartItem.cart_id == cart.id,
                CartItem.menu_id == menu.id,
            )
            .first()
        )

        if item:

            new_quantity = (
                item.quantity + data.quantity
            )

            if (
                menu.quantity is not None
                and new_quantity > menu.quantity
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Only {menu.quantity} "
                        f"items available"
                    )
                )

            item.quantity = new_quantity

            # Keep current menu snapshot updated
            item.name = menu.name
            item.price = menu.price
            item.image = (
                menu.image_urls[0]
                if menu.image_urls
                else ""
            )
            item.food_type = menu.food_type

        # -------------------------------------------------
        # NEW CART ITEM
        # -------------------------------------------------

        else:

            if (
                menu.quantity is not None
                and data.quantity > menu.quantity
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Only {menu.quantity} "
                        f"items available"
                    )
                )

            item = CartItem(
                cart_id=cart.id,
                menu_id=menu.id,
                quantity=data.quantity,
                name=menu.name,
                price=menu.price,
                image=(
                    menu.image_urls[0]
                    if menu.image_urls
                    else ""
                ),
                food_type=menu.food_type,
            )

            db.add(item)

    # =====================================================
    # 🔥 TOMORROW SPECIAL
    # =====================================================

    elif data.type == "special":

        special = (
            db.query(TomorrowSpecial)
            .filter(
                TomorrowSpecial.id == data.item_id
            )
            .first()
        )

        if not special:
            raise HTTPException(
                status_code=404,
                detail="Special not found"
            )

        # =================================================
        # ⏰ CUTOFF CHECK
        # =================================================

        try:

            if not special.special_date:
                raise HTTPException(
                    status_code=400,
                    detail="Special date is not configured"
                )

            if not special.cutoff_time:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Special ordering time "
                        "is not configured"
                    )
                )

            cutoff_datetime = datetime.strptime(
                f"{special.special_date} "
                f"{special.cutoff_time}",
                "%Y-%m-%d %H:%M"
            ).replace(
                tzinfo=INDIA_TZ
            )

            current_time = datetime.now(
                INDIA_TZ
            )

            if current_time >= cutoff_datetime:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Tomorrow Special ordering closed. "
                        f"Order by {special.cutoff_time}"
                    )
                )

        except HTTPException:
            raise

        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid special cutoff time"
            )

        # =================================================
        # 📦 STOCK CHECK
        # =================================================

        remaining = (
            special.max_plates
            - special.pre_orders
        )

        if remaining <= 0:
            raise HTTPException(
                status_code=400,
                detail="Out of stock"
            )

        # =================================================
        # EXISTING SPECIAL IN CART
        # =================================================

        item = (
            db.query(CartItem)
            .filter(
                CartItem.cart_id == cart.id,
                CartItem.special_id == special.id,
            )
            .first()
        )

        if item:

            new_quantity = (
                item.quantity + data.quantity
            )

            if new_quantity > remaining:
                raise HTTPException(
                    status_code=400,
                    detail="Not enough stock"
                )

            item.quantity = new_quantity

        # =================================================
        # NEW SPECIAL CART ITEM
        # =================================================

        else:

            if data.quantity > remaining:
                raise HTTPException(
                    status_code=400,
                    detail="Not enough stock"
                )

            item = CartItem(
                cart_id=cart.id,
                special_id=special.id,
                quantity=data.quantity,
                name=special.dish_name,
                price=special.price,
                image=special.image_url,
                food_type=special.food_type,
            )

            db.add(item)

    # =====================================================
    # INVALID TYPE
    # =====================================================

    else:

        raise HTTPException(
            status_code=400,
            detail="Invalid type"
        )

    # =====================================================
    # COMMIT
    # =====================================================

    try:
        db.commit()

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to add item to cart"
        )

    return {
        "msg": "Added to cart"
    }


# =============================
# ✅ UPDATE CART
# =============================
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
    # =====================================================
    # GET USER CART
    # =====================================================

    cart = (
        db.query(Cart)
        .filter(Cart.user_id == user.id)
        .first()
    )

    if not cart:
        raise HTTPException(
            status_code=404,
            detail="Cart not found"
        )

    # =====================================================
    # 🍽️ NORMAL MENU ITEM
    # =====================================================

    if type == "menu":

        # -------------------------------------------------
        # FIND CART ITEM
        # -------------------------------------------------

        item = (
            db.query(CartItem)
            .filter(
                CartItem.cart_id == cart.id,
                CartItem.menu_id == item_id,
            )
            .first()
        )

        if not item:
            raise HTTPException(
                status_code=404,
                detail="Menu item not found in cart"
            )

        # -------------------------------------------------
        # REMOVE ITEM
        # -------------------------------------------------

        if quantity <= 0:
            db.delete(item)
            db.commit()

            return {
                "msg": "Cart updated"
            }

        # -------------------------------------------------
        # FIND CURRENT MENU
        # -------------------------------------------------

        menu = (
            db.query(Menu)
            .filter(
                Menu.id == item_id,
                Menu.is_deleted == False,
                Menu.is_available == True,
            )
            .first()
        )

        if not menu:
            raise HTTPException(
                status_code=400,
                detail="Menu is no longer available"
            )

        # -------------------------------------------------
        # TODAY'S DATE
        # -------------------------------------------------

        today = datetime.now(
            INDIA_TZ
        ).date()

        # -------------------------------------------------
        # VERIFY TODAY'S SCHEDULED MENU
        #
        # Date override has priority.
        # Otherwise 30-day cycle is checked.
        # -------------------------------------------------

        scheduled_menu_id = get_today_menu_for_chef(
            db=db,
            chef_id=menu.chef_id,
            requested_menu_id=menu.id,
            target_date=today,
        )

        if scheduled_menu_id is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "This menu is no longer available "
                    "for ordering today."
                )
            )

        # -------------------------------------------------
        # STOCK CHECK
        # -------------------------------------------------

        if (
            menu.quantity is not None
            and quantity > menu.quantity
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Only {menu.quantity} "
                    f"items available"
                )
            )

        # -------------------------------------------------
        # UPDATE SNAPSHOT
        # -------------------------------------------------

        item.quantity = quantity

        item.name = menu.name
        item.price = menu.price
        item.image = (
            menu.image_urls[0]
            if menu.image_urls
            else ""
        )
        item.food_type = menu.food_type

    # =====================================================
    # 🔥 TOMORROW SPECIAL
    # =====================================================

    elif type == "special":

        # -------------------------------------------------
        # FIND CART ITEM
        # -------------------------------------------------

        item = (
            db.query(CartItem)
            .filter(
                CartItem.cart_id == cart.id,
                CartItem.special_id == item_id,
            )
            .first()
        )

        if not item:
            raise HTTPException(
                status_code=404,
                detail="Special item not found in cart"
            )

        # -------------------------------------------------
        # REMOVE
        # -------------------------------------------------

        if quantity <= 0:
            db.delete(item)
            db.commit()

            return {
                "msg": "Cart updated"
            }

        # -------------------------------------------------
        # FIND SPECIAL
        # -------------------------------------------------

        special = (
            db.query(TomorrowSpecial)
            .filter(
                TomorrowSpecial.id == item_id
            )
            .first()
        )

        if not special:
            raise HTTPException(
                status_code=404,
                detail="Special not found"
            )

        # =================================================
        # ⏰ CUTOFF CHECK
        # =================================================

        try:

            if not special.special_date:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Special date is not configured"
                    )
                )

            if not special.cutoff_time:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Special ordering time "
                        "is not configured"
                    )
                )

            cutoff_datetime = datetime.strptime(
                f"{special.special_date} "
                f"{special.cutoff_time}",
                "%Y-%m-%d %H:%M"
            ).replace(
                tzinfo=INDIA_TZ
            )

            current_time = datetime.now(
                INDIA_TZ
            )

            if current_time >= cutoff_datetime:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Tomorrow Special ordering closed. "
                        f"Order by {special.cutoff_time}"
                    )
                )

        except HTTPException:
            raise

        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid special cutoff time"
            )

        # =================================================
        # 📦 STOCK CHECK
        # =================================================

        remaining = (
            special.max_plates
            - special.pre_orders
        )

        if remaining <= 0:
            raise HTTPException(
                status_code=400,
                detail="Tomorrow Special is sold out"
            )

        if quantity > remaining:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Only {remaining} "
                    f"plates remaining"
                )
            )

        # -------------------------------------------------
        # UPDATE SPECIAL SNAPSHOT
        # -------------------------------------------------

        item.quantity = quantity

        item.name = special.dish_name
        item.price = special.price
        item.image = special.image_url
        item.food_type = special.food_type

    # =====================================================
    # INVALID TYPE
    # =====================================================

    else:

        raise HTTPException(
            status_code=400,
            detail="Invalid type"
        )

    # =====================================================
    # COMMIT
    # =====================================================

    try:

        db.commit()

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to update cart"
        )

    return {
        "msg": "Cart updated"
    }
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