from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
import cloudinary.uploader
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
import logging
from app.models.order import Order
from app.models.tomorrow_special_pre_order import TomorrowSpecialPreOrder
from app.models.order_item import OrderItem
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

# =========================================================
# 🍱 TOMORROW SPECIAL PRE-ORDER
# =========================================================

@router.post("/pre-order")
def create_pre_order(
    data: PreOrderCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # =====================================================
    # 🔐 CUSTOMER CHECK
    # =====================================================

    if user.role != "customer":
        raise HTTPException(
            status_code=403,
            detail="Only customers can place pre-orders",
        )

    # =====================================================
    # 🔎 LOCK SPECIAL ROW
    # Prevent two customers from overselling plates
    # =====================================================

    special = (
        db.query(TomorrowSpecial)
        .filter(
            TomorrowSpecial.id == data.special_id
        )
        .with_for_update()
        .first()
    )

    if not special:
        raise HTTPException(
            status_code=404,
            detail="Special not found",
        )

    # =====================================================
    # 📦 QUANTITY VALIDATION
    # =====================================================

    if data.quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be at least 1",
        )

    # =====================================================
    # ✅ ACTIVE CHECK
    # =====================================================

    if special.is_active == 0:
        raise HTTPException(
            status_code=400,
            detail="Tomorrow Special is not active",
        )

    # =====================================================
    # 📅 DATE VALIDATION
    # =====================================================

    if not special.special_date:
        raise HTTPException(
            status_code=400,
            detail="Special date is not configured",
        )

    # =====================================================
    # ⏰ CUTOFF VALIDATION
    # =====================================================

    if not special.cutoff_time:
        raise HTTPException(
            status_code=400,
            detail="Special ordering time is not configured",
        )

    try:
        cutoff_datetime = datetime.strptime(
            f"{special.special_date} {special.cutoff_time}",
            "%Y-%m-%d %H:%M",
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
                    "Tomorrow Special ordering closed. "
                    f"Order by {special.cutoff_time}"
                ),
            )

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid special date or cutoff time",
        )

    # =====================================================
    # 📦 AVAILABLE PLATES
    # =====================================================

    current_pre_orders = (
        special.pre_orders or 0
    )

    remaining = (
        special.max_plates
        - current_pre_orders
    )

    if data.quantity > remaining:
        raise HTTPException(
            status_code=400,
            detail=f"Only {remaining} plates left",
        )

    # =====================================================
    # 💰 PRICE SNAPSHOT
    # =====================================================

    unit_price = float(
        special.price
    )

    total_price = round(
        unit_price * data.quantity,
        2,
    )

    # =====================================================
    # 👨‍🍳 CHEF
    # =====================================================

    chef_id = special.chef_id

    if not chef_id:
        raise HTTPException(
            status_code=400,
            detail="Chef is not assigned to this special",
        )

    # =====================================================
    # 🧾 CREATE ORDER
    #
    # Payment initially pending.
    # Existing payment/COD flow can update this order.
    # =====================================================

    order = Order(
        user_id=user.id,
        chef_id=chef_id,

        status="pending",

        total_price=total_price,

        created_at=datetime.utcnow(),

        customer_name=user.name,
        phone=user.phone,

        # Existing Tomorrow Special endpoint
        # does not receive address/payment method.
        address=None,
        payment_method="tomorrow_special",
        payment_status="pending",

        payment_id=None,

        cod_confirmed=False,

        refund_status="pending",
        refund_amount=None,
        refund_date=None,
    )

    db.add(order)

    # Flush gives us order.id before creating OrderItem.
    db.flush()

    # =====================================================
    # 🍱 CREATE ORDER ITEM
    # =====================================================

    order_item = OrderItem(
        order_id=order.id,

        menu_id=None,

        special_id=special.id,

        quantity=data.quantity,

        price=unit_price,

        item_name=special.dish_name,

        item_image=special.image_url,

        meal_type=None,

        menu_date=special.special_date,
    )
    
    pre_order = TomorrowSpecialPreOrder(
      special_id=special.id,
      order_id=order.id,
      customer_id=user.id,
      quantity=data.quantity,
      unit_price=unit_price,
      total_amount=total_price,
    )

    db.add(order_item)
    db.add(pre_order)

    # =====================================================
    # 🔥 UPDATE SPECIAL COUNTER
    # =====================================================

    special.pre_orders = (
        current_pre_orders
        + data.quantity
    )

    # =====================================================
    # 💾 COMMIT EVERYTHING TOGETHER
    # =====================================================

    try:
        db.commit()

    except Exception:
        db.rollback()

        logger.exception(
            "Tomorrow Special pre-order failed"
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to create pre-order",
        )

    # =====================================================
    # 🔄 REFRESH
    # =====================================================

    db.refresh(order)
    db.refresh(special)

    # =====================================================
    # 📦 FINAL REMAINING
    # =====================================================

    final_remaining = max(
        special.max_plates
        - special.pre_orders,
        0,
    )

    # =====================================================
    # ✅ RESPONSE
    # =====================================================

    return {
        "success": True,

        "msg": "Pre-order successful",

        "order_id": str(
            order.id
        ),

        "special_id": str(
            special.id
        ),

        "customer": {
            "id": str(
                user.id
            ),

            "name": user.name,

            "phone": user.phone,
        },

        "item": {
            "name": special.dish_name,

            "quantity": data.quantity,

            "unit_price": unit_price,

            "total_price": total_price,
        },

        "payment": {
            "method": order.payment_method,

            "status": order.payment_status,

            "payment_id": order.payment_id,
        },

        "order_status": order.status,

        "pre_orders": (
            special.pre_orders
        ),

        "remaining": final_remaining,
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


# =========================================================
# 🍱 TOMORROW SPECIAL - PRE-ORDER CUSTOMERS
# =========================================================

@router.get("/pre-orders/{special_id}")
def get_special_pre_orders(
    special_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # =====================================================
    # 🔐 ADMIN / CHEF ONLY
    # =====================================================

    if user.role not in ["admin", "chef"]:
        raise HTTPException(
            status_code=403,
            detail="Only admin or chef can access pre-order details",
        )

    # =====================================================
    # 🔎 GET SPECIAL
    # =====================================================

    special = (
        db.query(TomorrowSpecial)
        .filter(
            TomorrowSpecial.id == special_id
        )
        .first()
    )

    if not special:
        raise HTTPException(
            status_code=404,
            detail="Tomorrow Special not found",
        )

    # =====================================================
    # 👨‍🍳 CHEF SECURITY
    # Chef can only see his own special
    # Admin can see all specials
    # =====================================================

    if user.role == "chef":
        if special.chef_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="You can only access your own Tomorrow Special",
            )

    # =====================================================
    # 📦 GET PRE-ORDERS
    # =====================================================

    pre_orders = (
        db.query(TomorrowSpecialPreOrder)
        .filter(
            TomorrowSpecialPreOrder.special_id
            == special_id
        )
        .order_by(
            TomorrowSpecialPreOrder.created_at.desc()
        )
        .all()
    )

    # =====================================================
    # 📊 SUMMARY
    # =====================================================

    total_pre_orders = len(pre_orders)

    total_plates = sum(
        p.quantity or 0
        for p in pre_orders
    )

    total_amount = sum(
        float(p.total_amount or 0)
        for p in pre_orders
    )

    remaining_plates = max(
        special.max_plates - total_plates,
        0,
    )

    # =====================================================
    # 👤 CUSTOMER DATA
    # =====================================================

    customers = []

    for pre_order in pre_orders:

        customer = pre_order.customer
        order = pre_order.order

        customers.append({
            # =================================================
            # 🆔 PRE-ORDER
            # =================================================
            "pre_order_id": str(
                pre_order.id
            ),

            # =================================================
            # 🍱 SPECIAL
            # =================================================
            "special_id": str(
                special.id
            ),

            "dish_name": special.dish_name,

            # =================================================
            # 👤 CUSTOMER
            # =================================================
            "customer": {
                "id": (
                    str(customer.id)
                    if customer
                    else None
                ),

                "name": (
                    customer.name
                    if customer
                    else None
                ),

                "phone": (
                    customer.phone
                    if customer
                    else None
                ),

                "email": (
                    customer.email
                    if customer
                    else None
                ),
            },

            # =================================================
            # 📦 ORDER
            # =================================================
            "order": {
                "id": (
                    str(order.id)
                    if order
                    else None
                ),

                "status": (
                    order.status
                    if order
                    else None
                ),

                "created_at": (
                    order.created_at.isoformat()
                    if order and order.created_at
                    else None
                ),
            },

            # =================================================
            # 🍽️ QUANTITY
            # =================================================
            "quantity": pre_order.quantity,

            # =================================================
            # 💰 PRICE
            # =================================================
            "unit_price": float(
                pre_order.unit_price
            ),

            "total_amount": float(
                pre_order.total_amount
            ),

            # =================================================
            # 💳 PAYMENT
            # =================================================
            "payment": {
                "method": (
                    order.payment_method
                    if order
                    else None
                ),

                "status": (
                    order.payment_status
                    if order
                    else None
                ),

                "payment_id": (
                    order.payment_id
                    if order
                    else None
                ),
            },

            # =================================================
            # 🕒 PRE-ORDER CREATED
            # =================================================
            "created_at": (
                pre_order.created_at.isoformat()
                if pre_order.created_at
                else None
            ),
        })

    # =====================================================
    # ✅ RESPONSE
    # =====================================================

    return {
        "success": True,

        "special": {
            "id": str(
                special.id
            ),

            "dish_name": special.dish_name,

            "price": float(
                special.price
            ),

            "original_price": (
                float(special.original_price)
                if special.original_price is not None
                else None
            ),

            "max_plates": special.max_plates,

            "pre_orders": special.pre_orders or 0,

            "remaining": remaining_plates,

            "special_date": (
                special.special_date.isoformat()
                if special.special_date
                else None
            ),

            "cutoff_time": special.cutoff_time,

            "chef_id": str(
                special.chef_id
            ),

            "chef_name": (
                special.chef.name
                if special.chef
                else "Chef"
            ),
        },

        "summary": {
            "total_customers": total_pre_orders,

            "total_plates": total_plates,

            "total_amount": round(
                total_amount,
                2,
            ),

            "remaining_plates": remaining_plates,
        },

        "customers": customers,
    }