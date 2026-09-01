from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import get_db, get_current_user
from uuid import UUID
from app.models.user import User
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.tomorrow_special import TomorrowSpecial
from app.models.tomorrow_special_pre_order import TomorrowSpecialPreOrder

from app.schemas.tomorrow_special import PreOrderCreate


router = APIRouter(
    prefix="/tomorrow-special",
    tags=["Tomorrow Special Pre-Order"],
)



# =========================================================
# 🍱 TOMORROW SPECIAL PRE-ORDER
# =========================================================

@router.post("/pre-order")
def create_tomorrow_special_pre_order(
    data: PreOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # =====================================================
    # 👤 CUSTOMER CHECK
    # =====================================================

    if current_user.role != "customer":
        raise HTTPException(
            status_code=403,
            detail="Only customers can place tomorrow special orders",
        )

    # =====================================================
    # 📦 QUANTITY VALIDATION
    # =====================================================

    if data.quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be greater than 0",
        )

    # =====================================================
    # 🍱 FIND TOMORROW SPECIAL
    # =====================================================

    special = (
        db.query(TomorrowSpecial)
        .filter(
            TomorrowSpecial.id == data.special_id,
            TomorrowSpecial.is_active == 1,
        )
        .first()
    )

    if not special:
        raise HTTPException(
            status_code=404,
            detail="Tomorrow special not found or inactive",
        )

    # =====================================================
    # 📅 CHECK SPECIAL DATE
    # =====================================================

    # Existing TomorrowSpecial already controls its date.
    # We don't modify the existing customer flow here.

    # =====================================================
    # 📊 CHECK AVAILABLE PLATES
    # =====================================================

    current_pre_orders = (
        db.query(
            func.coalesce(
                func.sum(TomorrowSpecialPreOrder.quantity),
                0,
            )
        )
        .filter(
            TomorrowSpecialPreOrder.special_id == special.id,
        )
        .scalar()
        or 0
    )

    remaining = special.max_plates - int(current_pre_orders)

    if data.quantity > remaining:
        raise HTTPException(
            status_code=400,
            detail=f"Only {remaining} plates remaining",
        )

    # =====================================================
    # 💰 PRICE SNAPSHOT
    # =====================================================

    unit_price = float(special.price)

    total_amount = round(
        unit_price * data.quantity,
        2,
    )

    # =====================================================
    # 🧾 CREATE ORDER
    # =====================================================

    order = Order(
        user_id=current_user.id,

        # Tomorrow Special belongs to its chef
        chef_id=special.chef_id,

        status="pending",

        cod_confirmed=False,

        total_price=total_amount,

        customer_name=current_user.name,

        phone=current_user.phone,

        payment_method="pending",

        payment_status="pending",
    )

    db.add(order)
    db.flush()

    # =====================================================
    # 📍 CUSTOMER ADDRESS
    # =====================================================

    # IMPORTANT:
    # PreOrderCreate currently does not contain address.
    #
    # Existing customer app may already handle address
    # separately. We keep this endpoint backward compatible.
    #
    # Address can be added in the next step without changing
    # the existing Tomorrow Special response.

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

    db.add(order_item)

    # =====================================================
    # 📊 UPDATE TOMORROW SPECIAL COUNTER
    # =====================================================

    special.pre_orders = (
        int(special.pre_orders or 0)
        + data.quantity
    )

    # =====================================================
    # 📝 CREATE PRE-ORDER RECORD
    # =====================================================

    preorder = TomorrowSpecialPreOrder(
        special_id=special.id,

        order_id=order.id,

        customer_id=current_user.id,

        quantity=data.quantity,

        unit_price=unit_price,

        total_amount=total_amount,
    )

    db.add(preorder)

    # =====================================================
    # 💾 COMMIT
    # =====================================================

    try:
        db.commit()

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to create tomorrow special pre-order",
        )

    # =====================================================
    # 🔄 REFRESH
    # =====================================================

    db.refresh(order)
    db.refresh(special)

    # =====================================================
    # ✅ RESPONSE
    # =====================================================

    return {
        "success": True,

        "message": "Tomorrow special pre-order placed successfully",

        "order": {
            "id": str(order.id),
            "status": order.status,
            "total_price": float(order.total_price),
            "customer_name": order.customer_name,
            "phone": order.phone,
            "chef_id": str(order.chef_id),
            "payment_method": order.payment_method,
            "payment_status": order.payment_status,
        },

        "tomorrow_special": {
            "id": str(special.id),
            "dish_name": special.dish_name,
            "quantity": data.quantity,
            "unit_price": unit_price,
            "total_amount": total_amount,
            "pre_orders": int(special.pre_orders or 0),
            "remaining": max(
                0,
                special.max_plates
                - int(special.pre_orders or 0),
            ),
        },

        "customer": {
            "id": str(current_user.id),
            "name": current_user.name,
            "phone": current_user.phone,
        },
    }