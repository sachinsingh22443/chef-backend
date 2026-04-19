from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from app.api.deps import get_db, get_current_user
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.menu import Menu
from app.models.earning import Earning
from app.models.review import Review

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/")
def get_dashboard(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    if user.role != "chef":
        raise HTTPException(status_code=403, detail="Only chefs allowed")

    # =========================
    # ✅ TOTAL STATS
    # =========================
    total_orders = db.query(Order)\
        .filter(
            Order.chef_id == user.id,
            Order.status != "cancelled"   # 🔥 FIX
        ).count()

    total_earnings = db.query(func.sum(Earning.amount))\
        .filter(Earning.chef_id == user.id)\
        .scalar() or 0

    # =========================
    # ✅ TODAY RANGE (FIXED)
    # =========================
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    today_earnings = db.query(func.sum(Earning.amount))\
        .filter(
            Earning.chef_id == user.id,
            Earning.created_at >= start,
            Earning.created_at < end
        ).scalar() or 0

    # =========================
    # ✅ THIS MONTH
    # =========================
    this_month = datetime.utcnow().month
    this_year = datetime.utcnow().year

    monthly_earnings = db.query(func.sum(Earning.amount))\
        .filter(
            Earning.chef_id == user.id,
            func.extract('month', Earning.created_at) == this_month,
            func.extract('year', Earning.created_at) == this_year
        ).scalar() or 0

    monthly_orders = db.query(Order)\
        .filter(
            Order.chef_id == user.id,
            Order.status != "cancelled",
            func.extract('month', Order.created_at) == this_month,
            func.extract('year', Order.created_at) == this_year
        ).count()

    avg_order_value = monthly_earnings / monthly_orders if monthly_orders > 0 else 0

    # =========================
    # ✅ AVG RATING
    # =========================
    avg_rating = db.query(func.avg(Review.rating))\
        .filter(Review.chef_id == user.id)\
        .scalar() or 0

    # =========================
    # ✅ WEEKLY DATA (FIXED)
    # =========================
    week_data = []

    for i in range(7):
        day_start = (datetime.utcnow() - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        earning = db.query(func.sum(Earning.amount))\
            .filter(
                Earning.chef_id == user.id,
                Earning.created_at >= day_start,
                Earning.created_at < day_end
            ).scalar() or 0

        week_data.append({
            "day": day_start.strftime("%a"),
            "earnings": earning
        })

    week_data.reverse()

    # =========================
    # 🔥 TOP PERFORMING DISHES (FIXED)
    # =========================
    top_dishes_query = db.query(
        Menu.name,
        func.sum(OrderItem.quantity).label("orders"),
        func.sum(OrderItem.quantity * OrderItem.price).label("revenue")
    )\
    .join(OrderItem, OrderItem.menu_id == Menu.id)\
    .join(Order, Order.id == OrderItem.order_id)\
    .filter(
        Order.chef_id == user.id,
        Order.status == "delivered"   # 🔥 FIX
    )\
    .group_by(Menu.name)\
    .order_by(func.sum(OrderItem.quantity).desc())\
    .limit(5)\
    .all()

    top_dishes = [
        {
            "name": dish.name,
            "orders": int(dish.orders or 0),
            "revenue": float(dish.revenue or 0)
        }
        for dish in top_dishes_query
    ]

    # =========================
    # ✅ FINAL RESPONSE
    # =========================
    return {
        "total_orders": total_orders,
        "total_earnings": total_earnings,
        "today_earnings": today_earnings,
        "avg_rating": round(avg_rating, 1),

        "monthly_earnings": monthly_earnings,
        "monthly_orders": monthly_orders,
        "avg_order_value": avg_order_value,

        "weekly_data": week_data,
        "top_dishes": top_dishes
    }