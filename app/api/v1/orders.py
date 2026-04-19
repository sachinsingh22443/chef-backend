from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import os

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

router = APIRouter(prefix="/orders", tags=["Orders"])

@router.get("/chef-orders")
def get_chef_orders(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    orders = db.query(Order)\
        .filter(Order.chef_id == user.id)\
        .order_by(Order.created_at.desc())\
        .all()

    data = []

    for order in orders:
        data.append({
            "id": str(order.id),
            "status": order.status,
            "total_price": order.total_price,
            "created_at": order.created_at,

            # 👤 customer info
            "customer_name": order.customer_name,
            "phone": order.phone,
            "address": order.address,

            # 💳 payment
            "payment_method": order.payment_method,
            "payment_status": order.payment_status,

            # 📦 items
            "items": [
                {
                    "name": item.item_name,
                    "quantity": item.quantity,
                    "price": item.price,
                    "image": item.item_image
                }
                for item in order.items
            ]
        })

    return {
    "total_orders": len([
    o for o in data if o["status"] != "cancelled"
]),
    "orders": data
}

# =========================
# ✅ GET ALL ORDERS
# =========================
@router.get("/")
def get_my_orders(db: Session = Depends(get_db), user=Depends(get_current_user)):
    orders = db.query(Order).filter(
        Order.user_id == user.id
    ).order_by(Order.created_at.desc()).all()

    return [
        {
            "id": str(order.id),
            "status": order.status,
            "total_price": order.total_price,
            "created_at": order.created_at,
            "address": order.address,
            "items": [
                {
                    "name": item.item_name,
                    "quantity": item.quantity
                }
                for item in order.items
            ]
        }
        for order in orders
    ]


# =========================
# ✅ GET SINGLE ORDER
# =========================
from uuid import UUID

@router.get("/{order_id}")
def get_order(order_id: str, db: Session = Depends(get_db)):
    # 🔥 UUID VALIDATION
    try:
        order_uuid = UUID(order_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid order ID")

    order = db.query(Order).filter(Order.id == order_uuid).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    items = db.query(OrderItem).filter(
        OrderItem.order_id == order.id
    ).all()

    return {
        "id": str(order.id),
        "status": order.status,
        "total_price": order.total_price,
        "customer_name": order.customer_name,
        "phone": order.phone,
        "address": order.address,
        "created_at": order.created_at,

        "items": [
            {
                "name": item.item_name,
                "quantity": item.quantity,
                "price": item.price
            }
            for item in items
        ]
    }
# =========================
# ✅ CREATE ORDER
# =========================


from app.models.tomorrow_special import TomorrowSpecial




@router.post("/")
def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    try:
        # =========================
        # 🔥 VALIDATION
        # =========================
        if data.payment_method not in ["cod", "card", "upi"]:
            raise HTTPException(status_code=400, detail="Invalid payment method")

        total_price = 0
        chef_id = None
        created_items = []

        # =========================
        # 🧾 CREATE ORDER
        # =========================
        order = Order(
            user_id=user.id,
            status="pending",
            customer_name=user.name,
            phone=user.phone,
            address=data.address,
            payment_method=data.payment_method,
            payment_status="pending",
            refund_status="pending"
        )

        db.add(order)
        db.flush()  # important for order.id

        # =========================
        # 🔥 LOOP ITEMS
        # =========================
        for item in data.items:

            # ❗ MUST HAVE ONE ID
            if not item.menu_id and not item.special_id:
                raise HTTPException(status_code=400, detail="Invalid item")

            # =========================
            # 🍽️ MENU ITEM
            # =========================
            if item.menu_id:
                menu = db.query(Menu).filter(Menu.id == item.menu_id).first()

                if not menu:
                    raise HTTPException(status_code=404, detail="Menu not found")

                if menu.quantity < item.quantity:
                    raise HTTPException(status_code=400, detail="Out of stock")

                menu.quantity -= item.quantity

                if not chef_id:
                    chef_id = menu.chef_id
                elif chef_id != menu.chef_id:
                    raise HTTPException(status_code=400, detail="Different chefs not allowed")

                price = menu.price * item.quantity
                total_price += price

                db.add(OrderItem(
                    order_id=order.id,
                    menu_id=menu.id,
                    quantity=item.quantity,
                    price=price,
                    item_name=menu.name,
                    item_image=menu.image_urls[0] if menu.image_urls else None
                ))

                created_items.append({
                    "name": menu.name,
                    "quantity": item.quantity,
                    "price": price,
                    "image": menu.image_urls[0] if menu.image_urls else None
                })

            # =========================
            # 🔥 SPECIAL ITEM
            # =========================
            elif item.special_id:
                special = db.query(TomorrowSpecial).filter(
                    TomorrowSpecial.id == item.special_id
                ).first()

                if not special:
                    raise HTTPException(status_code=404, detail="Special not found")

                remaining = special.max_plates - special.pre_orders

                if remaining < item.quantity:
                    raise HTTPException(status_code=400, detail="Out of stock")

                special.pre_orders += item.quantity

                if not chef_id:
                    chef_id = special.chef_id
                elif chef_id != special.chef_id:
                    raise HTTPException(status_code=400, detail="Different chefs not allowed")

                price = special.price * item.quantity
                total_price += price

                db.add(OrderItem(
                    order_id=order.id,
                    special_id=special.id,
                    quantity=item.quantity,
                    price=price,
                    item_name=special.dish_name,
                    item_image=special.image_url
                ))

                created_items.append({
                    "name": special.dish_name,
                    "quantity": item.quantity,
                    "price": price,
                    "image": special.image_url
                })

        # =========================
        # 🔥 FINAL UPDATE
        # =========================
        order.total_price = total_price
        order.chef_id = chef_id

        # =========================
        # 🔔 NOTIFICATION
        # =========================
        db.add(Notification(
            user_id=chef_id,
            type="order",
            title="New Order Received",
            message=f"You received an order of ₹{total_price}"
        ))

        # =========================
        # 🛒 CLEAR CART (COD)
        # =========================
        if data.payment_method == "cod":
            cart = db.query(Cart).filter(Cart.user_id == user.id).first()
            if cart:
                db.query(CartItem).filter(
                    CartItem.cart_id == cart.id
                ).delete(synchronize_session=False)
                db.delete(cart)

        db.commit()
        db.refresh(order)

        return {
            "id": str(order.id),
            "status": order.status,
            "total_price": order.total_price,
            "created_at": order.created_at,
            "customer_name": order.customer_name,
            "phone": order.phone,
            "address": order.address,
            "payment_method": order.payment_method,
            "payment_status": order.payment_status,
            "items": created_items
        }

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        print("❌ ORDER ERROR:", str(e))
        raise HTTPException(status_code=500, detail="Order creation failed")
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
    user = Depends(get_current_user)   # 🔥 ADD THIS
):
    try:
        # =========================
        # 🔥 UUID VALIDATION
        # =========================
        try:
            order_uuid = UUID(data.order_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid order ID")

        # =========================
        # 🔥 FETCH ORDER (SECURE)
        # =========================
        order = db.query(Order).filter(
            Order.id == order_uuid,
            Order.user_id == user.id   # 🔥 SECURITY FIX
        ).first()

        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        # =========================
        # 🔥 STATUS CHECK
        # =========================
        if order.payment_status == "paid":
            raise HTTPException(status_code=400, detail="Already paid")

        if order.status not in ["pending", "created"]:
            raise HTTPException(status_code=400, detail="Invalid order state")

        # =========================
        # 💰 AMOUNT
        # =========================
        amount = int(order.total_price * 100)

        if amount < 100:
            raise HTTPException(status_code=400, detail="Minimum ₹1 required")

        # =========================
        # 🔑 KEYS
        # =========================
        key_id = os.getenv("RAZORPAY_KEY_ID")
        key_secret = os.getenv("RAZORPAY_KEY_SECRET")

        if not key_id or not key_secret:
            raise HTTPException(status_code=500, detail="Razorpay keys missing")

        auth = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth}"
        }

        payload = {
            "amount": amount,
            "currency": "INR",
            "receipt": str(order.id)
        }

        # =========================
        # 🔥 API CALL
        # =========================
        res = requests.post(
            "https://api.razorpay.com/v1/orders",
            json=payload,
            headers=headers,
            timeout=10
        )

        if res.status_code != 200:
            print("❌ RAZORPAY ERROR:", res.text)
            raise HTTPException(status_code=500, detail="Payment gateway error")

        payment = res.json()

        return {
            "razorpay_order_id": payment["id"],
            "amount": payment["amount"],
            "key": key_id
        }

    except HTTPException:
        raise

    except Exception as e:
        print("❌ RAZORPAY ERROR:", str(e))
        raise HTTPException(status_code=500, detail="Payment init failed")
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

@router.post("/verify-payment")
def verify_payment(
    data: dict,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)   # 🔥 ADD THIS
):
    try:
        # =========================
        # 🔑 SECRET
        # =========================
        key_secret = os.getenv("RAZORPAY_KEY_SECRET")

        if not key_secret:
            raise HTTPException(status_code=500, detail="Razorpay key missing")

        # =========================
        # 🔥 SIGNATURE VERIFY
        # =========================
        body = f"{data['razorpay_order_id']}|{data['razorpay_payment_id']}"

        generated_signature = hmac.new(
            key_secret.encode(),
            body.encode(),
            hashlib.sha256
        ).hexdigest()

        if generated_signature != data["razorpay_signature"]:
            raise HTTPException(status_code=400, detail="Invalid signature")

        # =========================
        # 🔥 UUID VALIDATION
        # =========================
        try:
            order_uuid = UUID(data.get("order_id"))
        except:
            raise HTTPException(status_code=400, detail="Invalid order ID")

        # =========================
        # 🔥 FETCH ORDER (SECURE)
        # =========================
        order = db.query(Order).filter(
            Order.id == order_uuid,
            Order.user_id == user.id   # 🔥 SECURITY FIX
        ).first()

        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        # =========================
        # 🔥 DUPLICATE CHECK
        # =========================
        if order.payment_status == "paid":
            raise HTTPException(status_code=400, detail="Already verified")

        # =========================
        # 💳 UPDATE PAYMENT
        # =========================
        order.payment_status = "paid"
        order.payment_id = data.get("razorpay_payment_id")

        # बेहतर flow
        order.status = "accepted"   # 🔥 CHANGE (not directly preparing)

        # =========================
        # 🛒 CLEAR CART
        # =========================
        cart = db.query(Cart).filter(Cart.user_id == order.user_id).first()

        if cart:
            db.query(CartItem).filter(
                CartItem.cart_id == cart.id
            ).delete(synchronize_session=False)
            db.delete(cart)

        db.commit()

        return {
            "msg": "Payment success",
            "order_id": str(order.id)
        }

    except HTTPException:
        raise

    except Exception as e:
        print("❌ VERIFY ERROR:", str(e))
        raise HTTPException(status_code=400, detail="Payment failed")
# =========================
# 🔄 UPDATE STATUS
# =========================
from uuid import UUID
from fastapi import Depends, HTTPException
from datetime import datetime

@router.put("/{order_id}/status")
def update_status(
    order_id: str,
    status: str,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)   # 🔥 ADD
):
    # =========================
    # 🔥 UUID VALIDATION
    # =========================
    try:
        order_uuid = UUID(order_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid order ID")

    # =========================
    # 🔥 FETCH ORDER (SECURE)
    # =========================
    order = db.query(Order).filter(
        Order.id == order_uuid,
        Order.chef_id == user.id   # 🔥 ONLY CHEF CAN UPDATE
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # =========================
    # 🔥 VALID STATUS CHECK
    # =========================
    valid_status = [
        "pending",
        "accepted",
        "preparing",
        "ready",
        "delivered",
        "cancelled"
    ]

    if status not in valid_status:
        raise HTTPException(status_code=400, detail="Invalid status")

    old_status = order.status

    # =========================
    # 🔥 UPDATE STATUS
    # =========================
    order.status = status

    # =========================
    # 💸 CANCEL → REFUND INIT
    # =========================
    if status == "cancelled":
        order.refund_status = "processing"
        order.refund_amount = order.total_price
        order.refund_date = datetime.utcnow()

    # =========================
    # 💰 DELIVERED → EARNING (SAFE)
    # =========================
    if status == "delivered" and old_status != "delivered":
        db.add(Earning(
            chef_id=order.chef_id,
            amount=order.total_price
        ))

    db.commit()

    return {"msg": "updated", "status": status}


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