from datetime import datetime, timedelta
from uuid import UUID as UUIDType
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, aliased
from app.models.tomorrow_special import TomorrowSpecial
from app.models.tomorrow_special_pre_order import TomorrowSpecialPreOrder
from app.models.subscription_meal_schedule import SubscriptionMealSchedule

from app.models.user import User
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.subscription import Subscription

from app.api.deps import (
    get_db,
    require_role,
)

from app.utils.hashing import verify_password

from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
)


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


# =========================================================
# ADMIN LOGIN SCHEMA
# =========================================================

class AdminLoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


# =========================================================
# ADMIN LOGIN
# =========================================================

# =========================================================
# ADMIN LOGIN
# =========================================================

@router.post("/login")
def admin_login(
    data: AdminLoginSchema,
    db: Session = Depends(get_db),
):
    from sqlalchemy import text

    print("\n")
    print("====================================================")
    print("              ADMIN LOGIN DEBUG")
    print("====================================================")

    # =====================================================
    # 1. EMAIL RECEIVED FROM FRONTEND
    # =====================================================

    email = str(data.email).strip().lower()

    print("EMAIL RECEIVED :", repr(data.email))
    print("EMAIL NORMALIZED:", repr(email))
    print("EMAIL LENGTH   :", len(email))

    # =====================================================
    # 2. DATABASE IDENTITY
    # =====================================================

    try:
        db_info = db.execute(
            text("""
                SELECT
                    current_database() AS database_name,
                    current_schema() AS schema_name,
                    current_user AS database_user
            """)
        ).mappings().first()

        print("DATABASE INFO  :", dict(db_info) if db_info else None)

    except Exception as e:
        print("DATABASE ERROR  :", repr(e))

    # =====================================================
    # 3. RAW SQL - FIND EXACT EMAIL
    # =====================================================

    try:
        raw_user = db.execute(
            text("""
                SELECT
                    id,
                    name,
                    email,
                    role,
                    is_active,
                    is_verified,
                    application_status,
                    LENGTH(password) AS password_length,
                    LEFT(password, 20) AS password_prefix
                FROM users
                WHERE LOWER(TRIM(email)) = :email
                LIMIT 1
            """),
            {
                "email": email
            }
        ).mappings().first()

        print("RAW SQL USER   :", dict(raw_user) if raw_user else None)

    except Exception as e:
        print("RAW SQL ERROR  :", repr(e))
        raw_user = None

    # =====================================================
    # 4. RAW SQL - COUNT USERS
    # =====================================================

    try:
        users_count = db.execute(
            text("""
                SELECT COUNT(*) AS total
                FROM users
            """)
        ).scalar()

        print("TOTAL USERS    :", users_count)

    except Exception as e:
        print("COUNT ERROR    :", repr(e))

    # =====================================================
    # 5. RAW SQL - SHOW ADMIN EMAILS
    # =====================================================

    try:
        admin_rows = db.execute(
            text("""
                SELECT
                    id,
                    email,
                    role,
                    is_active,
                    is_verified
                FROM users
                WHERE role = 'admin'
                ORDER BY created_at DESC
                LIMIT 10
            """)
        ).mappings().all()

        print("RAW ADMINS     :", [dict(row) for row in admin_rows])

    except Exception as e:
        print("ADMIN SQL ERROR:", repr(e))

    # =====================================================
    # 6. SQLALCHEMY ORM - EMAIL ONLY
    # =====================================================

    try:
        email_user = (
            db.query(User)
            .filter(
                func.lower(func.trim(User.email)) == email
            )
            .first()
        )

        print(
            "ORM EMAIL USER :",
            {
                "found": bool(email_user),
                "id": str(email_user.id) if email_user else None,
                "name": email_user.name if email_user else None,
                "email": email_user.email if email_user else None,
                "role": email_user.role if email_user else None,
                "active": email_user.is_active if email_user else None,
                "verified": email_user.is_verified if email_user else None,
                "application_status": (
                    email_user.application_status
                    if email_user
                    else None
                ),
            }
        )

    except Exception as e:
        print("ORM EMAIL ERROR:", repr(e))
        email_user = None

    # =====================================================
    # 7. SQLALCHEMY ORM - ADMIN ONLY
    # =====================================================

    try:
        user = (
            db.query(User)
            .filter(
                func.lower(func.trim(User.email)) == email,
                User.role == "admin",
            )
            .first()
        )

        print(
            "ORM ADMIN USER :",
            {
                "found": bool(user),
                "id": str(user.id) if user else None,
                "name": user.name if user else None,
                "email": user.email if user else None,
                "role": user.role if user else None,
                "active": user.is_active if user else None,
                "verified": user.is_verified if user else None,
                "application_status": (
                    user.application_status
                    if user
                    else None
                ),
            }
        )

    except Exception as e:
        print("ORM ADMIN ERROR:", repr(e))
        user = None

    # =====================================================
    # 8. USER NOT FOUND
    # =====================================================

    if not user:

        print("")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("ADMIN LOGIN FAILED: USER NOT FOUND")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("")

        raise HTTPException(
            status_code=401,
            detail="ADMIN_USER_NOT_FOUND",
        )

    # =====================================================
    # 9. PASSWORD VERIFICATION
    # =====================================================

    try:
        password_valid = verify_password(
            data.password,
            user.password,
        )

        print("PASSWORD VALID :", password_valid)

    except Exception as e:
        print("PASSWORD ERROR :", repr(e))

        raise HTTPException(
            status_code=500,
            detail="Password verification failed",
        )

    # =====================================================
    # 10. INVALID PASSWORD
    # =====================================================

    if not password_valid:

        print("")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("ADMIN LOGIN FAILED: INVALID PASSWORD")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("")

        raise HTTPException(
            status_code=401,
            detail="INVALID_ADMIN_PASSWORD",
        )

    # =====================================================
    # 11. ACTIVE CHECK
    # =====================================================

    if not user.is_active:

        print("ADMIN LOGIN FAILED: ACCOUNT INACTIVE")

        raise HTTPException(
            status_code=403,
            detail="Admin account is disabled",
        )

    # =====================================================
    # 12. VERIFIED CHECK
    # =====================================================

    if not user.is_verified:

        print("ADMIN LOGIN FAILED: ACCOUNT NOT VERIFIED")

        raise HTTPException(
            status_code=403,
            detail="Admin account is not verified",
        )

    # =====================================================
    # 13. ROLE CHECK
    # =====================================================

    if user.role != "admin":

        print(
            "ADMIN LOGIN FAILED: WRONG ROLE:",
            repr(user.role)
        )

        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )

    # =====================================================
    # 14. CREATE ACCESS TOKEN
    # =====================================================

    access_token = create_access_token(
        {
            "sub": str(user.id),
            "role": user.role,
        }
    )

    # =====================================================
    # 15. CREATE REFRESH TOKEN
    # =====================================================

    refresh_token = create_refresh_token(
        {
            "sub": str(user.id),
            "role": user.role,
        }
    )

    # =====================================================
    # 16. SUCCESS
    # =====================================================

    print("")
    print("====================================================")
    print("              ADMIN LOGIN SUCCESS")
    print("====================================================")
    print("ADMIN ID       :", user.id)
    print("ADMIN EMAIL    :", user.email)
    print("ADMIN ROLE     :", user.role)
    print("ADMIN ACTIVE   :", user.is_active)
    print("ADMIN VERIFIED :", user.is_verified)
    print("====================================================")
    print("")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "role": user.role,
        "name": user.name,
        "email": user.email,
    }


# =========================================================
# ADMIN ACCESS TEST
# =========================================================

@router.get("/check")
def check_admin_access(
    current_user: User = Depends(
        require_role(["admin"])
    ),
):
    return {
        "success": True,
        "message": "Admin access verified",
        "user_id": str(current_user.id),
        "role": current_user.role,
    }


# =========================================================
# ADMIN DASHBOARD
# =========================================================

# =========================================================
# ADMIN DASHBOARD
# =========================================================

@router.get("/dashboard")
def admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role(["admin"])
    ),
):

    # =====================================================
    # INDIA TODAY
    # =====================================================

    india_tz = ZoneInfo("Asia/Kolkata")
    utc_tz = ZoneInfo("UTC")

    now_india = datetime.now(india_tz)

    today_start_india = now_india.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    tomorrow_start_india = (
        today_start_india
        + timedelta(days=1)
    )

    # =====================================================
    # UTC-NAIVE BOUNDARIES
    # =====================================================

    today_start_utc = (
        today_start_india
        .astimezone(utc_tz)
        .replace(tzinfo=None)
    )

    tomorrow_start_utc = (
        tomorrow_start_india
        .astimezone(utc_tz)
        .replace(tzinfo=None)
    )

    # =====================================================
    # TOTAL ORDERS
    # =====================================================

    total_orders = (
        db.query(func.count(Order.id))
        .filter(
            Order.status != "cancelled"
        )
        .scalar()
        or 0
    )

    # =====================================================
    # TODAY'S ORDERS
    # =====================================================

    todays_orders = (
        db.query(func.count(Order.id))
        .filter(
            Order.created_at >= today_start_utc,
            Order.created_at < tomorrow_start_utc,
            Order.status != "cancelled",
        )
        .scalar()
        or 0
    )

    # =====================================================
    # PENDING
    # =====================================================

    pending_orders = (
        db.query(func.count(Order.id))
        .filter(
            Order.status == "pending",
        )
        .scalar()
        or 0
    )

    # =====================================================
    # PREPARING
    # =====================================================

    preparing_orders = (
        db.query(func.count(Order.id))
        .filter(
            Order.status == "preparing",
        )
        .scalar()
        or 0
    )

    # =====================================================
    # OUT FOR DELIVERY
    # =====================================================

    out_for_delivery_orders = (
        db.query(func.count(Order.id))
        .filter(
            Order.status == "out_for_delivery",
        )
        .scalar()
        or 0
    )

    # =====================================================
    # DELIVERED
    # =====================================================

    delivered_orders = (
        db.query(func.count(Order.id))
        .filter(
            Order.status == "delivered",
        )
        .scalar()
        or 0
    )

    # =====================================================
    # CANCELLED
    # =====================================================

    cancelled_orders = (
        db.query(func.count(Order.id))
        .filter(
            Order.status == "cancelled",
        )
        .scalar()
        or 0
    )

    # =====================================================
    # TODAY'S REVENUE
    # =====================================================

    todays_revenue = (
        db.query(
            func.coalesce(
                func.sum(Order.total_price),
                0,
            )
        )
        .filter(
            Order.created_at >= today_start_utc,
            Order.created_at < tomorrow_start_utc,
            Order.status != "cancelled",
        )
        .scalar()
        or 0
    )

    # =====================================================
    # TOTAL REVENUE
    # =====================================================

    total_revenue = (
        db.query(
            func.coalesce(
                func.sum(Order.total_price),
                0,
            )
        )
        .filter(
            Order.status != "cancelled",
        )
        .scalar()
        or 0
    )

    # =====================================================
    # CUSTOMERS
    # =====================================================

    total_customers = (
        db.query(func.count(User.id))
        .filter(
            User.role == "customer",
        )
        .scalar()
        or 0
    )

    active_customers = (
        db.query(func.count(User.id))
        .filter(
            User.role == "customer",
            User.is_active == True,
        )
        .scalar()
        or 0
    )

    # =====================================================
    # CHEFS
    # =====================================================

    total_chefs = (
        db.query(func.count(User.id))
        .filter(
            User.role == "chef",
        )
        .scalar()
        or 0
    )

    active_chefs = (
        db.query(func.count(User.id))
        .filter(
            User.role == "chef",
            User.is_active == True,
        )
        .scalar()
        or 0
    )

    # =====================================================
    # SUBSCRIPTIONS
    # =====================================================

    active_subscriptions = (
        db.query(func.count(Subscription.id))
        .filter(
            Subscription.status == "active",
        )
        .scalar()
        or 0
    )

    todays_subscriptions = (
        db.query(func.count(Subscription.id))
        .filter(
            Subscription.created_at >= today_start_india,
            Subscription.created_at < tomorrow_start_india,
        )
        .scalar()
        or 0
    )

    # =====================================================
    # PAYMENT BREAKDOWN
    # =====================================================

    cod_orders = (
        db.query(func.count(Order.id))
        .filter(
            Order.created_at >= today_start_utc,
            Order.created_at < tomorrow_start_utc,
            Order.status != "cancelled",
            func.lower(
                func.coalesce(
                    Order.payment_method,
                    ""
                )
            ) == "cod",
        )
        .scalar()
        or 0
    )

    upi_orders = (
        db.query(func.count(Order.id))
        .filter(
            Order.created_at >= today_start_utc,
            Order.created_at < tomorrow_start_utc,
            Order.status != "cancelled",
            func.lower(
                func.coalesce(
                    Order.payment_method,
                    ""
                )
            ).in_(
                [
                    "upi",
                    "online",
                    "razorpay",
                ]
            ),
        )
        .scalar()
        or 0
    )

    card_orders = (
        db.query(func.count(Order.id))
        .filter(
            Order.created_at >= today_start_utc,
            Order.created_at < tomorrow_start_utc,
            Order.status != "cancelled",
            func.lower(
                func.coalesce(
                    Order.payment_method,
                    ""
                )
            ).in_(
                [
                    "card",
                    "credit_card",
                    "debit_card",
                ]
            ),
        )
        .scalar()
        or 0
    )

    # =====================================================
    # RECENT ORDERS
    # =====================================================

    recent_order_rows = (
        db.query(Order)
        .order_by(
            Order.created_at.desc()
        )
        .limit(5)
        .all()
    )

    recent_orders = []

    for recent_order in recent_order_rows:

        created_at_ist = None

        if recent_order.created_at:

            if recent_order.created_at.tzinfo is None:

                created_at_ist = (
                    recent_order.created_at
                    .replace(
                        tzinfo=utc_tz
                    )
                    .astimezone(
                        india_tz
                    )
                )

            else:

                created_at_ist = (
                    recent_order.created_at
                    .astimezone(
                        india_tz
                    )
                )

        # -------------------------------------------------
        # FIRST ITEM
        # -------------------------------------------------

        first_item_name = "Order"

        if recent_order.items:

            first_item_name = (
                recent_order.items[0].item_name
                or "Order"
            )

        # -------------------------------------------------
        # CUSTOMER NAME
        # -------------------------------------------------

        customer_name = (
            recent_order.customer_name
            or "Customer"
        )

        recent_orders.append(
            {
                "id": str(
                    recent_order.id
                ),

                "customer": customer_name,

                "item": first_item_name,

                "amount": (
                    round(
                        float(
                            recent_order.total_price
                            or 0
                        ),
                        2,
                    )
                ),

                "status": (
                    recent_order.status
                ),

                "payment_method": (
                    recent_order.payment_method
                ),

                "time": (
                    created_at_ist.strftime(
                        "%d %b, %I:%M %p"
                    )
                    if created_at_ist
                    else "-"
                ),
            }
        )

    # =====================================================
    # TOMORROW SPECIAL
    # =====================================================

    tomorrow_specials = (
        db.query(TomorrowSpecial)
        .filter(
            TomorrowSpecial.special_date
            == tomorrow_start_india.date(),

            TomorrowSpecial.is_active == 1,
        )
        .all()
    )

    tomorrow_special_preorders = 0

    tomorrow_special_plates = 0

    tomorrow_special_max_plates = 0

    tomorrow_special_remaining = 0

    for special in tomorrow_specials:

        # -------------------------------------------------
        # MAX PLATES
        # -------------------------------------------------

        tomorrow_special_max_plates += (
            special.max_plates or 0
        )

        # -------------------------------------------------
        # PRE-ORDER COUNT
        # -------------------------------------------------

        preorder_count = (
            db.query(
                func.count(
                    TomorrowSpecialPreOrder.id
                )
            )
            .filter(
                TomorrowSpecialPreOrder.special_id
                == special.id
            )
            .scalar()
            or 0
        )

        tomorrow_special_preorders += (
            preorder_count
        )

        # -------------------------------------------------
        # PLATES BOOKED
        # -------------------------------------------------

        booked_plates = (
            db.query(
                func.coalesce(
                    func.sum(
                        TomorrowSpecialPreOrder.quantity
                    ),
                    0,
                )
            )
            .filter(
                TomorrowSpecialPreOrder.special_id
                == special.id
            )
            .scalar()
            or 0
        )

        tomorrow_special_plates += int(
            booked_plates
        )

        # -------------------------------------------------
        # REMAINING
        # -------------------------------------------------

        remaining_for_special = max(
            (
                special.max_plates or 0
            )
            - int(booked_plates),
            0,
        )

        tomorrow_special_remaining += (
            remaining_for_special
        )

    # =====================================================
    # TODAY'S DIET STATUS
    # =====================================================

    diet_on = (
        db.query(
            func.count(
                func.distinct(
                    SubscriptionMealSchedule.subscription_id
                )
            )
        )
        .join(
            Subscription,
            Subscription.id
            == SubscriptionMealSchedule.subscription_id,
        )
        .filter(
            Subscription.status == "active",

            SubscriptionMealSchedule.date
            == now_india.date(),

            SubscriptionMealSchedule.status == "on",
        )
        .scalar()
        or 0
    )

    diet_off = (
        db.query(
            func.count(
                func.distinct(
                    SubscriptionMealSchedule.subscription_id
                )
            )
        )
        .join(
            Subscription,
            Subscription.id
            == SubscriptionMealSchedule.subscription_id,
        )
        .filter(
            Subscription.status == "active",

            SubscriptionMealSchedule.date
            == now_india.date(),

            SubscriptionMealSchedule.status == "off",
        )
        .scalar()
        or 0
    )

    # =====================================================
    # SUBSCRIPTIONS EXPIRING IN NEXT 7 DAYS
    # =====================================================

    expiring_soon = (
        db.query(
            func.count(
                Subscription.id
            )
        )
        .filter(
            Subscription.status == "active",

            Subscription.end_date >= now_india,

            Subscription.end_date
            <= now_india + timedelta(days=7),
        )
        .scalar()
        or 0
    )

    # =====================================================
    # RESPONSE
    # =====================================================

    return {

        "success": True,

        # -------------------------------------------------
        # DATE / TIME
        # -------------------------------------------------

        "date": now_india.strftime(
            "%d %b %Y"
        ),

        "time": now_india.strftime(
            "%I:%M %p"
        ),

        # -------------------------------------------------
        # ORDERS
        # -------------------------------------------------

        "orders": {

            "total": total_orders,

            "today": todays_orders,

            "pending": pending_orders,

            "preparing": preparing_orders,

            "out_for_delivery":
                out_for_delivery_orders,

            "delivered":
                delivered_orders,

            "completed":
                delivered_orders,

            "cancelled":
                cancelled_orders,
        },

        # -------------------------------------------------
        # REVENUE
        # -------------------------------------------------

        "revenue": {

            "today": round(
                float(todays_revenue),
                2,
            ),

            "total": round(
                float(total_revenue),
                2,
            ),
        },

        # -------------------------------------------------
        # CUSTOMERS
        # -------------------------------------------------

        "customers": {

            "total":
                total_customers,

            "active":
                active_customers,
        },

        # -------------------------------------------------
        # CHEFS
        # -------------------------------------------------

        "chefs": {

            "total":
                total_chefs,

            "active":
                active_chefs,
        },

        # -------------------------------------------------
        # SUBSCRIPTIONS
        # -------------------------------------------------

        "subscriptions": {

            "active":
                active_subscriptions,

            "today":
                todays_subscriptions,
        },

        # -------------------------------------------------
        # PAYMENT BREAKDOWN
        # -------------------------------------------------

        "payments": {

            "cod":
                cod_orders,

            "upi":
                upi_orders,

            "card":
                card_orders,
        },

        # -------------------------------------------------
        # RECENT ORDERS
        # -------------------------------------------------

        "recent_orders":
            recent_orders,

        # -------------------------------------------------
        # TOMORROW SPECIAL
        # -------------------------------------------------

        "tomorrow_special": {

            "preorders":
                tomorrow_special_preorders,

            "plates":
                tomorrow_special_plates,

            "max_plates":
                tomorrow_special_max_plates,

            "remaining":
                tomorrow_special_remaining,
        },

        # -------------------------------------------------
        # DIET STATUS
        # -------------------------------------------------

        "diet": {

            "on":
                diet_on,

            "off":
                diet_off,
        },

        # -------------------------------------------------
        # EXTRA SUBSCRIPTION INFO
        # -------------------------------------------------

        "subscription_extra": {

            "expiring_soon":
                expiring_soon,
        },
    }
# =========================================================
# ADMIN ORDERS
#
# FEATURES:
# - All orders
# - Status filter
# - Customer search
# - Chef search
# - Pagination
# - Customer information
# - Chef information
# - Order items
# - Payment information
# - Refund information
# - Order time
# =========================================================
# =========================================================
# 📊 ADMIN ANALYTICS
# =========================================================
#
# Premium business analytics API
#
# FEATURES:
# - Revenue summary
# - Orders summary
# - Customers summary
# - Active subscriptions
# - Daily revenue trend
# - Daily orders trend
# - Order status breakdown
# - Payment method breakdown
# - Subscription trend
# - Date range support
#
# =========================================================


@router.get("/analytics")
def admin_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role(["admin"])
    ),
    days: int = Query(
        30,
        ge=7,
        le=365,
        description="Analytics period in days",
    ),
):
    # =====================================================
    # TIMEZONE
    # =====================================================

    india_tz = ZoneInfo("Asia/Kolkata")
    utc_tz = ZoneInfo("UTC")

    now_india = datetime.now(india_tz)

    # Current period
    period_start_india = (
        now_india
        - timedelta(days=days - 1)
    ).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    period_end_india = (
        now_india
        + timedelta(days=1)
    ).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    period_start_utc = (
        period_start_india
        .astimezone(utc_tz)
        .replace(tzinfo=None)
    )

    period_end_utc = (
        period_end_india
        .astimezone(utc_tz)
        .replace(tzinfo=None)
    )

    # =====================================================
    # PREVIOUS PERIOD
    # =====================================================

    previous_period_end_india = period_start_india

    previous_period_start_india = (
        previous_period_end_india
        - timedelta(days=days)
    )

    previous_period_start_utc = (
        previous_period_start_india
        .astimezone(utc_tz)
        .replace(tzinfo=None)
    )

    previous_period_end_utc = (
        previous_period_end_india
        .astimezone(utc_tz)
        .replace(tzinfo=None)
    )

    # =====================================================
    # CURRENT ORDERS
    # =====================================================

    current_orders_query = (
        db.query(Order)
        .filter(
            Order.created_at >= period_start_utc,
            Order.created_at < period_end_utc,
            Order.status != "cancelled",
        )
    )

    current_orders = current_orders_query.all()

    # =====================================================
    # PREVIOUS ORDERS
    # =====================================================

    previous_orders_count = (
        db.query(func.count(Order.id))
        .filter(
            Order.created_at >= previous_period_start_utc,
            Order.created_at < previous_period_end_utc,
            Order.status != "cancelled",
        )
        .scalar()
        or 0
    )

    # =====================================================
    # CURRENT REVENUE
    # =====================================================

    current_revenue = (
        db.query(
            func.coalesce(
                func.sum(Order.total_price),
                0,
            )
        )
        .filter(
            Order.created_at >= period_start_utc,
            Order.created_at < period_end_utc,
            Order.status != "cancelled",
        )
        .scalar()
        or 0
    )

    current_revenue = float(
        current_revenue
    )

    # =====================================================
    # PREVIOUS REVENUE
    # =====================================================

    previous_revenue = (
        db.query(
            func.coalesce(
                func.sum(Order.total_price),
                0,
            )
        )
        .filter(
            Order.created_at >= previous_period_start_utc,
            Order.created_at < previous_period_end_utc,
            Order.status != "cancelled",
        )
        .scalar()
        or 0
    )

    previous_revenue = float(
        previous_revenue
    )

    # =====================================================
    # ORDER COUNT
    # =====================================================

    current_orders_count = len(
        current_orders
    )

    # =====================================================
    # AVERAGE ORDER VALUE
    # =====================================================

    average_order_value = (
        current_revenue / current_orders_count
        if current_orders_count > 0
        else 0
    )

    # =====================================================
    # GROWTH CALCULATOR
    # =====================================================

    def calculate_growth(
        current_value,
        previous_value,
    ):
        if previous_value == 0:
            if current_value == 0:
                return 0.0
            return 100.0

        return round(
            (
                (
                    current_value
                    - previous_value
                )
                / previous_value
            )
            * 100,
            2,
        )

    revenue_growth = calculate_growth(
        current_revenue,
        previous_revenue,
    )

    orders_growth = calculate_growth(
        current_orders_count,
        previous_orders_count,
    )

    # =====================================================
    # CUSTOMER SUMMARY
    # =====================================================

    total_customers = (
        db.query(func.count(User.id))
        .filter(
            User.role == "customer"
        )
        .scalar()
        or 0
    )

    active_customers = (
        db.query(func.count(User.id))
        .filter(
            User.role == "customer",
            User.is_active == True,
        )
        .scalar()
        or 0
    )

    # =====================================================
    # NEW CUSTOMERS IN PERIOD
    # =====================================================

    new_customers = (
        db.query(func.count(User.id))
        .filter(
            User.role == "customer",
            User.created_at >= period_start_utc,
            User.created_at < period_end_utc,
        )
        .scalar()
        or 0
    )

    # =====================================================
    # SUBSCRIPTIONS
    # =====================================================

    active_subscriptions = (
        db.query(func.count(Subscription.id))
        .filter(
            Subscription.status == "active",
        )
        .scalar()
        or 0
    )

    new_subscriptions = (
        db.query(func.count(Subscription.id))
        .filter(
            Subscription.created_at >= period_start_utc,
            Subscription.created_at < period_end_utc,
        )
        .scalar()
        or 0
    )

    # =====================================================
    # ORDER STATUS BREAKDOWN
    # =====================================================

    status_summary = {
        "pending": 0,
        "preparing": 0,
        "out_for_delivery": 0,
        "delivered": 0,
        "cancelled": 0,
    }

    status_rows = (
        db.query(
            Order.status,
            func.count(Order.id),
        )
        .filter(
            Order.created_at >= period_start_utc,
            Order.created_at < period_end_utc,
        )
        .group_by(Order.status)
        .all()
    )

    for order_status, count in status_rows:
        if order_status in status_summary:
            status_summary[
                order_status
            ] = int(count)

    # =====================================================
    # PAYMENT BREAKDOWN
    # =====================================================

    payment_summary = {
        "cod": 0,
        "upi": 0,
        "card": 0,
        "other": 0,
    }

    payment_rows = (
        db.query(
            Order.payment_method,
            func.count(Order.id),
        )
        .filter(
            Order.created_at >= period_start_utc,
            Order.created_at < period_end_utc,
            Order.status != "cancelled",
        )
        .group_by(Order.payment_method)
        .all()
    )

    for payment_method, count in payment_rows:

        method = (
            str(payment_method)
            .strip()
            .lower()
            if payment_method
            else "other"
        )

        if method == "cod":
            payment_summary["cod"] += int(count)

        elif method in {
            "upi",
            "online",
            "razorpay",
        }:
            payment_summary["upi"] += int(count)

        elif method in {
            "card",
            "credit_card",
            "debit_card",
        }:
            payment_summary["card"] += int(count)

        else:
            payment_summary["other"] += int(count)

    # =====================================================
    # DAILY TREND
    # =====================================================

    daily = {}

    for index in range(days):

        date_value = (
            period_start_india
            + timedelta(days=index)
        ).date()

        key = date_value.isoformat()

        daily[key] = {
            "date": key,
            "label": date_value.strftime(
                "%d %b"
            ),
            "orders": 0,
            "revenue": 0.0,
        }

    # =====================================================
    # BUILD DAILY ORDER / REVENUE TREND
    # =====================================================

    for order in current_orders:

        created_at = order.created_at

        if not created_at:
            continue

        if created_at.tzinfo is None:
            created_at_india = (
                created_at
                .replace(tzinfo=utc_tz)
                .astimezone(india_tz)
            )
        else:
            created_at_india = (
                created_at.astimezone(
                    india_tz
                )
            )

        date_key = (
            created_at_india.date()
            .isoformat()
        )

        if date_key not in daily:
            continue

        daily[date_key]["orders"] += 1

        daily[date_key]["revenue"] += float(
            order.total_price or 0
        )

    daily_trend = list(
        daily.values()
    )

    for item in daily_trend:
        item["revenue"] = round(
            item["revenue"],
            2,
        )

    # =====================================================
    # BEST DAY
    # =====================================================

    best_revenue_day = None

    if daily_trend:

        best_revenue_day = max(
            daily_trend,
            key=lambda item: item["revenue"],
        )

    # =====================================================
    # PERIOD START / END
    # =====================================================

    return {
        "success": True,

        "period": {
            "days": days,
            "start": period_start_india.strftime(
                "%Y-%m-%d"
            ),
            "end": (
                period_end_india
                - timedelta(days=1)
            ).strftime(
                "%Y-%m-%d"
            ),
            "generated_at": now_india.isoformat(),
        },

        "overview": {
            "revenue": round(
                current_revenue,
                2,
            ),

            "revenue_growth": revenue_growth,

            "orders": current_orders_count,

            "orders_growth": orders_growth,

            "average_order_value": round(
                average_order_value,
                2,
            ),

            "customers": total_customers,

            "active_customers": active_customers,

            "new_customers": new_customers,

            "active_subscriptions":
                active_subscriptions,

            "new_subscriptions":
                new_subscriptions,
        },

        "orders": {
            "total": current_orders_count,

            "pending":
                status_summary["pending"],

            "preparing":
                status_summary["preparing"],

            "out_for_delivery":
                status_summary[
                    "out_for_delivery"
                ],

            "delivered":
                status_summary["delivered"],

            "cancelled":
                status_summary["cancelled"],
        },

        "revenue": {
            "current": round(
                current_revenue,
                2,
            ),

            "previous": round(
                previous_revenue,
                2,
            ),

            "growth": revenue_growth,
        },

        "status_breakdown": status_summary,

        "payment_breakdown":
            payment_summary,

        "daily_trend":
            daily_trend,

        "best_day":
            best_revenue_day,
    }


@router.get("/orders")
def admin_orders(
    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_role(["admin"])
    ),

    page: int = Query(
        1,
        ge=1,
    ),

    limit: int = Query(
        20,
        ge=1,
        le=100,
    ),

    status: str | None = Query(
        None,
        description=(
            "pending, preparing, "
            "out_for_delivery, delivered, cancelled"
        ),
    ),

    search: str | None = Query(
        None,
        description=(
            "Search customer name, "
            "phone, chef name"
        ),
    ),
):
    # =====================================================
    # ALIASES
    #
    # users table is used for both customer and chef.
    # =====================================================

    CustomerUser = aliased(User)
    ChefUser = aliased(User)

    # =====================================================
    # BASE QUERY
    # =====================================================

    query = (
        db.query(
            Order,
            CustomerUser,
            ChefUser,
        )
        .outerjoin(
            CustomerUser,
            CustomerUser.id == Order.user_id,
        )
        .outerjoin(
            ChefUser,
            ChefUser.id == Order.chef_id,
        )
    )

    # =====================================================
    # STATUS FILTER
    # =====================================================

    if status:
        normalized_status = status.strip().lower()

        # Frontend can use "completed"
        # while database currently uses "delivered".
        if normalized_status == "completed":
            normalized_status = "delivered"

        allowed_statuses = {
            "pending",
            "preparing",
            "out_for_delivery",
            "delivered",
            "cancelled",
        }

        if normalized_status not in allowed_statuses:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid status. Allowed: "
                    "pending, preparing, "
                    "out_for_delivery, delivered, cancelled"
                ),
            )

        query = query.filter(
            Order.status == normalized_status
        )

    # =====================================================
    # SEARCH
    # =====================================================

    if search:
        search_value = search.strip()

        if search_value:

            search_pattern = (
                f"%{search_value}%"
            )

            query = query.filter(
                or_(
                    Order.customer_name.ilike(
                        search_pattern
                    ),

                    Order.phone.ilike(
                        search_pattern
                    ),

                    CustomerUser.name.ilike(
                        search_pattern
                    ),

                    CustomerUser.email.ilike(
                        search_pattern
                    ),

                    ChefUser.name.ilike(
                        search_pattern
                    ),

                    ChefUser.email.ilike(
                        search_pattern
                    ),

                    ChefUser.phone.ilike(
                        search_pattern
                    ),
                )
            )

    # =====================================================
    # TOTAL MATCHING ORDERS
    # =====================================================

    total = query.count()

    # =====================================================
    # STATUS SUMMARY
    #
    # This summary is for ALL orders, not just current page.
    # =====================================================

    status_rows = (
        db.query(
            Order.status,
            func.count(Order.id),
        )
        .group_by(Order.status)
        .all()
    )

    status_summary = {
        "pending": 0,
        "preparing": 0,
        "out_for_delivery": 0,
        "delivered": 0,
        "cancelled": 0,
    }

    for order_status, count in status_rows:

        if order_status == "pending":
            status_summary["pending"] = count

        elif order_status == "preparing":
            status_summary["preparing"] = count

        elif order_status == "out_for_delivery":
            status_summary["out_for_delivery"] = count

        elif order_status == "delivered":
            status_summary["delivered"] = count

        elif order_status == "cancelled":
            status_summary["cancelled"] = count

    # =====================================================
    # PAGINATION
    # =====================================================

    offset = (
        (page - 1)
        * limit
    )

    rows = (
        query
        .order_by(
            Order.created_at.desc()
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    # =====================================================
    # BUILD ORDERS
    # =====================================================

    orders = []

    india_tz = ZoneInfo(
        "Asia/Kolkata"
    )

    for order, customer, chef in rows:

        # =================================================
        # ITEMS
        # =================================================

        items = []

        for item in (
            order.items or []
        ):

            items.append(
                {
                    "id": str(item.id),

                    "menu_id": (
                        str(item.menu_id)
                        if item.menu_id
                        else None
                    ),

                    "special_id": (
                        str(item.special_id)
                        if item.special_id
                        else None
                    ),

                    "name": item.item_name,

                    "quantity": item.quantity,

                    "price": (
                        round(
                            float(item.price),
                            2,
                        )
                        if item.price is not None
                        else 0.0
                    ),

                    "meal_type": item.meal_type,

                    "menu_date": (
                        item.menu_date.isoformat()
                        if item.menu_date
                        else None
                    ),

                    "image": item.item_image,
                }
            )

        # =================================================
        # ORDER CREATED TIME
        # =================================================

        created_at = order.created_at

        created_at_ist = None

        if created_at:

            if created_at.tzinfo is None:
                created_at_ist = (
                    created_at
                    .replace(
                        tzinfo=ZoneInfo(
                            "UTC"
                        )
                    )
                    .astimezone(
                        india_tz
                    )
                )

            else:
                created_at_ist = (
                    created_at
                    .astimezone(
                        india_tz
                    )
                )

        # =================================================
        # CUSTOMER
        # =================================================

        customer_data = {
            "id": (
                str(customer.id)
                if customer
                else (
                    str(order.user_id)
                    if order.user_id
                    else None
                )
            ),

            "name": (
                customer.name
                if customer
                else order.customer_name
            ),

            "email": (
                customer.email
                if customer
                else None
            ),

            "phone": (
                customer.phone
                if customer
                else order.phone
            ),
        }

        # =================================================
        # CHEF
        # =================================================

        chef_data = {
            "id": (
                str(chef.id)
                if chef
                else (
                    str(order.chef_id)
                    if order.chef_id
                    else None
                )
            ),

            "name": (
                chef.name
                if chef
                else None
            ),

            "email": (
                chef.email
                if chef
                else None
            ),

            "phone": (
                chef.phone
                if chef
                else None
            ),
        }

        # =================================================
        # ORDER RESPONSE
        # =================================================

        orders.append(
            {
                "id": str(order.id),

                "order_id": str(
                    order.id
                ),

                "customer": customer_data,

                "chef": chef_data,

                "customer_name": (
                    order.customer_name
                ),

                "phone": order.phone,

                "address": order.address,

                "items": items,

                "items_count": len(
                    items
                ),

                "total_price": (
                    round(
                        float(
                            order.total_price
                        ),
                        2,
                    )
                    if order.total_price
                    is not None
                    else 0.0
                ),

                "status": order.status,

                # Delivered is treated as
                # completed in Admin UI.
                "completed": (
                    order.status
                    == "delivered"
                ),

                "payment_method": (
                    order.payment_method
                ),

                "payment_status": (
                    order.payment_status
                ),

                "payment_id": (
                    order.payment_id
                ),

                "cod_confirmed": (
                    order.cod_confirmed
                ),

                "refund_status": (
                    order.refund_status
                ),

                "refund_amount": (
                    round(
                        float(
                            order.refund_amount
                        ),
                        2,
                    )
                    if order.refund_amount
                    is not None
                    else 0.0
                ),

                "refund_date": (
                    order.refund_date.isoformat()
                    if order.refund_date
                    else None
                ),

                "created_at": (
                    created_at.isoformat()
                    if created_at
                    else None
                ),

                "created_at_ist": (
                    created_at_ist.isoformat()
                    if created_at_ist
                    else None
                ),
            }
        )

    # =====================================================
    # COMPLETED ALIAS
    # =====================================================

    status_summary["completed"] = (
        status_summary["delivered"]
    )

    # =====================================================
    # RESPONSE
    # =====================================================

    total_pages = (
        (total + limit - 1)
        // limit
        if total > 0
        else 0
    )

    return {
        "success": True,

        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages,
            "has_next": (
                page < total_pages
            ),
            "has_previous": (
                page > 1
            ),
        },

        "summary": {
            "total": sum(
                status_summary.values()
            ),

            "pending": status_summary[
                "pending"
            ],

            "preparing": status_summary[
                "preparing"
            ],

            "out_for_delivery": status_summary[
                "out_for_delivery"
            ],

            "delivered": status_summary[
                "delivered"
            ],

            "completed": status_summary[
                "completed"
            ],

            "cancelled": status_summary[
                "cancelled"
            ],
        },

        "orders": orders,
    }


# =========================================================
# ADMIN SINGLE ORDER DETAIL
# =========================================================

@router.get("/orders/{order_id}")
def admin_order_detail(
    order_id: str,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_role(["admin"])
    ),
):
    # =====================================================
    # VALIDATE UUID
    # =====================================================

    try:
        order_uuid = UUIDType(
            order_id
        )

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid order ID",
        )

    # =====================================================
    # GET ORDER
    # =====================================================

    order = (
        db.query(Order)
        .filter(
            Order.id == order_uuid
        )
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    # =====================================================
    # CUSTOMER
    # =====================================================

    customer = None

    if order.user_id:

        customer = (
            db.query(User)
            .filter(
                User.id == order.user_id
            )
            .first()
        )

    # =====================================================
    # CHEF
    # =====================================================

    chef = None

    if order.chef_id:

        chef = (
            db.query(User)
            .filter(
                User.id == order.chef_id
            )
            .first()
        )

    # =====================================================
    # ITEMS
    # =====================================================

    items = []

    for item in (
        order.items or []
    ):

        items.append(
            {
                "id": str(item.id),

                "menu_id": (
                    str(item.menu_id)
                    if item.menu_id
                    else None
                ),

                "special_id": (
                    str(item.special_id)
                    if item.special_id
                    else None
                ),

                "name": item.item_name,

                "quantity": item.quantity,

                "price": (
                    round(
                        float(item.price),
                        2,
                    )
                    if item.price is not None
                    else 0.0
                ),

                "meal_type": item.meal_type,

                "menu_date": (
                    item.menu_date.isoformat()
                    if item.menu_date
                    else None
                ),

                "image": item.item_image,
            }
        )

    # =====================================================
    # TIME
    # =====================================================

    india_tz = ZoneInfo(
        "Asia/Kolkata"
    )

    created_at_ist = None

    if order.created_at:

        if order.created_at.tzinfo is None:

            created_at_ist = (
                order.created_at
                .replace(
                    tzinfo=ZoneInfo(
                        "UTC"
                    )
                )
                .astimezone(
                    india_tz
                )
            )

        else:

            created_at_ist = (
                order.created_at
                .astimezone(
                    india_tz
                )
            )

    # =====================================================
    # RESPONSE
    # =====================================================

    return {
        "success": True,

        "order": {
            "id": str(
                order.id
            ),

            "order_id": str(
                order.id
            ),

            # ---------------------------------------------
            # CUSTOMER
            # ---------------------------------------------

            "customer": {
                "id": (
                    str(customer.id)
                    if customer
                    else (
                        str(order.user_id)
                        if order.user_id
                        else None
                    )
                ),

                "name": (
                    customer.name
                    if customer
                    else order.customer_name
                ),

                "email": (
                    customer.email
                    if customer
                    else None
                ),

                "phone": (
                    customer.phone
                    if customer
                    else order.phone
                ),
            },

            # ---------------------------------------------
            # CHEF
            # ---------------------------------------------

            "chef": {
                "id": (
                    str(chef.id)
                    if chef
                    else (
                        str(order.chef_id)
                        if order.chef_id
                        else None
                    )
                ),

                "name": (
                    chef.name
                    if chef
                    else None
                ),

                "email": (
                    chef.email
                    if chef
                    else None
                ),

                "phone": (
                    chef.phone
                    if chef
                    else None
                ),
            },

            # ---------------------------------------------
            # DELIVERY
            # ---------------------------------------------

            "customer_name": (
                order.customer_name
            ),

            "phone": order.phone,

            "address": order.address,

            # ---------------------------------------------
            # ITEMS
            # ---------------------------------------------

            "items": items,

            "items_count": len(
                items
            ),

            # ---------------------------------------------
            # PRICE
            # ---------------------------------------------

            "total_price": (
                round(
                    float(
                        order.total_price
                    ),
                    2,
                )
                if order.total_price
                is not None
                else 0.0
            ),

            # ---------------------------------------------
            # STATUS
            # ---------------------------------------------

            "status": order.status,

            "completed": (
                order.status
                == "delivered"
            ),

            # ---------------------------------------------
            # PAYMENT
            # ---------------------------------------------

            "payment_method": (
                order.payment_method
            ),

            "payment_status": (
                order.payment_status
            ),

            "payment_id": (
                order.payment_id
            ),

            "cod_confirmed": (
                order.cod_confirmed
            ),

            # ---------------------------------------------
            # REFUND
            # ---------------------------------------------

            "refund_status": (
                order.refund_status
            ),

            "refund_amount": (
                round(
                    float(
                        order.refund_amount
                    ),
                    2,
                )
                if order.refund_amount
                is not None
                else 0.0
            ),

            "refund_date": (
                order.refund_date.isoformat()
                if order.refund_date
                else None
            ),

            # ---------------------------------------------
            # TIME
            # ---------------------------------------------

            "created_at": (
                order.created_at.isoformat()
                if order.created_at
                else None
            ),

            "created_at_ist": (
                created_at_ist.isoformat()
                if created_at_ist
                else None
            ),
        },
    }
    
    
# =========================================================
# 🍱 ADMIN - TOMORROW SPECIAL ORDERS
#
# FEATURES:
# - All Tomorrow Special pre-orders
# - Customer information
# - Customer phone/email
# - Delivery address
# - Special information
# - Quantity / plates
# - Unit price
# - Total amount
# - Chef information
# - Order status
# - Payment information
# - Order time
# - Pagination
# =========================================================

@router.get("/tomorrow-special/orders")
def admin_tomorrow_special_orders(
    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_role(["admin"])
    ),

    page: int = Query(
        1,
        ge=1,
    ),

    limit: int = Query(
        20,
        ge=1,
        le=100,
    ),

    search: str | None = Query(
        None,
        description="Search customer, phone, email, dish or chef",
    ),

    status: str | None = Query(
        None,
        description="pending, preparing, out_for_delivery, delivered, cancelled",
    ),
):
    # =====================================================
    # 👥 USER ALIASES
    # =====================================================

    CustomerUser = aliased(User)
    ChefUser = aliased(User)

    # =====================================================
    # 🔎 BASE QUERY
    # =====================================================

    query = (
        db.query(
            TomorrowSpecialPreOrder,
            TomorrowSpecial,
            Order,
            CustomerUser,
            ChefUser,
        )
        .join(
            TomorrowSpecial,
            TomorrowSpecial.id
            == TomorrowSpecialPreOrder.special_id,
        )
        .outerjoin(
            Order,
            Order.id
            == TomorrowSpecialPreOrder.order_id,
        )
        .outerjoin(
            CustomerUser,
            CustomerUser.id
            == TomorrowSpecialPreOrder.customer_id,
        )
        .outerjoin(
            ChefUser,
            ChefUser.id
            == TomorrowSpecial.chef_id,
        )
    )

    # =====================================================
    # 🔍 SEARCH
    # =====================================================

    if search:
        search_value = search.strip()

        if search_value:
            pattern = f"%{search_value}%"

            query = query.filter(
                or_(
                    CustomerUser.name.ilike(pattern),
                    CustomerUser.email.ilike(pattern),
                    CustomerUser.phone.ilike(pattern),

                    Order.customer_name.ilike(pattern),
                    Order.phone.ilike(pattern),

                    TomorrowSpecial.dish_name.ilike(pattern),

                    ChefUser.name.ilike(pattern),
                    ChefUser.email.ilike(pattern),
                    ChefUser.phone.ilike(pattern),
                )
            )

    # =====================================================
    # 📊 STATUS FILTER
    # =====================================================

    if status:
        normalized_status = status.strip().lower()

        if normalized_status == "completed":
            normalized_status = "delivered"

        allowed_statuses = {
            "pending",
            "preparing",
            "out_for_delivery",
            "delivered",
            "cancelled",
        }

        if normalized_status not in allowed_statuses:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid status. Allowed: "
                    "pending, preparing, "
                    "out_for_delivery, delivered, cancelled"
                ),
            )

        query = query.filter(
            Order.status == normalized_status
        )

    # =====================================================
    # 📊 TOTAL
    # =====================================================

    total = query.count()

    # =====================================================
    # 📄 PAGINATION
    # =====================================================

    offset = (
        (page - 1)
        * limit
    )

    rows = (
        query
        .order_by(
            TomorrowSpecialPreOrder.created_at.desc()
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    # =====================================================
    # 🇮🇳 TIMEZONE
    # =====================================================

    india_tz = ZoneInfo("Asia/Kolkata")

    # =====================================================
    # 📦 BUILD RESPONSE
    # =====================================================

    orders = []

    total_plates = 0
    total_amount = 0.0

    for (
        pre_order,
        special,
        order,
        customer,
        chef,
    ) in rows:

        quantity = int(
            pre_order.quantity or 0
        )

        unit_price = float(
            pre_order.unit_price or 0
        )

        amount = float(
            pre_order.total_amount or 0
        )

        total_plates += quantity
        total_amount += amount

        # =================================================
        # 🕒 ORDER TIME - IST
        # =================================================

        created_at_ist = None

        created_at = (
            order.created_at
            if order
            else pre_order.created_at
        )

        if created_at:

            if created_at.tzinfo is None:
                created_at_ist = (
                    created_at
                    .replace(
                        tzinfo=ZoneInfo("UTC")
                    )
                    .astimezone(india_tz)
                )

            else:
                created_at_ist = (
                    created_at
                    .astimezone(india_tz)
                )

        # =================================================
        # 👤 CUSTOMER
        # =================================================

        customer_data = {
            "id": (
                str(customer.id)
                if customer
                else (
                    str(pre_order.customer_id)
                    if pre_order.customer_id
                    else None
                )
            ),

            "name": (
                customer.name
                if customer
                else (
                    order.customer_name
                    if order
                    else None
                )
            ),

            "email": (
                customer.email
                if customer
                else None
            ),

            "phone": (
                customer.phone
                if customer
                else (
                    order.phone
                    if order
                    else None
                )
            ),
        }

        # =================================================
        # 👨‍🍳 CHEF
        # =================================================

        chef_data = {
            "id": (
                str(chef.id)
                if chef
                else (
                    str(special.chef_id)
                    if special.chef_id
                    else None
                )
            ),

            "name": (
                chef.name
                if chef
                else "Chef"
            ),

            "email": (
                chef.email
                if chef
                else None
            ),

            "phone": (
                chef.phone
                if chef
                else None
            ),
        }

        # =================================================
        # 🍱 SPECIAL
        # =================================================

        special_data = {
            "id": str(
                special.id
            ),

            "dish_name": (
                special.dish_name
            ),

            "description": (
                special.description
            ),

            "image_url": (
                special.image_url
            ),

            "price": (
                float(special.price)
                if special.price is not None
                else 0.0
            ),

            "original_price": (
                float(special.original_price)
                if special.original_price is not None
                else None
            ),

            "special_date": (
                special.special_date.isoformat()
                if special.special_date
                else None
            ),

            "cutoff_time": (
                special.cutoff_time
            ),

            "max_plates": (
                special.max_plates
            ),

            "pre_orders": (
                special.pre_orders or 0
            ),

            "remaining": max(
                (
                    special.max_plates
                    - (special.pre_orders or 0)
                ),
                0,
            ),

            "food_type": (
                special.food_type
            ),
        }

        # =================================================
        # 📦 ORDER
        # =================================================

        order_data = {
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

            "address": (
                order.address
                if order
                else None
            ),

            "payment_method": (
                order.payment_method
                if order
                else None
            ),

            "payment_status": (
                order.payment_status
                if order
                else None
            ),

            "payment_id": (
                order.payment_id
                if order
                else None
            ),

            "cod_confirmed": (
                order.cod_confirmed
                if order
                else False
            ),

            "refund_status": (
                order.refund_status
                if order
                else None
            ),

            "refund_amount": (
                round(
                    float(order.refund_amount),
                    2,
                )
                if order
                and order.refund_amount is not None
                else 0.0
            ),

            "refund_date": (
                order.refund_date.isoformat()
                if order
                and order.refund_date
                else None
            ),

            "created_at": (
                order.created_at.isoformat()
                if order
                and order.created_at
                else None
            ),

            "created_at_ist": (
                created_at_ist.isoformat()
                if created_at_ist
                else None
            ),
        }

        # =================================================
        # 📋 FINAL ORDER
        # =================================================

        orders.append(
            {
                "pre_order_id": str(
                    pre_order.id
                ),

                "order_id": (
                    str(order.id)
                    if order
                    else None
                ),

                "customer": customer_data,

                "chef": chef_data,

                "special": special_data,

                "quantity": quantity,

                "unit_price": round(
                    unit_price,
                    2,
                ),

                "total_amount": round(
                    amount,
                    2,
                ),

                "order": order_data,

                "created_at": (
                    pre_order.created_at.isoformat()
                    if pre_order.created_at
                    else None
                ),
            }
        )

    # =====================================================
    # 📊 PAGINATION
    # =====================================================

    total_pages = (
        (total + limit - 1)
        // limit
        if total > 0
        else 0
    )

    # =====================================================
    # ✅ RESPONSE
    # =====================================================

    return {
        "success": True,

        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages,
            "has_next": (
                page < total_pages
            ),
            "has_previous": (
                page > 1
            ),
        },

        "summary": {
            "total_orders": total,
            "total_plates": total_plates,
            "total_amount": round(
                total_amount,
                2,
            ),
        },

        "orders": orders,
    }