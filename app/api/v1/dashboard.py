from app.core.cache import get_cache, set_cache
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
    user=Depends(get_current_user)
):
    if user.role != "chef":
        raise HTTPException(status_code=403, detail="Only chefs allowed")
    
    cache_key = f"dashboard:{user.id}"

    cached = get_cache(cache_key)

    if cached:
       print("✅ Dashboard Cache Hit")
       return cached

    # =========================
    # ✅ TOTAL STATS
    # =========================
    total_orders = (
      db.query(func.count(Order.id))
        .filter(
        Order.chef_id == user.id,
        Order.status != "cancelled"
       )
        .scalar() or 0
    )

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
    current_time = datetime.utcnow()

    month_start = current_time.replace(
     day=1,
     hour=0,
     minute=0,
     second=0,
     microsecond=0
)

    if month_start.month == 12:
        next_month = month_start.replace(
         year=month_start.year + 1,
         month=1
        )
    else:
        next_month = month_start.replace(
         month=month_start.month + 1
        )

    monthly_earnings = (
     db.query(func.sum(Earning.amount))
     .filter(
        Earning.chef_id == user.id,
        Earning.created_at >= month_start,
        Earning.created_at < next_month
      ) .scalar() or 0
    )

    monthly_orders = (
      db.query(func.count(Order.id))
      .filter(
        Order.chef_id == user.id,
        Order.status != "cancelled",
        Order.created_at >= month_start,
        Order.created_at < next_month
       )
       .scalar() or 0
    )

    avg_order_value = monthly_earnings / monthly_orders if monthly_orders > 0 else 0

    # =========================
    # ✅ AVG RATING
    # =========================
    avg_rating = db.query(func.avg(Review.rating))\
        .filter(Review.chef_id == user.id)\
        .scalar() or 0

    
    
    # =========================
# ✅ WEEKLY DATA (1 QUERY)
# =========================

    today = current_time.replace(
     hour=0,
     minute=0,
     second=0,
     microsecond=0
    )

    week_start = today - timedelta(days=6)

    weekly_result = (
      db.query(
        func.date(Earning.created_at).label("day"),
        func.sum(Earning.amount).label("earnings")
        )
        .filter(
            Earning.chef_id == user.id,
            Earning.created_at >= week_start,
            Earning.created_at < today + timedelta(days=1)
        )
         .group_by(func.date(Earning.created_at))
         .all()
         )

    weekly_map = {
     row.day: float(row.earnings or 0)
     for row in weekly_result
    }

    week_data = []

    for i in range(7):
      day = week_start + timedelta(days=i)

      week_data.append({
        "day": day.strftime("%a"),
        "earnings": weekly_map.get(day.date(), 0)
        })

    # =========================
    # 🔥 TOP PERFORMING DISHES (FIXED)
    # =========================
    top_dishes_query = db.query(
        Menu.id,
        Menu.name,
        func.sum(OrderItem.quantity).label("orders"),
        func.sum(OrderItem.price).label("revenue")
    )\
    .join(OrderItem, OrderItem.menu_id == Menu.id)\
    .join(Order, Order.id == OrderItem.order_id)\
    .filter(
        Order.chef_id == user.id,
        Order.status == "delivered"   # 🔥 FIX
    )\
     .group_by(Menu.id, Menu.name)\
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
    response = {
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

    set_cache(cache_key, response, ttl=300)

    return response