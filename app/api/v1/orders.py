from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from datetime import datetime
from datetime import timedelta, date
from zoneinfo import ZoneInfo
from sqlalchemy import or_
import os
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

router = APIRouter(prefix="/orders", tags=["Orders"])

@router.get("/chef-orders")
def get_chef_orders(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    orders = (
     db.query(Order)
     .options(selectinload(Order.items))
     .filter(
       Order.chef_id == user.id,
       or_(
        Order.payment_method != "cod",
        Order.cod_confirmed == True
       )
       )
     .order_by(Order.created_at.desc())
     .all()
    )

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
    orders = (
     db.query(Order)
     .options(selectinload(Order.items))
     .filter(Order.user_id == user.id)
     .order_by(Order.created_at.desc())
     .all()
    )

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

        result.append({
            # =========================
            # 🧾 ORDER
            # =========================
            "order_id": str(order.id),
            "order_status": order.status,

            "ordered_at": (
                order.created_at.isoformat()
                if order.created_at
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
def get_order(order_id: str, db: Session = Depends(get_db)):
    # 🔥 UUID VALIDATION
    try:
        order_uuid = UUID(order_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid order ID")

    order = (
     db.query(Order)
     .options(selectinload(Order.items))
     .filter(Order.id == order_uuid)
     .first()
    )

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
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
            for item in order.items
        ]
    }
# =========================
# ✅ CREATE ORDER
# =========================


from app.models.tomorrow_special import TomorrowSpecial




@router.post("/")
async def create_order(
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
# 🚀 FETCH ALL SPECIALS IN ONE QUERY
# =========================
        special_ids = [item.special_id for item in data.items if item.special_id]

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
        menu_ids = [item.menu_id for item in data.items if item.menu_id]

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

                menu = menus.get(item.menu_id)

                if menu is None:
                    raise HTTPException(
                       status_code=404,
                       detail="Menu not found"
                       )

                if not data.is_subscription:
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
                special = specials.get(item.special_id)

                if special is None:
                    raise HTTPException(
                      status_code=404,
                      detail="Special not found"
                    )

    # =========================
    # ⏰ TOMORROW SPECIAL CUTOFF
    # =========================
                # =========================
# ⏰ TOMORROW SPECIAL CUTOFF
# =========================
                try:
                    if not special.special_date:
                        raise HTTPException(
                          status_code=400,
                          detail="Special date is not configured"
                        )
                    if not special.cutoff_time:
                        raise HTTPException(
                          status_code=400,
                          detail="Special ordering time is not configured"
                          )
                    cutoff_datetime = datetime.strptime(
                     f"{special.special_date} {special.cutoff_time}",
                     "%Y-%m-%d %H:%M"
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
                          f"Tomorrow Special ordering closed. "
                          f"Order by {special.cutoff_time}"
                         )
                        )

                except HTTPException:
                    raise

                except Exception:
                    raise HTTPException(
                       status_code=400,
                       detail="Invalid special date or cutoff time"
                      )

                remaining = special.max_plates - special.pre_orders

                if remaining < item.quantity:
                    raise HTTPException(
                      status_code=400,
                      detail="Out of stock"
                    )

                special.pre_orders += item.quantity
                if not chef_id:
                    chef_id = special.chef_id
                elif chef_id != special.chef_id:
                    raise HTTPException(
                      status_code=400,
                      detail="Different chefs not allowed"
                    )

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
        if data.is_subscription and data.amount:
            total_price = data.amount
        order.total_price = total_price
        order.chef_id = chef_id
        if data.payment_method == "cod":

            cart = db.query(Cart).filter(
             Cart.user_id == user.id
            ).first()

            if cart:
                db.query(CartItem).filter(
                 CartItem.cart_id == cart.id
                ).delete(synchronize_session=False)

                db.delete(cart)

    # Save COD order first
            db.commit()

        else:
            db.commit()
        if chef_id:
            delete_cache(f"dashboard:{chef_id}")
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
        # 🔥 UUID VALIDATION
        # =========================
        try:
            order_uuid = UUID(order_id)
        except:
            raise HTTPException(
                status_code=400,
                detail="Invalid order ID"
            )

        # =========================
        # 🔍 FIND CUSTOMER ORDER
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
        # 💵 COD CHECK
        # =========================
        if order.payment_method != "cod":
            raise HTTPException(
                status_code=400,
                detail="This is not a COD order"
            )

        # =========================
        # 🚫 DUPLICATE CHECK
        # =========================
        if order.cod_confirmed:
            raise HTTPException(
                status_code=400,
                detail="COD order already confirmed"
            )

        # =========================
        # ✅ CONFIRM COD
        # =========================
        order.cod_confirmed = True
        order.status = "pending"

        # =========================
        # 🔔 CUSTOMER NOTIFICATION
        # =========================
        db.add(Notification(
            user_id=order.user_id,
            type="order",
            title="Order Confirmed",
            message=(
                f"Your COD order for ₹{order.total_price} "
                f"has been confirmed successfully."
            )
        ))

        # =========================
        # 🔔 CHEF NOTIFICATION
        # =========================
        db.add(Notification(
            user_id=order.chef_id,
            type="order",
            title="New Order Received",
            message=(
                f"You received a COD order "
                f"of ₹{order.total_price}"
            )
        ))

        # =========================
        # 💾 SAVE FIRST
        # =========================
        db.commit()
        db.refresh(order)

        # =========================
        # 📱 WHATSAPP → SACHIN
        # =========================
        try:
            items_text = ", ".join(
                f"{item.item_name} x{item.quantity}"
                for item in order.items
            )

            print(
                "📱 SENDING COD ORDER WHATSAPP | "
                f"order_id={order.id} | "
                f"customer={order.customer_name}"
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

        except Exception as e:
            print(
                "⚠️ COD WHATSAPP NOTIFICATION ERROR:",
                str(e)
            )

        # =========================
        # 🔥 CLEAR CHEF CACHE
        # =========================
        if order.chef_id:
            delete_cache(f"dashboard:{order.chef_id}")

        return {
            "status": "success",
            "message": "COD order confirmed",
            "order_id": str(order.id),
            "cod_confirmed": order.cod_confirmed
        }

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        print("❌ COD CONFIRM ERROR:", str(e))
        raise HTTPException(
            status_code=500,
            detail="COD confirmation failed"
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
async def verify_payment(
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
        db.add(Notification(
        user_id=order.user_id,
        type="payment",
        title="Payment Successful",
        message=f"Payment of ₹{order.total_price} received successfully."
        ))
        
        
        db.add(Notification(
          user_id=order.user_id,
          type="order",
          title="Order Placed",
          message=f"Your order for ₹{order.total_price} has been placed successfully."
        ))
        
        # =========================
# 🔔 CHEF NOTIFICATION
# PAYMENT SUCCESSFUL
# =========================
        db.add(Notification(
         user_id=order.chef_id,
         type="order",
         title="New Order Received",
         message=f"You received a paid order of ₹{order.total_price}"
        ))
        order.payment_id = data.get("razorpay_payment_id")

        # बेहतर flow
        order.status = "pending"   # 🔥 CHANGE (not directly preparing)

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
        try:

            items_text = ", ".join(
             f"{item.item_name} x{item.quantity}"
             for item in order.items
            )
            
            print(
                 "📱 SENDING PAID ORDER WHATSAPP | "
                 f"order_id={order.id} | "
                 f"customer={order.customer_name}"
                )
            
            whatsapp_result = await send_new_order_whatsapp(
               order_id=str(order.id),
               customer_name=order.customer_name,
               amount=float(order.total_price),
               items=items_text,
            )
            
            print(
              "✅ PAID ORDER WHATSAPP RESULT:",
              whatsapp_result
            )
        except Exception as e:

            print(
              "⚠️ PAID ORDER WHATSAPP NOTIFICATION ERROR:",
              str(e)
            )


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
    "out_for_delivery",
    "delivered",
    "cancelled"
]

    if status not in valid_status:
     raise HTTPException(status_code=400, detail="Invalid status")

    old_status = order.status
    if order.status == status:
     return {"msg": "already updated", "status": status}

    allowed_transitions = {
    "pending": ["accepted", "cancelled"],
    "accepted": ["preparing", "cancelled"],
    "preparing": ["ready"],
    "ready": ["out_for_delivery"],
    "out_for_delivery": ["delivered"],
    "delivered": [],
    "cancelled": []
}

    if status not in allowed_transitions.get(order.status, []):
     raise HTTPException(
        status_code=400,
        detail=f"Cannot change status from {order.status} to {status}"
    )

    # =========================
    # 🔥 UPDATE STATUS
    # =========================
    order.status = status
    if status == "accepted":
     db.add(Notification(
        user_id=order.user_id,
        type="order",
        title="Order Accepted",
        message="Your order has been accepted by the chef."
    ))
    if status == "preparing":
     db.add(Notification(
        user_id=order.user_id,
        type="order",
        title="Preparing Your Food",
        message="Chef has started preparing your food."
    ))
    if status == "ready":
       db.add(Notification(
        user_id=order.user_id,
        type="order",
        title="Food Ready",
        message="Your food is ready and waiting for pickup."
    ))
    if status == "out_for_delivery":
     db.add(Notification(
        user_id=order.user_id,
        type="delivery",
        title="Out For Delivery",
        message="Your order is on the way."
    ))
    if status == "delivered":
     db.add(Notification(
        user_id=order.user_id,
        type="order",
        title="Order Delivered",
        message="Enjoy your meal! Your order has been delivered."
    ))
    if status == "cancelled":
     db.add(Notification(
        user_id=order.user_id,
        type="order",
        title="Order Cancelled",
        message="Your order has been cancelled."
    ))

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
    delete_cache(f"dashboard:{order.chef_id}")

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