from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from app.models.menu_cycle import MenuCycle
from app.models.menu_date_override import MenuDateOverride
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from sqlalchemy import or_
from app.core.cache import get_cache, set_cache
import os
from app.models.tomorrow_special_pre_order import TomorrowSpecialPreOrder
from app.core.cache import delete_cache
from app.services.whatsapp import send_new_order_whatsapp
from app.api.deps import get_db, get_current_user
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.menu import Menu
from app.models.cart import Cart, CartItem
from app.models.notification import Notification
from app.models.earning import Earning
from app.schemas.order import OrderCreate
from app.core.razorpay_client import client
from pydantic import BaseModel
from app.models.wallet import Wallet
from app.models.wallet_transaction import WalletTransaction
from app.models.referral import Referral

router = APIRouter(prefix="/orders", tags=["Orders"])



# =========================================================
# 🍽️ MENU CYCLE RESOLVER
# =========================================================

# =========================================================
# 🍽️ MENU CYCLE RESOLVER
# =========================================================

INDIA_TZ = ZoneInfo("Asia/Kolkata")
MENU_CYCLE_DAYS = 30


def get_today_menu_for_chef(
    db: Session,
    chef_id,
    requested_menu_id=None,
    target_date: date | None = None,
):
    """
    Resolve the menu scheduled for a chef on a specific date.

    Supports:
    - Date override
    - 30-day menu cycle
    - Automatic cycle repetition
    - Breakfast / Lunch / Dinner
    - Multiple MenuCycle rows for the same day

    IMPORTANT:
    A single cycle_day has 3 records:
        breakfast
        lunch
        dinner

    Therefore we MUST NOT use .first() directly.
    We check all records for that cycle day and then
    match requested_menu_id.
    """

    # =====================================================
    # 0️⃣ TARGET DATE
    # =====================================================

    if target_date is None:
        target_date = datetime.now(INDIA_TZ).date()

    # =====================================================
    # 1️⃣ DATE OVERRIDE HAS HIGHEST PRIORITY
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
        return override.menu_id

    # =====================================================
    # 2️⃣ FIND LATEST CYCLE STARTED ON OR BEFORE TARGET DATE
    # =====================================================

    active_cycle_start = (
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

    if not active_cycle_start:
        return None

    cycle_start_date = active_cycle_start[0]

    # =====================================================
    # 3️⃣ CALCULATE 30-DAY CYCLE DAY
    # =====================================================

    days_elapsed = (
        target_date - cycle_start_date
    ).days

    cycle_day = (
        days_elapsed % MENU_CYCLE_DAYS
    ) + 1

    # =====================================================
    # 4️⃣ GET ALL MENUS FOR THIS CYCLE DAY
    #
    # IMPORTANT:
    # One day contains:
    #   breakfast
    #   lunch
    #   dinner
    #
    # DO NOT use .first()
    # =====================================================

    cycle_menus = (
        db.query(MenuCycle)
        .filter(
            MenuCycle.chef_id == chef_id,
            MenuCycle.cycle_start_date == cycle_start_date,
            MenuCycle.cycle_day == cycle_day,
        )
        .all()
    )

    if not cycle_menus:
        return None

    # =====================================================
    # 5️⃣ REQUESTED MENU VALIDATION
    #
    # If customer is ordering a specific menu,
    # check whether THAT menu is scheduled today.
    # =====================================================

    if requested_menu_id is not None:

        for cycle_menu in cycle_menus:

            if cycle_menu.menu_id == requested_menu_id:
                return cycle_menu.menu_id

        # Requested menu exists for chef,
        # but is not today's scheduled menu.
        return None

    # =====================================================
    # 6️⃣ NO SPECIFIC MENU REQUESTED
    #
    # Return first scheduled menu.
    # =====================================================

    return cycle_menus[0].menu_id
# =========================================================
# 🎁 REFERRAL REWARD — SINGLE TIFFIN
# =========================================================

# =========================================================
# 🎁 REFERRAL REWARD — SINGLE TIFFIN
# =========================================================

def process_single_tiffin_referral_reward(
    db: Session,
    order: Order,
):
    """
    Give ₹1 referral reward to referrer.

    Reward is allowed only when:
    - referred user has a valid referral
    - order is NOT subscription
    - order is NOT Tomorrow Special
    - exactly one normal menu item
    - quantity is exactly 1
    - referral has not already been rewarded
    - referral is not already attached to another order

    IMPORTANT:
    This function DOES NOT COMMIT.
    Caller must commit atomically.
    """

    # =====================================================
    # 1️⃣ CUSTOMER CHECK
    # =====================================================

    if not order.user_id:
        return False

    # =====================================================
    # 2️⃣ FIND + LOCK REFERRAL
    # =====================================================

    referral = (
        db.query(Referral)
        .filter(
            Referral.referred_user_id == order.user_id,
            Referral.status == "PENDING",
        )
        .with_for_update()
        .first()
    )

    if not referral:
        return False

    # =====================================================
    # 3️⃣ SELF REFERRAL PROTECTION
    # =====================================================

    if referral.referrer_id == order.user_id:
        return False

    # =====================================================
    # 4️⃣ SUBSCRIPTION = NO SINGLE TIFFIN REWARD
    # =====================================================

    if getattr(order, "is_subscription", False):
        return False

    # =====================================================
    # 5️⃣ LOAD ORDER ITEMS
    # =====================================================

    items = (
        db.query(OrderItem)
        .filter(
            OrderItem.order_id == order.id
        )
        .all()
    )

    if not items:
        return False

    # =====================================================
    # 6️⃣ EXACTLY ONE ITEM
    # =====================================================

    if len(items) != 1:
        return False

    item = items[0]

    # =====================================================
    # 7️⃣ TOMORROW SPECIAL = NO REWARD
    # =====================================================

    if item.special_id is not None:
        return False

    # =====================================================
    # 8️⃣ MUST BE NORMAL MENU
    # =====================================================

    if item.menu_id is None:
        return False

    # =====================================================
    # 9️⃣ EXACTLY ONE TIFFIN
    # =====================================================

    if item.quantity != 1:
        return False

    # =====================================================
    # 🔟 DUPLICATE PROTECTION
    # =====================================================

    if referral.status == "REWARDED":
        return False

    if referral.order_id is not None:
        return False

    # =====================================================
    # 1️⃣1️⃣ BACKEND CONTROLLED REWARD
    # =====================================================

    reward_amount = 1.0

    # =====================================================
    # 1️⃣2️⃣ FIND / CREATE REFERRER WALLET
    # =====================================================

    wallet = (
        db.query(Wallet)
        .filter(
            Wallet.user_id == referral.referrer_id
        )
        .with_for_update()
        .first()
    )

    if not wallet:

        wallet = Wallet(
            user_id=referral.referrer_id,
            balance=0.0,
        )

        db.add(wallet)

        # Force INSERT before balance update
        db.flush()

    # =====================================================
    # 1️⃣3️⃣ ADD MONEY
    # =====================================================

    wallet.balance = (
        float(wallet.balance or 0)
        + reward_amount
    )

    # =====================================================
    # 1️⃣4️⃣ WALLET TRANSACTION
    # =====================================================

    wallet_transaction = WalletTransaction(
        wallet_id=wallet.id,
        user_id=referral.referrer_id,

        amount=reward_amount,

        transaction_type="referral_reward",

        meal_type=None,

        subscription_id=None,

        order_id=order.id,

        referral_id=referral.id,

        schedule_id=None,

        description=(
            "Referral reward ₹1 for "
            "single tiffin order"
        ),
    )

    db.add(wallet_transaction)

    # =====================================================
    # 1️⃣5️⃣ MARK REFERRAL REWARDED
    # =====================================================

    referral.status = "REWARDED"

    referral.reward_amount = reward_amount

    referral.reward_type = "single_tiffin"

    referral.order_id = order.id

    referral.rewarded_at = datetime.utcnow()

    referral.cancelled_at = None

    referral.cancellation_reason = None

    # =====================================================
    # 1️⃣6️⃣ NO COMMIT HERE
    # =====================================================

    return True


# =========================================================
# 🔄 REVERSE REFERRAL REWARD
# =========================================================

def reverse_single_tiffin_referral_reward(
    db: Session,
    order: Order,
):
    """
    Reverse previously given ₹1 referral reward
    when the qualifying order is cancelled.

    IMPORTANT:
    - No duplicate reversal
    - Wallet is locked
    - Referral is locked
    - No commit inside this function
    """

    if not order.user_id:
        return False

    # =====================================================
    # 1️⃣ FIND REWARDED REFERRAL FOR THIS ORDER
    # =====================================================

    referral = (
        db.query(Referral)
        .filter(
            Referral.referred_user_id == order.user_id,
            Referral.order_id == order.id,
            Referral.status == "REWARDED",
        )
        .with_for_update()
        .first()
    )

    if not referral:
        return False

    # =====================================================
    # 2️⃣ FIND ORIGINAL REWARD TRANSACTION
    # =====================================================

    original_transaction = (
        db.query(WalletTransaction)
        .filter(
            WalletTransaction.referral_id == referral.id,
            WalletTransaction.order_id == order.id,
            WalletTransaction.transaction_type == "referral_reward",
        )
        .first()
    )

    if not original_transaction:
        return False

    # =====================================================
    # 3️⃣ CHECK WHETHER ALREADY REVERSED
    # =====================================================

    already_reversed = (
        db.query(WalletTransaction)
        .filter(
            WalletTransaction.referral_id == referral.id,
            WalletTransaction.order_id == order.id,
            WalletTransaction.transaction_type
            == "referral_reward_reversal",
        )
        .first()
    )

    if already_reversed:
        return False

    # =====================================================
    # 4️⃣ LOCK REFERRER WALLET
    # =====================================================

    wallet = (
        db.query(Wallet)
        .filter(
            Wallet.user_id == referral.referrer_id
        )
        .with_for_update()
        .first()
    )

    if not wallet:
        return False

    # =====================================================
    # 5️⃣ REWARD AMOUNT
    # =====================================================

    reward_amount = float(
        original_transaction.amount or 0
    )

    if reward_amount <= 0:
        return False

    # =====================================================
    # 6️⃣ REVERSE WALLET BALANCE
    # =====================================================

    wallet.balance = (
        float(wallet.balance or 0)
        - reward_amount
    )

    # =====================================================
    # 7️⃣ CREATE REVERSAL TRANSACTION
    # =====================================================

    reversal_transaction = WalletTransaction(
        wallet_id=wallet.id,
        user_id=referral.referrer_id,

        amount=-reward_amount,

        transaction_type="referral_reward_reversal",

        meal_type=None,

        subscription_id=None,

        order_id=order.id,

        referral_id=referral.id,

        schedule_id=None,

        description=(
            "Referral reward reversed because "
            "the qualifying order was cancelled"
        ),
    )

    db.add(reversal_transaction)

    # =====================================================
    # 8️⃣ RESET REFERRAL
    # =====================================================
    #
    # This order no longer qualifies.
    #
    # Future qualifying order can reward again.
    #

    referral.status = "PENDING"

    referral.reward_amount = 0.0

    referral.reward_type = None

    referral.order_id = None

    referral.rewarded_at = None

    referral.cancelled_at = datetime.utcnow()

    referral.cancellation_reason = (
        "Reward reversed because qualifying "
        "order was cancelled"
    )

    return True

@router.get("/chef-orders")
def get_chef_orders(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    try:
        orders = (
            db.query(Order)
            .options(selectinload(Order.items))
            .filter(
                Order.chef_id == user.id
            )
            .order_by(Order.created_at.desc())
            .all()
        )

        data = []

        for order in orders:

            # COD order tabhi Chef ko dikhega
            # jab customer ne COD confirm kiya ho.
            if (
                order.payment_method == "cod"
                and not order.cod_confirmed
            ):
                continue

            items = []

            for item in order.items:

                items.append({
                    "id": str(item.id) if item.id else None,
                    "name": item.item_name,
                    "quantity": item.quantity,
                    "price": float(item.price or 0),
                    "image": item.item_image,

                    # 🔥 Tomorrow Special identification
                    "special_id": (
                        str(item.special_id)
                        if item.special_id
                        else None
                    ),

                    "menu_id": (
                        str(item.menu_id)
                        if item.menu_id
                        else None
                    ),

                    "is_tomorrow_special": (
                        item.special_id is not None
                    ),
                })

            data.append({
                "id": str(order.id),

                "status": order.status,

                "total_price": float(
                    order.total_price or 0
                ),

                "created_at": order.created_at,

                # Customer
                "customer_name": order.customer_name,
                "phone": order.phone,
                "address": order.address,

                # Payment
                "payment_method": order.payment_method,
                "payment_status": order.payment_status,

                # 🔥 IMPORTANT
                "cod_confirmed": bool(
                    order.cod_confirmed
                ),

                # 🔥 Tomorrow Special flag
                "is_tomorrow_special": any(
                    item.special_id is not None
                    for item in order.items
                ),

                # Items
                "items": items,
            })

        return {
            "total_orders": len([
                o for o in data
                if o["status"] != "cancelled"
            ]),
            "orders": data
        }

    except Exception as e:
        print(
            "❌ CHEF ORDERS ERROR:",
            repr(e)
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to fetch chef orders"
        )

# =========================
# ✅ GET ALL ORDERS
# =========================
@router.get("/")
def get_my_orders(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # =====================================================
    # CACHE KEY
    # =====================================================

    cache_key = f"orders:v1:user:{user.id}"

    # =====================================================
    # CACHE HIT
    # =====================================================

    cached = get_cache(cache_key)

    if cached is not None:
        return cached

    # =====================================================
    # DATABASE
    # =====================================================

    orders = (
        db.query(Order)
        .options(
            selectinload(Order.items)
        )
        .filter(
            Order.user_id == user.id
        )
        .order_by(
            Order.created_at.desc()
        )
        .all()
    )

    # =====================================================
    # RESPONSE
    # =====================================================

    result = []

    for order in orders:

        result.append({
            "id": str(order.id),
            "status": order.status,
            "total_price": order.total_price,
            "created_at": (
                order.created_at.isoformat()
                if order.created_at
                else None
            ),

            "items": [
                {
                    "id": str(item.id),
                    "name": item.item_name,
                    "quantity": item.quantity,
                    "price": item.price,
                    "image": item.item_image,
                }
                for item in order.items
            ],
        })

    # =====================================================
    # CACHE
    # =====================================================

    set_cache(
        cache_key,
        result,
        ttl=30,
    )

    return result
    
# =========================
# 🍽️ CUSTOMER - MY SPECIAL HISTORY
# =========================
@router.get("/special-history")
def get_my_special_history(
    date_filter: date = None,
    from_date: date = None,
    to_date: date = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    # =========================
    # 🔎 BASE QUERY
    # =========================
    query = (
        db.query(
            Order,
            OrderItem,
            TomorrowSpecial
        )
        .join(
            OrderItem,
            OrderItem.order_id == Order.id
        )
        .join(
            TomorrowSpecial,
            TomorrowSpecial.id == OrderItem.special_id
        )
        .filter(
            Order.user_id == user.id,
            OrderItem.special_id.isnot(None)
        )
    )

    # =========================
    # 📅 SPECIFIC DATE
    # =========================
    if date_filter:

        query = query.filter(
            TomorrowSpecial.special_date == date_filter
        )

    # =========================
    # 📅 DATE RANGE
    # =========================
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

    # =========================
    # 📅 ONLY FROM DATE
    # =========================
    elif from_date:

        query = query.filter(
            TomorrowSpecial.special_date >= from_date
        )

    # =========================
    # 📅 ONLY TO DATE
    # =========================
    elif to_date:

        query = query.filter(
            TomorrowSpecial.special_date <= to_date
        )

    # =========================
    # 🔽 LATEST FIRST
    # =========================
    rows = query.order_by(
        TomorrowSpecial.special_date.desc(),
        Order.created_at.desc()
    ).all()

    result = []

    for order, item, special in rows:
        created_at = order.created_at

        if created_at:
            if created_at.tzinfo is None:
                created_at = created_at.replace(
                    tzinfo=ZoneInfo("UTC")
                )

            created_at = created_at.astimezone(
                ZoneInfo("Asia/Kolkata")
            )

        result.append({
            
            
            # =========================
            # 🧾 ORDER
            # =========================
            "order_id": str(order.id),
            "order_status": order.status,

            "ordered_at": (
                created_at.isoformat()
                if created_at
                else None
            ),

            # =========================
            # 🍽️ SPECIAL
            # =========================
            "special_id": str(special.id),
            "dish_name": special.dish_name,
            "description": special.description,

            "image_url": special.image_url,
            "food_type": special.food_type,

            # =========================
            # 📅 SPECIAL DATE
            # =========================
            "special_date": (
                special.special_date.isoformat()
                if special.special_date
                else None
            ),

            "cutoff_time": special.cutoff_time,

            # =========================
            # 📦 ORDERED QUANTITY
            # =========================
            "quantity": item.quantity,

            # OrderItem.price already contains
            # total price for that item
            "total": item.price,

            # Per plate price
            "unit_price": (
                item.price / item.quantity
                if item.quantity
                else 0
            ),

            # =========================
            # 👨‍🍳 CHEF
            # =========================
            "chef_id": str(special.chef_id),
        })

    return {
        "total": len(result),
        "special_orders": result
    }


# =========================
# ✅ GET SINGLE ORDER
# =========================
from uuid import UUID

@router.get("/{order_id}")
def get_order(
    order_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    # UUID validation
    try:
        order_uuid = UUID(order_id)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid order ID"
        )

    # Customer apna order dekh sakta hai
    # Chef apne assigned orders dekh sakta hai
    order = (
        db.query(Order)
        .options(selectinload(Order.items))
        .filter(
            Order.id == order_uuid,
            or_(
                Order.user_id == user.id,
                Order.chef_id == user.id,
            )
        )
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    # 🇮🇳 Convert created_at to IST
    created_at = order.created_at

    if created_at:
        if created_at.tzinfo is None:
            created_at = created_at.replace(
                tzinfo=ZoneInfo("UTC")
            )

        created_at = created_at.astimezone(
            ZoneInfo("Asia/Kolkata")
        )

    return {
        "id": str(order.id),

        "status": order.status,

        "total_price": float(
            order.total_price or 0
        ),

        "customer_name": order.customer_name,

        "phone": order.phone,

        "address": order.address,

        "created_at": (
            created_at.isoformat()
            if created_at
            else None
        ),

        "payment_method": order.payment_method,

        "payment_status": order.payment_status,

        "cod_confirmed": bool(
            order.cod_confirmed
        ),

        # Tomorrow Special order identify
        "is_tomorrow_special": any(
            item.special_id is not None
            for item in order.items
        ),

        "items": [
            {
                "id": (
                    str(item.id)
                    if item.id
                    else None
                ),

                "name": item.item_name,

                "quantity": item.quantity,

                "price": float(
                    item.price or 0
                ),

                "image": item.item_image,

                "special_id": (
                    str(item.special_id)
                    if item.special_id
                    else None
                ),

                "menu_id": (
                    str(item.menu_id)
                    if item.menu_id
                    else None
                ),

                "is_tomorrow_special": (
                    item.special_id is not None
                ),
            }
            for item in order.items
        ],
    }
# =========================
# ✅ CREATE ORDER
# =========================


from app.models.tomorrow_special import TomorrowSpecial




# =========================
# 🍽️ CREATE ORDER
# =========================

@router.post("/")
async def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    try:

        # =====================================================
        # 🔥 BASIC VALIDATION
        # =====================================================

        if data.payment_method not in [
            "cod",
            "card",
            "upi",
        ]:
            raise HTTPException(
                status_code=400,
                detail="Invalid payment method"
            )

        if not data.items:
            raise HTTPException(
                status_code=400,
                detail="Order must contain at least one item"
            )

        total_price = 0
        chef_id = None
        created_items = []

        # =====================================================
        # 🚀 FETCH ALL SPECIALS IN ONE QUERY
        # =====================================================

        special_ids = [
            item.special_id
            for item in data.items
            if item.special_id
        ]

        specials = {}

        if special_ids:

            special_list = (
                db.query(TomorrowSpecial)
                .filter(
                    TomorrowSpecial.id.in_(special_ids),
                    TomorrowSpecial.is_active == 1,
                )
                .all()
            )

            specials = {
                special.id: special
                for special in special_list
            }

        # =====================================================
        # 🚀 FETCH ALL MENUS IN ONE QUERY
        # =====================================================

        menu_ids = [
            item.menu_id
            for item in data.items
            if item.menu_id
        ]

        menus = {}

        if menu_ids:

            menu_list = (
                db.query(Menu)
                .filter(
                    Menu.id.in_(menu_ids),
                    Menu.is_available == True,
                    Menu.is_deleted == False,
                )
                .all()
            )

            menus = {
                menu.id: menu
                for menu in menu_list
            }

        # =====================================================
        # 🧾 CREATE ORDER
        # =====================================================

        order = Order(
            user_id=user.id,

            status="pending",

            customer_name=user.name,

            phone=user.phone,

            address=data.address,

            payment_method=data.payment_method,

            payment_status="pending",

            refund_status="pending",

            # 🔥 IMPORTANT
            # Subscription flag stored in DB
            is_subscription=bool(
                data.is_subscription
            ),
        )

        db.add(order)

        # Get UUID immediately
        db.flush()

        # =====================================================
        # 🔥 LOOP THROUGH ITEMS
        # =====================================================

        for item in data.items:

            # =================================================
            # ❗ MUST HAVE EXACTLY ONE ID
            # =================================================
            meal_type = None
            target_date = None

            if not item.menu_id and not item.special_id:

                raise HTTPException(
                    status_code=400,
                    detail="Invalid item"
                )

            if item.menu_id and item.special_id:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Item cannot contain both "
                        "menu_id and special_id"
                    )
                )

            # =================================================
            # 🍽️ NORMAL MENU ITEM
            # =================================================

            if item.menu_id:

                menu = menus.get(
                    item.menu_id
                )

                if menu is None:

                    raise HTTPException(
                        status_code=404,
                        detail=(
                            "Menu not found "
                            "or unavailable"
                        )
                    )

                # =============================================
                # 👨‍🍳 CHEF CONSISTENCY
                # =============================================

                if not chef_id:

                    chef_id = menu.chef_id

                elif chef_id != menu.chef_id:

                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Different chefs "
                            "not allowed"
                        )
                    )

                # =============================================
                # 📅 NORMAL CUSTOMER ORDER
                # =============================================

                if not data.is_subscription:

                    india_now = datetime.now(
                        INDIA_TZ
                    )

                    today = india_now.date()

                    # -----------------------------------------
                    # MEAL TYPE
                    # -----------------------------------------

                    meal_type = getattr(
                        item,
                        "meal_type",
                        None
                    )

                    if not meal_type:

                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "Meal type is required. "
                                "Use breakfast, lunch or dinner."
                            )
                        )

                    meal_type = str(
                        meal_type
                    ).lower().strip()

                    # -----------------------------------------
                    # VALID MEAL TYPE
                    # -----------------------------------------

                    cutoff_times = {
                        "breakfast": "09:00",
                        "lunch": "13:00",
                        "dinner": "20:00",
                    }

                    if meal_type not in cutoff_times:

                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "Invalid meal type. "
                                "Use breakfast, lunch or dinner."
                            )
                        )

                    # -----------------------------------------
                    # MENU DATE
                    # -----------------------------------------

                    requested_menu_date = getattr(
                        item,
                        "menu_date",
                        None
                    )

                    if requested_menu_date:

                        if isinstance(
                            requested_menu_date,
                            datetime
                        ):

                            target_date = (
                                requested_menu_date.date()
                            )

                        elif isinstance(
                            requested_menu_date,
                            date
                        ):

                            target_date = (
                                requested_menu_date
                            )

                        else:

                            try:

                                target_date = (
                                    datetime.fromisoformat(
                                        str(
                                            requested_menu_date
                                        ).replace(
                                            "Z",
                                            "+00:00"
                                        )
                                    ).date()
                                )

                            except Exception:

                                try:

                                    target_date = (
                                        date.fromisoformat(
                                            str(
                                                requested_menu_date
                                            )
                                        )
                                    )

                                except Exception:

                                    raise HTTPException(
                                        status_code=400,
                                        detail=(
                                            "Invalid menu date"
                                        )
                                    )

                    else:

                        target_date = today

                    # -----------------------------------------
                    # 🚫 UPCOMING DATE
                    # -----------------------------------------

                    if target_date > today:

                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "This meal is upcoming. "
                                "You can view it, but ordering "
                                "is not available yet."
                            )
                        )

                    # -----------------------------------------
                    # 🚫 PAST DATE
                    # -----------------------------------------

                    if target_date < today:

                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "Past menu dates are closed."
                            )
                        )

                    # -----------------------------------------
                    # 📅 MENU CYCLE VALIDATION
                    # -----------------------------------------

                    scheduled_menu_id = (
                        get_today_menu_for_chef(
                            db=db,
                            chef_id=menu.chef_id,
                            requested_menu_id=menu.id,
                            target_date=today,
                        )
                    )

                    if scheduled_menu_id is None:

                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "No menu is scheduled "
                                "for this chef today"
                            )
                        )

                    if scheduled_menu_id != menu.id:

                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "This menu is not available "
                                "for ordering today. "
                                "Please select today's menu."
                            )
                        )

                    # -----------------------------------------
                    # ⏰ MEAL CUTOFF
                    # -----------------------------------------

                    cutoff_datetime = datetime.strptime(
                        f"{today} "
                        f"{cutoff_times[meal_type]}",
                        "%Y-%m-%d %H:%M",
                    ).replace(
                        tzinfo=INDIA_TZ
                    )

                    if india_now >= cutoff_datetime:

                        display_cutoff = (
                            cutoff_datetime.strftime(
                                "%I:%M %p"
                            ).lstrip("0")
                        )

                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"{meal_type.capitalize()} "
                                f"ordering is closed for today. "
                                f"Order by {display_cutoff}."
                            )
                        )

                # =============================================
                # 📦 QUANTITY VALIDATION
                # =============================================

                if item.quantity <= 0:

                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Quantity must be "
                            "greater than zero"
                        )
                    )

                # =============================================
                # 📦 STOCK
                # =============================================

                if not data.is_subscription:

                    if menu.quantity is None:

                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "Menu quantity "
                                "is not configured"
                            )
                        )

                    if menu.quantity < item.quantity:

                        raise HTTPException(
                            status_code=400,
                            detail="Out of stock"
                        )

                    menu.quantity -= item.quantity

                # =============================================
                # 💰 PRICE
                # =============================================

                price = (
                    menu.price
                    * item.quantity
                )

                total_price += price

                # =============================================
                # 🧾 ORDER ITEM SNAPSHOT
                # =============================================

                db.add(
                    OrderItem(
                        order_id=order.id,

                        menu_id=menu.id,

                        quantity=item.quantity,

                        price=price,

                        item_name=menu.name,

                        item_image=(
                            menu.image_urls[0]
                            if menu.image_urls
                            else None
                        ),

                        meal_type=meal_type,

                        menu_date=target_date,
                    )
                )

                created_items.append(
                    {
                        "name": menu.name,

                        "quantity": item.quantity,

                        "price": price,

                        "image": (
                            menu.image_urls[0]
                            if menu.image_urls
                            else None
                        ),

                        "menu_id": str(
                            menu.id
                        ),

                        "is_tomorrow_special": False,
                    }
                )

            # =================================================
            # 🍽️ TOMORROW SPECIAL
            # =================================================

            elif item.special_id:

                special = specials.get(
                    item.special_id
                )

                if special is None:

                    raise HTTPException(
                        status_code=404,
                        detail=(
                            "Special not found "
                            "or unavailable"
                        )
                    )

                # =============================================
                # QUANTITY VALIDATION
                # =============================================

                if item.quantity <= 0:

                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Quantity must be "
                            "greater than zero"
                        )
                    )

                # =============================================
                # ⏰ TOMORROW SPECIAL CUTOFF
                # =============================================

                try:

                    if not special.special_date:

                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "Special date "
                                "is not configured"
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

                        display_cutoff = (
                            cutoff_datetime.strftime(
                                "%I:%M %p"
                            ).lstrip("0")
                        )

                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "Tomorrow Special "
                                "ordering closed. "
                                f"Order by {display_cutoff}"
                            )
                        )

                except HTTPException:

                    raise

                except Exception:

                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Invalid special date "
                            "or cutoff time"
                        )
                    )

                # =============================================
                # 📦 SPECIAL STOCK
                # =============================================

                remaining = (
                    special.max_plates
                    - special.pre_orders
                )

                if remaining < item.quantity:

                    raise HTTPException(
                        status_code=400,
                        detail="Out of stock"
                    )

                special.pre_orders += (
                    item.quantity
                )

                # =============================================
                # 👨‍🍳 CHEF CONSISTENCY
                # =============================================

                if not chef_id:

                    chef_id = special.chef_id

                elif chef_id != special.chef_id:

                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Different chefs "
                            "not allowed"
                        )
                    )

                # =============================================
                # 💰 PRICE
                # =============================================

                price = (
                    special.price
                    * item.quantity
                )

                total_price += price

                # =============================================
                # 🧾 ORDER ITEM SNAPSHOT
                # =============================================

                db.add(
                    OrderItem(
                        order_id=order.id,

                        special_id=special.id,

                        quantity=item.quantity,

                        price=price,

                        item_name=special.dish_name,

                        item_image=special.image_url,
                    )
                )

                db.add(
                    TomorrowSpecialPreOrder(
                        special_id=special.id,

                        order_id=order.id,

                        customer_id=user.id,

                        quantity=item.quantity,

                        unit_price=float(
                            special.price
                        ),

                        total_amount=float(
                            price
                        ),
                    )
                )

                created_items.append(
                    {
                        "name": special.dish_name,

                        "quantity": item.quantity,

                        "price": price,

                        "image": special.image_url,

                        "special_id": str(
                            special.id
                        ),

                        "is_tomorrow_special": True,
                    }
                )

        # =====================================================
        # ❗ CHEF MUST EXIST
        # =====================================================

        if chef_id is None:

            raise HTTPException(
                status_code=400,
                detail="Unable to determine chef"
            )

        # =====================================================
        # 🔥 SUBSCRIPTION PRICE
        # =====================================================
        #
        # CURRENT FLOW:
        # Subscription frontend sends amount.
        #
        # IMPORTANT:
        # Later we will make this backend-calculated
        # using subscription plan ID.
        #
        # Do NOT change breakfast logic here.
        # =====================================================

        if data.is_subscription:

            if data.amount is None:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Subscription order "
                        "amount is required"
                    )
                )

            if data.amount < 0:

                raise HTTPException(
                    status_code=400,
                    detail="Invalid subscription amount"
                )

            total_price = float(
                data.amount
            )

        # =====================================================
        # 🔥 FINAL ORDER UPDATE
        # =====================================================

        order.total_price = (
            total_price
        )

        order.chef_id = chef_id

        order.is_subscription = bool(
            data.is_subscription
        )

        # =====================================================
        # 💾 COMMIT
        # =====================================================

        db.commit()

        # =====================================================
        # 🧹 CUSTOMER ORDER CACHE
        # =====================================================

        delete_cache(
            f"orders:v1:user:{user.id}"
        )

        # =====================================================
        # 🧹 CHEF DASHBOARD CACHE
        # =====================================================

        try:

            delete_cache(
                f"dashboard:{chef_id}"
            )

        except Exception as cache_error:

            print(
                "⚠️ DASHBOARD CACHE DELETE ERROR:",
                str(cache_error)
            )

        # =====================================================
        # 🔄 REFRESH
        # =====================================================

        db.refresh(order)

        # =====================================================
        # 🇮🇳 UTC → INDIA TIME
        # =====================================================

        created_at = order.created_at

        if created_at:

            if created_at.tzinfo is None:

                created_at = (
                    created_at.replace(
                        tzinfo=ZoneInfo("UTC")
                    )
                )

            created_at = (
                created_at.astimezone(
                    ZoneInfo("Asia/Kolkata")
                )
            )

        # =====================================================
        # ✅ RESPONSE
        # =====================================================

        return {

            "id": str(
                order.id
            ),

            "status": order.status,

            "total_price": float(
                order.total_price or 0
            ),

            "created_at": (
                created_at.isoformat()
                if created_at
                else None
            ),

            "customer_name": (
                order.customer_name
            ),

            "phone": order.phone,

            "address": order.address,

            "payment_method": (
                order.payment_method
            ),

            "payment_status": (
                order.payment_status
            ),

            "items": created_items,

            "cod_confirmed": bool(
                order.cod_confirmed
            ),

            "is_subscription": bool(
                order.is_subscription
            ),

            "is_tomorrow_special": any(
                item.special_id is not None
                for item in order.items
            ),

            "chef_id": (
                str(order.chef_id)
                if order.chef_id
                else None
            ),
        }

    # =========================================================
    # 🔥 EXPECTED HTTP ERROR
    # =========================================================

    except HTTPException:

        db.rollback()

        raise

    # =========================================================
    # ❌ UNEXPECTED ERROR
    # =========================================================

    except Exception as e:

        db.rollback()

        print(
            "❌ ORDER ERROR:",
            repr(e)
        )

        raise HTTPException(
            status_code=500,
            detail="Order creation failed"
        )
    
# =========================
# 💵 CONFIRM COD ORDER
# =========================

@router.post("/{order_id}/confirm-cod")
async def confirm_cod_order(
    order_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    try:
        # =========================
        # UUID VALIDATION
        # =========================
        try:
            order_uuid = UUID(order_id)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid order ID"
            )

        # =========================
        # FIND CUSTOMER ORDER
        # =========================
        order = (
            db.query(Order)
            .options(selectinload(Order.items))
            .filter(
                Order.id == order_uuid,
                Order.user_id == user.id
            )
            .first()
        )

        if not order:
            raise HTTPException(
                status_code=404,
                detail="Order not found"
            )

        # =========================
        # COD CHECK
        # =========================
        if order.payment_method != "cod":
            raise HTTPException(
                status_code=400,
                detail="This is not a COD order"
            )

        # =========================
        # DUPLICATE CHECK
        # =========================
        if order.cod_confirmed:
            raise HTTPException(
                status_code=400,
                detail="COD order already confirmed"
            )

        # =========================
        # CHECK CHEF
        # =========================
        if not order.chef_id:
            raise HTTPException(
                status_code=400,
                detail="Chef not assigned to this order"
            )

        # =========================
        # CONFIRM ORDER
        # =========================
        order.cod_confirmed = True
        order.status = "pending"

        # =========================
        # CUSTOMER NOTIFICATION
        # =========================
        db.add(
            Notification(
                user_id=order.user_id,
                type="order",
                title="Order Confirmed",
                message=(
                    f"Your COD order for ₹{order.total_price} "
                    f"has been confirmed successfully."
                )
            )
        )
        is_tomorrow_special = any(
           item.special_id is not None
           for item in order.items
        )
        
        db.add(
            Notification(
                user_id=order.chef_id,
                type="order",
                title=(
                   "New Tomorrow Special Order"
                     if is_tomorrow_special
                     else "New Order Received"
                    ),

                message=(
                    f"You received a "
                    f"{'Tomorrow Special ' if is_tomorrow_special else ''}"
                    f"COD order of ₹{order.total_price}"
                )
            )
        )

        # =========================
        # COMMIT CORE ORDER
        # =========================
        db.commit()
        db.refresh(order)
        delete_cache(f"orders:v1:user:{order.user_id}")

        # =========================
        # CLEAR CART
        # =========================
        try:
            cart = (
                db.query(Cart)
                .filter(Cart.user_id == order.user_id)
                .first()
            )

            if cart:
                db.query(CartItem).filter(
                    CartItem.cart_id == cart.id
                ).delete(
                    synchronize_session=False
                )

                db.delete(cart)
                db.commit()

        except Exception as cart_error:
            db.rollback()
            print(
                "⚠️ CART CLEAR ERROR:",
                str(cart_error)
            )

        # =========================
        # WHATSAPP
        # =========================
        try:
            items_text = ", ".join(
                f"{item.item_name} x{item.quantity}"
                for item in order.items
            )

            print(
                "📱 SENDING COD ORDER WHATSAPP | "
                f"order_id={order.id} | "
                f"customer={order.customer_name} | "
                f"items={items_text}"
            )

            whatsapp_result = await send_new_order_whatsapp(
                order_id=str(order.id),
                customer_name=order.customer_name,
                amount=float(order.total_price),
                items=items_text
            )

            print(
                "✅ COD ORDER WHATSAPP RESULT:",
                whatsapp_result
            )

        except Exception as whatsapp_error:
            print(
                "⚠️ COD WHATSAPP ERROR:",
                str(whatsapp_error)
            )

        # =========================
        # CHEF CACHE
        # =========================
        try:
            if order.chef_id:
                delete_cache(
                    f"dashboard:{order.chef_id}"
                )
        except Exception as cache_error:
            print(
                "⚠️ CACHE ERROR:",
                str(cache_error)
            )

        # =========================
        # SUCCESS
        # =========================
        return {
            "status": "success",
            "message": "COD order confirmed",

            "order_id": str(order.id),

            "cod_confirmed": True,

            "order_status": order.status,

            "chef_id": (
                str(order.chef_id)
                if order.chef_id
                else None
               ),

            "is_tomorrow_special": any(
               item.special_id is not None
               for item in order.items
            ),

            "total_price": float(
              order.total_price or 0
               )
             }

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()

        print(
            "❌ COD CONFIRM ERROR:",
            repr(e)
        )

        raise HTTPException(
            status_code=500,
            detail=f"COD confirmation failed: {str(e)}"
        )
# =========================
# 💳 CREATE PAYMENT
# =========================
from pydantic import BaseModel
import requests
import os
import base64

class PaymentCreate(BaseModel):
    order_id: str


from uuid import UUID
from fastapi import Depends, HTTPException
import requests
import os
import base64

@router.post("/create-payment")
def create_payment(
    data: PaymentCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    try:
        # =========================
        # 🔥 UUID VALIDATION
        # =========================
        try:
            order_uuid = UUID(data.order_id)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid order ID"
            )

        # =========================
        # 🔥 FETCH ORDER SECURELY
        # =========================
        order = (
            db.query(Order)
            .filter(
                Order.id == order_uuid,
                Order.user_id == user.id
            )
            .first()
        )

        if not order:
            raise HTTPException(
                status_code=404,
                detail="Order not found"
            )

        # =========================
        # 🔥 PAYMENT STATUS CHECK
        # =========================
        if order.payment_status == "paid":
            raise HTTPException(
                status_code=400,
                detail="Already paid"
            )

        # =========================
        # 🔥 ORDER STATUS CHECK
        # =========================
        if order.status not in ["pending", "created"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid order state"
            )

        # =========================
        # 💰 AMOUNT
        # =========================
        amount = int(round(float(order.total_price or 0) * 100))

        if amount < 100:
            raise HTTPException(
                status_code=400,
                detail="Minimum ₹1 required"
            )

        # =========================
        # 🔑 RAZORPAY KEYS
        # =========================
        key_id = os.getenv("RAZORPAY_KEY_ID")
        key_secret = os.getenv("RAZORPAY_KEY_SECRET")

        if not key_id or not key_secret:
            raise HTTPException(
                status_code=500,
                detail="Razorpay keys missing"
            )

        # =====================================================
        # 🔥 REUSE EXISTING RAZORPAY ORDER
        # =====================================================
        # Agar same internal order ke liye Razorpay order
        # already create ho chuka hai, naya Razorpay order
        # unnecessarily create nahi karenge.
        if order.razorpay_order_id:
            return {
                "razorpay_order_id": order.razorpay_order_id,
                "amount": amount,
                "key": key_id
            }

        # =========================
        # 🔐 BASIC AUTH
        # =========================
        auth = base64.b64encode(
            f"{key_id}:{key_secret}".encode()
        ).decode()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth}"
        }

        # =========================
        # 💳 RAZORPAY ORDER
        # =========================
        payload = {
            "amount": amount,
            "currency": "INR",
            "receipt": str(order.id)
        }

        # =========================
        # 🔥 RAZORPAY API CALL
        # =========================
        res = requests.post(
            "https://api.razorpay.com/v1/orders",
            json=payload,
            headers=headers,
            timeout=10
        )

        if res.status_code != 200:
            print(
                "❌ RAZORPAY CREATE ORDER ERROR:",
                res.text
            )

            raise HTTPException(
                status_code=500,
                detail="Payment gateway error"
            )

        payment = res.json()

        razorpay_order_id = payment.get("id")

        if not razorpay_order_id:
            raise HTTPException(
                status_code=500,
                detail="Razorpay order ID missing"
            )

        # =====================================================
        # 💾 SAVE RAZORPAY ORDER ID
        # =====================================================
        order.razorpay_order_id = razorpay_order_id

        db.commit()
        db.refresh(order)

        # =========================
        # ✅ RESPONSE
        # =========================
        return {
            "razorpay_order_id": razorpay_order_id,
            "amount": payment["amount"],
            "key": key_id
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "❌ RAZORPAY CREATE PAYMENT ERROR:",
            repr(e)
        )

        raise HTTPException(
            status_code=500,
            detail="Payment init failed"
        )
# =========================
# 💰 VERIFY PAYMENT (IMPORTANT 🔥)
# =========================
import hmac
import hashlib

from uuid import UUID
from fastapi import Depends, HTTPException
import hmac
import hashlib
import os

# =========================
# 💰 VERIFY PAYMENT (IMPORTANT 🔥)
# =========================

import hmac
import hashlib
import os

from uuid import UUID
from fastapi import Depends, HTTPException


# =========================================================
# 💰 VERIFY PAYMENT
# =========================================================

@router.post("/verify-payment")
async def verify_payment(
    data: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    try:

        # =====================================================
        # 🔑 RAZORPAY SECRET
        # =====================================================

        key_secret = os.getenv(
            "RAZORPAY_KEY_SECRET"
        )

        if not key_secret:
            raise HTTPException(
                status_code=500,
                detail="Razorpay key missing"
            )

        # =====================================================
        # 🔎 REQUIRED DATA
        # =====================================================

        razorpay_order_id = data.get(
            "razorpay_order_id"
        )

        razorpay_payment_id = data.get(
            "razorpay_payment_id"
        )

        razorpay_signature = data.get(
            "razorpay_signature"
        )

        order_id = data.get(
            "order_id"
        )

        # =====================================================
        # VALIDATION
        # =====================================================

        if not razorpay_order_id:
            raise HTTPException(
                status_code=400,
                detail="Razorpay order ID is required"
            )

        if not razorpay_payment_id:
            raise HTTPException(
                status_code=400,
                detail="Razorpay payment ID is required"
            )

        if not razorpay_signature:
            raise HTTPException(
                status_code=400,
                detail="Razorpay signature is required"
            )

        if not order_id:
            raise HTTPException(
                status_code=400,
                detail="Order ID is required"
            )

        # =====================================================
        # 🔐 VERIFY RAZORPAY SIGNATURE
        # =====================================================

        body = (
            f"{razorpay_order_id}|"
            f"{razorpay_payment_id}"
        )

        generated_signature = hmac.new(
            key_secret.encode(),
            body.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(
            generated_signature,
            razorpay_signature
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid signature"
            )

        # =====================================================
        # 🔥 UUID
        # =====================================================

        try:

            order_uuid = UUID(order_id)

        except Exception:

            raise HTTPException(
                status_code=400,
                detail="Invalid order ID"
            )

        # =====================================================
        # 🔐 FETCH ORDER
        # =====================================================

        order = (
            db.query(Order)
            .filter(
                Order.id == order_uuid,
                Order.user_id == user.id
            )
            .first()
        )

        if not order:

            raise HTTPException(
                status_code=404,
                detail="Order not found"
            )

        # =====================================================
        # 🔐 RAZORPAY ORDER MATCH
        # =====================================================

        if (
            order.razorpay_order_id
            != razorpay_order_id
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Razorpay order does not "
                    "match this order"
                )
            )

        # =====================================================
        # 🔥 DUPLICATE PAYMENT
        # =====================================================

        if order.payment_status == "paid":

            raise HTTPException(
                status_code=400,
                detail="Already verified"
            )

        # =====================================================
        # 💳 MARK PAYMENT PAID
        # =====================================================

        order.payment_status = "paid"

        order.payment_id = (
            razorpay_payment_id
        )

        order.status = "pending"

        # =====================================================
        # 🔎 TOMORROW SPECIAL
        # =====================================================

        is_tomorrow_special = any(
            item.special_id is not None
            for item in order.items
        )

        # =====================================================
        # 🔔 CUSTOMER PAYMENT NOTIFICATION
        # =====================================================

        db.add(
            Notification(
                user_id=order.user_id,
                type="payment",
                title="Payment Successful",
                message=(
                    f"Payment of ₹"
                    f"{order.total_price} "
                    f"received successfully."
                )
            )
        )

        # =====================================================
        # 🔔 CUSTOMER ORDER NOTIFICATION
        # =====================================================

        db.add(
            Notification(
                user_id=order.user_id,
                type="order",
                title="Order Placed",
                message=(
                    f"Your order for ₹"
                    f"{order.total_price} "
                    f"has been placed successfully."
                )
            )
        )

        # =====================================================
        # 🔔 CHEF NOTIFICATION
        # =====================================================

        if order.chef_id:

            db.add(
                Notification(
                    user_id=order.chef_id,
                    type="order",
                    title=(
                        "New Tomorrow Special Order"
                        if is_tomorrow_special
                        else "New Order Received"
                    ),
                    message=(
                        f"You received a "
                        f"{'Tomorrow Special '
                         if is_tomorrow_special
                         else ''}"
                        f"paid order of "
                        f"₹{order.total_price}"
                    )
                )
            )

        # =====================================================
        # 🎁 REFERRAL REWARD
        # =====================================================
        #
        # ONLY:
        # Normal single tiffin
        #
        # NOT:
        # Subscription
        # Tomorrow Special
        # Multiple items
        #
        # Reward = ₹1
        #
        # IMPORTANT:
        # This is the ONLY place where the
        # online payment referral reward is triggered.
        # =====================================================

        referral_reward_given = False

        if (
            not getattr(
                order,
                "is_subscription",
                False
            )
            and order.payment_status == "paid"
        ):

            referral_reward_given = (
                process_single_tiffin_referral_reward(
                    db=db,
                    order=order
                )
            )

        # =====================================================
        # 🛒 CLEAR CART
        # =====================================================

        cart = (
            db.query(Cart)
            .filter(
                Cart.user_id == order.user_id
            )
            .first()
        )

        if cart:

            db.query(CartItem).filter(
                CartItem.cart_id == cart.id
            ).delete(
                synchronize_session=False
            )

            db.delete(cart)

        # =====================================================
        # 💾 ATOMIC COMMIT
        # =====================================================
        #
        # Payment
        # Order
        # Notifications
        # Referral reward
        # Wallet
        # Wallet transaction
        # Referral status
        #
        # ALL TOGETHER
        # =====================================================

        db.commit()

        # =====================================================
        # 🧹 CLEAR CACHE
        # =====================================================

        delete_cache(
            f"orders:v1:user:{order.user_id}"
        )

        # =====================================================
        # 📱 WHATSAPP
        # =====================================================

        try:

            items_text = ", ".join(
                f"{item.item_name} x{item.quantity}"
                for item in order.items
            )

            whatsapp_result = (
                await send_new_order_whatsapp(
                    order_id=str(order.id),
                    customer_name=order.customer_name,
                    amount=float(
                        order.total_price
                    ),
                    items=items_text,
                )
            )

            print(
                "✅ PAID ORDER WHATSAPP RESULT:",
                whatsapp_result
            )

        except Exception as whatsapp_error:

            print(
                "⚠️ PAID ORDER WHATSAPP ERROR:",
                str(whatsapp_error)
            )

        # =====================================================
        # ✅ RESPONSE
        # =====================================================

        return {
            "msg": "Payment success",

            "order_id": str(
                order.id
            ),

            "payment_status": "paid",

            "referral_reward_given": (
                referral_reward_given
            )
        }

    # =========================================================
    # HTTP EXCEPTION
    # =========================================================

    except HTTPException:

        db.rollback()

        raise

    # =========================================================
    # UNEXPECTED ERROR
    # =========================================================

    except Exception as e:

        db.rollback()

        print(
            "❌ VERIFY ERROR:",
            repr(e)
        )

        raise HTTPException(
            status_code=400,
            detail="Payment failed"
        )
# =========================
# 🔄 UPDATE STATUS
# =========================
from uuid import UUID
from fastapi import Depends, HTTPException
from datetime import datetime

# =========================================================
# 🔄 UPDATE ORDER STATUS
# =========================================================

# =========================================================
# 🔄 UPDATE ORDER STATUS
# =========================================================

@router.put("/{order_id}/status")
def update_status(
    order_id: str,
    status: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    # =====================================================
    # UUID VALIDATION
    # =====================================================

    try:

        order_uuid = UUID(order_id)

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Invalid order ID"
        )

    # =====================================================
    # 🔐 FETCH ORDER
    # ONLY ASSIGNED CHEF
    # =====================================================

    order = (
        db.query(Order)
        .filter(
            Order.id == order_uuid,
            Order.chef_id == user.id
        )
        .first()
    )

    if not order:

        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    # =====================================================
    # VALID STATUS
    # =====================================================

    valid_status = [
        "pending",
        "accepted",
        "preparing",
        "ready",
        "out_for_delivery",
        "delivered",
        "cancelled",
    ]

    if status not in valid_status:

        raise HTTPException(
            status_code=400,
            detail="Invalid status"
        )

    # =====================================================
    # OLD STATUS
    # =====================================================

    old_status = order.status

    if old_status == status:

        return {
            "msg": "already updated",
            "status": status,
            "referral_reward_given": False,
            "referral_reward_reversed": False,
        }

    # =====================================================
    # ALLOWED TRANSITIONS
    # =====================================================

    allowed_transitions = {

        "pending": [
            "accepted",
            "cancelled",
        ],

        "accepted": [
            "preparing",
            "cancelled",
        ],

        "preparing": [
            "ready",
        ],

        "ready": [
            "out_for_delivery",
        ],

        "out_for_delivery": [
            "delivered",
        ],

        "delivered": [],

        "cancelled": [],
    }

    if status not in allowed_transitions.get(
        old_status,
        []
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot change status "
                f"from {old_status} to {status}"
            )
        )

    # =====================================================
    # 🔥 UPDATE STATUS
    # =====================================================

    order.status = status

    # =====================================================
    # 🔔 NOTIFICATIONS
    # =====================================================

    if status == "accepted":

        db.add(
            Notification(
                user_id=order.user_id,
                type="order",
                title="Order Accepted",
                message=(
                    "Your order has been accepted "
                    "by the chef."
                ),
            )
        )

    if status == "preparing":

        db.add(
            Notification(
                user_id=order.user_id,
                type="order",
                title="Preparing Your Food",
                message=(
                    "Chef has started preparing "
                    "your food."
                ),
            )
        )

    if status == "ready":

        db.add(
            Notification(
                user_id=order.user_id,
                type="order",
                title="Food Ready",
                message=(
                    "Your food is ready and "
                    "waiting for pickup."
                ),
            )
        )

    if status == "out_for_delivery":

        db.add(
            Notification(
                user_id=order.user_id,
                type="delivery",
                title="Out For Delivery",
                message=(
                    "Your order is on the way."
                ),
            )
        )

    if status == "delivered":

        db.add(
            Notification(
                user_id=order.user_id,
                type="order",
                title="Order Delivered",
                message=(
                    "Enjoy your meal! Your order "
                    "has been delivered."
                ),
            )
        )

    if status == "cancelled":

        db.add(
            Notification(
                user_id=order.user_id,
                type="order",
                title="Order Cancelled",
                message=(
                    "Your order has been cancelled."
                ),
            )
        )

    # =====================================================
    # 💸 CANCEL → REFUND INIT
    # =====================================================

    referral_reward_reversed = False

    if status == "cancelled":

        order.refund_status = "processing"

        order.refund_amount = (
            order.total_price
        )

        order.refund_date = datetime.utcnow()

        # =================================================
        # 🔄 REVERSE REFERRAL REWARD
        # =================================================
        #
        # If ₹1 referral reward was already given
        # for this order, remove it.
        #
        # This happens before commit so:
        #
        # Order cancellation
        # +
        # Wallet reversal
        # +
        # Referral reset
        #
        # are atomic.
        # =================================================

        try:

            referral_reward_reversed = (
                reverse_single_tiffin_referral_reward(
                    db=db,
                    order=order,
                )
            )

        except Exception as referral_error:

            print(
                "❌ REFERRAL REVERSAL ERROR:",
                repr(referral_error)
            )

            db.rollback()

            raise HTTPException(
                status_code=500,
                detail=(
                    "Order cancellation failed "
                    "because referral reward "
                    "could not be reversed."
                )
            )

        # =================================================
        # 🍽️ TOMORROW SPECIAL STOCK RELEASE
        # =================================================

        tomorrow_special_items = (
            db.query(OrderItem)
            .filter(
                OrderItem.order_id == order.id,
                OrderItem.special_id.isnot(None),
            )
            .all()
        )

        for item in tomorrow_special_items:

            special = (
                db.query(TomorrowSpecial)
                .filter(
                    TomorrowSpecial.id
                    == item.special_id
                )
                .first()
            )

            if special:

                special.pre_orders = max(
                    0,
                    special.pre_orders
                    - item.quantity
                )

    # =====================================================
    # 💰 DELIVERED → CHEF EARNING
    # =====================================================

    if (
        status == "delivered"
        and old_status != "delivered"
    ):

        db.add(
            Earning(
                chef_id=order.chef_id,
                amount=order.total_price
            )
        )

    # =====================================================
    # ❌ IMPORTANT
    #
    # NO REFERRAL REWARD HERE
    #
    # Referral reward is already handled inside
    # verify_payment().
    #
    # Therefore delivered status will NEVER
    # create another ₹1 reward.
    # =====================================================

    # =====================================================
    # 💾 ONE ATOMIC COMMIT
    # =====================================================

    db.commit()

    # =====================================================
    # 🧹 CACHE CLEAR
    # =====================================================

    delete_cache(
        f"dashboard:{order.chef_id}"
    )

    delete_cache(
        f"orders:v1:user:{order.user_id}"
    )

    # =====================================================
    # RESPONSE
    # =====================================================

    return {
        "msg": "updated",

        "status": status,

        "referral_reward_given": False,

        "referral_reward_reversed": (
            referral_reward_reversed
        ),
    }


@router.put("/{order_id}/refund-complete")
def complete_refund(
    order_id: str,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)   # 🔥 ADD
):
    try:
        order_uuid = UUID(order_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid order ID")

    order = db.query(Order).filter(
        Order.id == order_uuid,
        Order.chef_id == user.id   # 🔥 ONLY CHEF
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # =========================
    # 🔥 CHECK STATUS
    # =========================
    if order.refund_status != "processing":
        raise HTTPException(status_code=400, detail="Refund not in processing state")

    order.refund_status = "completed"

    db.commit()

    return {"msg": "Refund completed"}


# =========================================================
# CUSTOMER - TODAY ORDERS
# =========================================================

@router.get("/customer/today")
def get_today_orders(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    today = datetime.now(INDIA_TZ).date()

    orders = (
        db.query(Order)
        .filter(
            Order.user_id == user.id,
            func.date(Order.created_at) == today,
        )
        .order_by(Order.created_at.desc())
        .all()
    )

    return [
        {
            "id": str(order.id),
            "status": order.status,
            "total_price": order.total_price,
            "customer_name": order.customer_name,
            "phone": order.phone,
            "address": order.address,
            "payment_method": order.payment_method,
            "payment_status": order.payment_status,
            "created_at": (
                order.created_at.isoformat()
                if order.created_at
                else None
            ),
            "items": [
                {
                    "name": item.item_name,
                    "quantity": item.quantity,
                    "price": item.price,
                    "image": item.item_image,
                }
                for item in order.items
            ],
        }
        for order in orders
    ]


# =========================================================
# CUSTOMER - UPCOMING ORDERS
# =========================================================

@router.get("/customer/upcoming")
def get_upcoming_orders(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    today = datetime.now(INDIA_TZ).date()

    orders = (
        db.query(Order)
        .filter(
            Order.user_id == user.id,
            func.date(Order.created_at) > today,
        )
        .order_by(Order.created_at.asc())
        .all()
    )

    return [
        {
            "id": str(order.id),
            "status": order.status,
            "total_price": order.total_price,
            "customer_name": order.customer_name,
            "phone": order.phone,
            "address": order.address,
            "payment_method": order.payment_method,
            "payment_status": order.payment_status,
            "created_at": (
                order.created_at.isoformat()
                if order.created_at
                else None
            ),
            "items": [
                {
                    "name": item.item_name,
                    "quantity": item.quantity,
                    "price": item.price,
                    "image": item.item_image,
                }
                for item in order.items
            ],
        }
        for order in orders
    ]


# =========================================================
# CUSTOMER - PAST ORDERS
# =========================================================

@router.get("/customer/past")
def get_past_orders(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    today = datetime.now(INDIA_TZ).date()

    orders = (
        db.query(Order)
        .filter(
            Order.user_id == user.id,
            func.date(Order.created_at) < today,
        )
        .order_by(Order.created_at.desc())
        .all()
    )

    return [
        {
            "id": str(order.id),
            "status": order.status,
            "total_price": order.total_price,
            "customer_name": order.customer_name,
            "phone": order.phone,
            "address": order.address,
            "payment_method": order.payment_method,
            "payment_status": order.payment_status,
            "refund_status": order.refund_status,
            "refund_amount": order.refund_amount,
            "refund_date": (
                order.refund_date.isoformat()
                if order.refund_date
                else None
            ),
            "created_at": (
                order.created_at.isoformat()
                if order.created_at
                else None
            ),
            "items": [
                {
                    "name": item.item_name,
                    "quantity": item.quantity,
                    "price": item.price,
                    "image": item.item_image,
                }
                for item in order.items
            ],
        }
        for order in orders
    ]