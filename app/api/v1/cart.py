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
    meal_type: str | None = None,
):
    """
    Production-safe menu resolver.

    Priority:
    1. Exact date override
    2. Latest applicable cycle
    3. 30-day cycle calculation

    For normal menu:
    meal_type is also checked.
    """

    # =====================================================
    # TARGET DATE
    # =====================================================

    if target_date is None:
        target_date = datetime.now(INDIA_TZ).date()

    # =====================================================
    # NORMALIZE MEAL TYPE
    # =====================================================

    if meal_type is not None:
        meal_type = meal_type.lower().strip()

        if meal_type not in {
            "breakfast",
            "lunch",
            "dinner",
        }:
            return None

    # =====================================================
    # 1. DATE OVERRIDE
    # =====================================================

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

    # =====================================================
    # 2. LATEST ACTIVE CYCLE
    # =====================================================

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
    # 4. EXACT CYCLE MENU
    # =====================================================

    query = (
        db.query(MenuCycle)
        .filter(
            MenuCycle.chef_id == chef_id,
            MenuCycle.cycle_start_date == cycle_start_date,
            MenuCycle.cycle_day == cycle_day,
        )
    )

    # =====================================================
    # MEAL TYPE FILTER
    # =====================================================

    if meal_type is not None:
        query = query.filter(
            MenuCycle.meal_type == meal_type
        )

    cycle_menu = query.first()

    if not cycle_menu:
        return None

    # =====================================================
    # REQUESTED MENU CHECK
    # =====================================================

    if (
        requested_menu_id is not None
        and cycle_menu.menu_id != requested_menu_id
    ):
        return None

    return cycle_menu.menu_id

# =============================
# ✅ GET CART
# =============================
# =============================
# ✅ GET CART
# =============================

@router.get("/")
def get_cart(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    cart = (
        db.query(Cart)
        .filter(
            Cart.user_id == user.id
        )
        .first()
    )

    if not cart:
        return {
            "items": []
        }

    items = []

    for item in cart.items:

        items.append({

            # =================================================
            # IMPORTANT
            # CartItem unique ID
            # =================================================

            "id": str(item.id),

            # =================================================
            # ACTUAL ITEM ID
            # =================================================

            "item_id": str(
                item.menu_id
                or item.special_id
            ),

            # =================================================
            # BASIC DATA
            # =================================================

            "name": item.name,

            "price": item.price,

            "image": item.image,

            "quantity": item.quantity,

            # =================================================
            # TYPE
            # =================================================

            "type": (
                "menu"
                if item.menu_id
                else "special"
            ),

            # =================================================
            # NORMAL MENU CYCLE DATA
            # =================================================

            "menu_date": (
                item.menu_date.isoformat()
                if item.menu_date
                else None
            ),

            "meal_type": (
                item.meal_type
                if item.meal_type
                else None
            ),

            # =================================================
            # FOOD TYPE
            # =================================================

            "food_type": item.food_type,

            # =================================================
            # MENU ID
            # =================================================

            "menu_id": (
                str(item.menu_id)
                if item.menu_id
                else None
            ),

            # =================================================
            # SPECIAL ID
            # =================================================

            "special_id": (
                str(item.special_id)
                if item.special_id
                else None
            ),
        })

    return {
        "items": items
    }

# =============================
# ✅ ADD TO CART
# =============================


class CartItemCreate(BaseModel):
    type: str

    item_id: str

    quantity: int

    # =====================================================
    # NORMAL MENU
    # =====================================================

    menu_date: date | None = None

    meal_type: str | None = None


@router.post("/add")
def add_to_cart(
    data: CartItemCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # =====================================================
    # QUANTITY VALIDATION
    # =====================================================

    if data.quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be greater than 0",
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
    # NORMAL MENU
    # =====================================================

    if data.type == "menu":

        # -------------------------------------------------
        # VALIDATE MEAL TYPE
        # -------------------------------------------------

        if not data.meal_type:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Meal type is required. "
                    "Use breakfast, lunch or dinner."
                ),
            )

        meal_type = data.meal_type.lower().strip()

        if meal_type not in {
            "breakfast",
            "lunch",
            "dinner",
        }:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid meal type. "
                    "Use breakfast, lunch or dinner."
                ),
            )

        # -------------------------------------------------
        # TARGET DATE
        # -------------------------------------------------

        target_date = (
            data.menu_date
            if data.menu_date
            else datetime.now(INDIA_TZ).date()
        )

        today = datetime.now(
            INDIA_TZ
        ).date()

        # -------------------------------------------------
        # PAST DATE BLOCK
        # -------------------------------------------------

        if target_date > today:
            raise HTTPException(
               status_code=400,
               detail=(
                "This meal is upcoming. "
                "You can view it, but ordering is not available yet."
                ),
            )

        if target_date < today:
            raise HTTPException(
               status_code=400,
               detail="Past menu dates are closed.",
            )

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
                detail="Menu not found or unavailable",
            )

        # -------------------------------------------------
        # VERIFY CYCLE MENU
        # -------------------------------------------------

        scheduled_menu_id = (
            get_today_menu_for_chef(
                db=db,
                chef_id=menu.chef_id,
                requested_menu_id=menu.id,
                target_date=target_date,
                meal_type=meal_type,
            )
        )

        if scheduled_menu_id is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"This menu is not scheduled for "
                    f"{meal_type} on "
                    f"{target_date.strftime('%d %b %Y')}."
                ),
            )

        # -------------------------------------------------
        # CUTOFF TIME
        # -------------------------------------------------

        cutoff_times = {
          "breakfast": "09:00",
          "lunch": "13:00",
          "dinner": "20:00",
        }

        cutoff_time = cutoff_times[meal_type]

        # -------------------------------------------------
        # CUTOFF ONLY FOR TODAY
        # -------------------------------------------------

        if target_date == today:

            cutoff_datetime = datetime.strptime(
                f"{target_date} {cutoff_time}",
                "%Y-%m-%d %H:%M",
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
                        f"{meal_type.capitalize()} "
                        f"ordering is closed for today. "
                        f"Order by {cutoff_datetime.strftime('%I:%M %p')}."
                    ),
                )

        # -------------------------------------------------
        # STOCK
        # -------------------------------------------------

        if (
            menu.quantity is not None
            and menu.quantity <= 0
        ):
            raise HTTPException(
                status_code=400,
                detail="Menu is out of stock",
            )

        # -------------------------------------------------
        # EXISTING CART ITEM
        #
        # Same dish + same date + same meal
        # -------------------------------------------------

        item = (
            db.query(CartItem)
            .filter(
                CartItem.cart_id == cart.id,
                CartItem.menu_id == menu.id,
                CartItem.menu_date == target_date,
                CartItem.meal_type == meal_type,
            )
            .first()
        )

        if item:

            new_quantity = (
                item.quantity
                + data.quantity
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
                    ),
                )

            item.quantity = new_quantity

            # -------------------------------------------------
            # UPDATE SNAPSHOT
            # -------------------------------------------------

            item.name = menu.name
            item.price = menu.price

            item.image = (
                menu.image_urls[0]
                if menu.image_urls
                else ""
            )

            item.food_type = menu.food_type

            item.menu_date = target_date
            item.meal_type = meal_type

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
                    ),
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

                # =========================================
                # NORMAL MENU CYCLE
                # =========================================

                menu_date=target_date,

                meal_type=meal_type,
            )

            db.add(item)

    # =====================================================
    # TOMORROW SPECIAL
    # =====================================================

    elif data.type == "special":

        special = (
            db.query(TomorrowSpecial)
            .filter(
                TomorrowSpecial.id
                == data.item_id
            )
            .first()
        )

        if not special:
            raise HTTPException(
                status_code=404,
                detail="Special not found",
            )

        # =================================================
        # CUTOFF CHECK
        # =================================================

        try:

            if not special.special_date:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Special date is not configured"
                    ),
                )

            if not special.cutoff_time:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Special ordering time "
                        "is not configured"
                    ),
                )

            cutoff_datetime = datetime.strptime(
                f"{special.special_date} "
                f"{special.cutoff_time}",
                "%Y-%m-%d %H:%M",
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
                        "Tomorrow Special ordering "
                        "closed. "
                        f"Order by {special.cutoff_time}"
                    ),
                )

        except HTTPException:
            raise

        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid special cutoff time",
            )

        # =================================================
        # STOCK CHECK
        # =================================================

        remaining = (
            special.max_plates
            - special.pre_orders
        )

        if remaining <= 0:
            raise HTTPException(
                status_code=400,
                detail="Out of stock",
            )

        if data.quantity > remaining:
            raise HTTPException(
                status_code=400,
                detail="Not enough stock",
            )

        # =================================================
        # EXISTING SPECIAL
        # =================================================

        item = (
            db.query(CartItem)
            .filter(
                CartItem.cart_id == cart.id,
                CartItem.special_id
                == special.id,
            )
            .first()
        )

        if item:

            new_quantity = (
                item.quantity
                + data.quantity
            )

            if new_quantity > remaining:
                raise HTTPException(
                    status_code=400,
                    detail="Not enough stock",
                )

            item.quantity = new_quantity

            item.name = special.dish_name
            item.price = special.price
            item.image = special.image_url
            item.food_type = special.food_type

        # =================================================
        # NEW SPECIAL
        # =================================================

        else:

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
            detail="Invalid type",
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
            detail="Failed to add item to cart",
        )

    return {
        "msg": "Added to cart",
    }

# =============================
# ✅ UPDATE CART
# =============================
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
    user=Depends(get_current_user),
):

    # =====================================================
    # GET USER CART
    # =====================================================

    cart = (
        db.query(Cart)
        .filter(
            Cart.user_id == user.id
        )
        .first()
    )

    if not cart:
        raise HTTPException(
            status_code=404,
            detail="Cart not found",
        )

    # =====================================================
    # FIND CART ITEM BY CART ITEM ID
    # =====================================================

    item = (
        db.query(CartItem)
        .filter(
            CartItem.id == item_id,
            CartItem.cart_id == cart.id,
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Cart item not found",
        )

    # =====================================================
    # REMOVE ITEM
    # =====================================================

    if quantity <= 0:

        db.delete(item)

        db.commit()

        return {
            "msg": "Cart updated"
        }

    # =====================================================
    # TOMORROW SPECIAL
    # =====================================================

    if type == "special":

        if not item.special_id:
            raise HTTPException(
                status_code=400,
                detail="Invalid special cart item",
            )

        special = (
            db.query(TomorrowSpecial)
            .filter(
                TomorrowSpecial.id
                == item.special_id
            )
            .first()
        )

        if not special:
            raise HTTPException(
                status_code=404,
                detail="Special not found",
            )

        # =================================================
        # CUTOFF
        # =================================================

        try:

            if not special.special_date:
                raise HTTPException(
                    status_code=400,
                    detail="Special date is not configured",
                )

            if not special.cutoff_time:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Special ordering time "
                        "is not configured"
                    ),
                )

            cutoff_datetime = datetime.strptime(
                f"{special.special_date} "
                f"{special.cutoff_time}",
                "%Y-%m-%d %H:%M",
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
                        "Tomorrow Special ordering "
                        "closed. "
                        f"Order by {special.cutoff_time}"
                    ),
                )

        except HTTPException:
            raise

        except Exception:

            raise HTTPException(
                status_code=400,
                detail="Invalid special cutoff time",
            )

        # =================================================
        # STOCK
        # =================================================

        remaining = (
            special.max_plates
            - special.pre_orders
        )

        if remaining <= 0:
            raise HTTPException(
                status_code=400,
                detail="Tomorrow Special is sold out",
            )

        if quantity > remaining:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Only {remaining} "
                    f"plates remaining"
                ),
            )

        # =================================================
        # UPDATE SNAPSHOT
        # =================================================

        item.quantity = quantity

        item.name = special.dish_name

        item.price = special.price

        item.image = special.image_url

        item.food_type = special.food_type

        # =================================================
        # COMMIT
        # =================================================

        try:

            db.commit()

        except Exception:

            db.rollback()

            raise HTTPException(
                status_code=500,
                detail="Failed to update cart",
            )

        return {
            "msg": "Cart updated"
        }

    # =====================================================
    # NORMAL MENU
    # =====================================================

    elif type == "menu":

        if not item.menu_id:
            raise HTTPException(
                status_code=400,
                detail="Invalid menu cart item",
            )

        menu = (
            db.query(Menu)
            .filter(
                Menu.id == item.menu_id,
                Menu.is_deleted == False,
                Menu.is_available == True,
            )
            .first()
        )

        if not menu:
            raise HTTPException(
                status_code=400,
                detail="Menu is no longer available",
            )

        # =================================================
        # DATE
        # =================================================

        target_date = item.menu_date

        if target_date is None:

            target_date = datetime.now(
                INDIA_TZ
            ).date()

        today = datetime.now(
            INDIA_TZ
        ).date()

        # =================================================
        # PAST DATE
        # =================================================

        if target_date > today:
            raise HTTPException(
                status_code=400,
                detail=(
                 "This meal is upcoming. "
                 "You cannot update or order it yet."
                ),
            )

        if target_date < today:
            raise HTTPException(
              status_code=400,
              detail="Past menu dates are closed.",
            )

        # =================================================
        # MEAL TYPE
        # =================================================

        meal_type = (
            item.meal_type.lower().strip()
            if item.meal_type
            else None
        )

        if meal_type not in {
            "breakfast",
            "lunch",
            "dinner",
        }:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid meal type for cart item."
                ),
            )

        # =================================================
        # VERIFY CYCLE
        # =================================================

        scheduled_menu_id = (
            get_today_menu_for_chef(
                db=db,
                chef_id=menu.chef_id,
                requested_menu_id=menu.id,
                target_date=target_date,
                meal_type=meal_type,
            )
        )

        if scheduled_menu_id is None:

            raise HTTPException(
                status_code=400,
                detail=(
                    "This menu is no longer "
                    "scheduled for this date."
                ),
            )

        # =================================================
        # CUTOFF TIMES
        # =================================================

        cutoff_times = {
            "breakfast": "09:00",
            "lunch": "13:00",
            "dinner": "20:00",
        }

        cutoff_time = cutoff_times[
            meal_type
        ]

        # =================================================
        # TODAY CUTOFF
        # =================================================

        if target_date == today:

            cutoff_datetime = datetime.strptime(
                f"{target_date} {cutoff_time}",
                "%Y-%m-%d %H:%M",
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
                        f"{meal_type.capitalize()} "
                        f"ordering is closed for today. "
                        f"Order by "
                        f"{cutoff_datetime.strftime('%I:%M %p')}."
                    ),
                )

        # =================================================
        # STOCK
        # =================================================

        if (
            menu.quantity is not None
            and quantity > menu.quantity
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Only {menu.quantity} "
                    f"items available"
                ),
            )

        # =================================================
        # UPDATE CART ITEM
        # =================================================

        item.quantity = quantity

        item.name = menu.name

        item.price = menu.price

        item.image = (
            menu.image_urls[0]
            if menu.image_urls
            else ""
        )

        item.food_type = menu.food_type

        # =================================================
        # KEEP DATE + MEAL
        # =================================================

        item.menu_date = target_date

        item.meal_type = meal_type

    # =====================================================
    # INVALID TYPE
    # =====================================================

    else:

        raise HTTPException(
            status_code=400,
            detail="Invalid type",
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
            detail="Failed to update cart",
        )

    return {
        "msg": "Cart updated"
    }
# =============================
# ✅ REMOVE ITEM
# =============================
# =============================
# ✅ REMOVE ITEM
# =============================

@router.delete("/remove/{type}/{item_id}")
def remove_item(
    type: str,
    item_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):

    # =====================================================
    # GET USER CART
    # =====================================================

    cart = (
        db.query(Cart)
        .filter(
            Cart.user_id == user.id
        )
        .first()
    )

    if not cart:
        raise HTTPException(
            status_code=404,
            detail="Cart not found",
        )

    # =====================================================
    # VALIDATE TYPE
    # =====================================================

    if type not in {
        "menu",
        "special",
    }:

        raise HTTPException(
            status_code=400,
            detail="Invalid type",
        )

    # =====================================================
    # FIND CART ITEM BY CART ITEM ID
    # =====================================================

    item = (
        db.query(CartItem)
        .filter(
            CartItem.id == item_id,
            CartItem.cart_id == cart.id,
        )
        .first()
    )

    if not item:

        raise HTTPException(
            status_code=404,
            detail="Item not found in cart",
        )

    # =====================================================
    # TYPE SAFETY
    # =====================================================

    if type == "menu" and not item.menu_id:

        raise HTTPException(
            status_code=400,
            detail="Invalid menu cart item",
        )

    if type == "special" and not item.special_id:

        raise HTTPException(
            status_code=400,
            detail="Invalid special cart item",
        )

    # =====================================================
    # DELETE
    # =====================================================

    db.delete(item)

    try:

        db.commit()

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to remove item",
        )

    return {
        "msg": "Removed"
    }