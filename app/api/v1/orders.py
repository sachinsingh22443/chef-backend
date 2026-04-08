from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models.notification import Notification
from app.api.deps import get_db, get_current_user
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.menu import Menu
from app.schemas.order import OrderCreate
from app.models.earning import Earning

router = APIRouter(prefix="/orders", tags=["Orders"])


# ✅ CREATE ORDER (UPDATED 🔥)
from app.models.notification import Notification

@router.post("/")
def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    total_price = 0
    chef_id = None

    order = Order(
    user_id=user.id,
    status="pending",
    customer_name=user.name,
    phone=user.phone,
    address=data.address
)
    db.add(order)
    db.flush()

    for item in data.items:
        menu = db.query(Menu).filter(Menu.id == item.menu_id).first()

        if not menu:
            raise HTTPException(status_code=404, detail="Menu not found")

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
            # ✅ FIX (NO COLUMN CHANGE)
            item_image=menu.image_urls[0] if menu.image_urls else None
        ))

    # ✅ SET VALUES
    order.total_price = total_price
    order.chef_id = chef_id

    # 🔔 NOTIFICATION (SAFE ADD)
    db.add(Notification(
        user_id=chef_id,
        type="order",
        title="New Order Received",
        message=f"You received an order of ₹{total_price}"
    ))

    # ✅ SINGLE COMMIT
    db.commit()
    db.refresh(order)

    return {
        "msg": "Order created",
        "order_id": str(order.id)
    }

# ✅ GET CHEF ORDERS (OPTIMIZED 🔥)
@router.get("/chef-orders")
def get_chef_orders(db: Session = Depends(get_db), user=Depends(get_current_user)):
    orders = db.query(Order).filter(Order.chef_id == user.id).all()

    result = []

    for order in orders:
        items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()

        item_list = [
            {
                "name": item.item_name,
                "quantity": item.quantity,
                "price": item.price,
                "image": item.item_image
            }
            for item in items
        ]

        result.append({
            "id": str(order.id),
            "status": order.status,
            "total_price": order.total_price,

            # 🔥 ADD THESE (IMPORTANT)
            "customer_name": order.customer_name,
            "phone": order.phone,
            "address": order.address,
            "created_at": order.created_at,

            "items": item_list
        })

    return result

# ✅ ORDER DETAIL (UPDATED 🔥)
@router.get("/{order_id}")
def get_order(order_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()

    return {
        "id": str(order.id),
        "status": order.status,
        "total_price": order.total_price,

        # 🔥 ADD THIS (VERY IMPORTANT)
        "created_at": order.created_at,
        "customer_name": order.customer_name,
        "phone": order.phone,
        "address": order.address,

        "items": [
            {
                "name": item.item_name,
                "quantity": item.quantity,
                "price": item.price,
                "image": item.item_image
            }
            for item in items
        ]
    }

# ✅ UPDATE STATUS (IMPROVED 🔥)
@router.put("/{order_id}/status")
def update_status(
    order_id: str,
    status: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

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

    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Not found")

    # 🔥 IMPORTANT: EARNING LOGIC ADD HERE
    if status == "delivered" and order.status != "delivered":
        earning = Earning(
            chef_id=order.chef_id,
            amount=order.total_price
        )
        db.add(earning)

    # 🔥 update status
    order.status = status

    db.commit()

    return {"msg": "updated", "status": status}


from app.models.earning import Earning
from app.models.notification import Notification

@router.put("/orders/{order_id}/complete")
def complete_order(
    order_id: str,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # ✅ status update
    order.status = "completed"

    # 💰 EARNING SAVE
    db.add(Earning(
        chef_id=order.chef_id,
        amount=order.total_price
    ))

    # 🔔 NOTIFICATION (payment)
    db.add(Notification(
        user_id=order.chef_id,
        type="payment",
        title="Payment Received",
        message=f"₹{order.total_price} credited"
    ))

    db.commit()

    return {"msg": "Order completed"}