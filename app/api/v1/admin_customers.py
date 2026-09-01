from datetime import datetime
from uuid import UUID as UUIDType
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role

from app.models.user import User
from app.models.order import Order
from app.models.subscription import Subscription
from app.models.wallet import Wallet
from app.models.wallet_transaction import WalletTransaction


router = APIRouter(
    prefix="/admin/customers",
    tags=["Admin Customers"],
)


# =========================================================
# HELPER — IST TIME
# =========================================================

def to_ist(dt):
    if not dt:
        return None

    india_tz = ZoneInfo("Asia/Kolkata")

    if dt.tzinfo is None:
        return (
            dt
            .replace(tzinfo=ZoneInfo("UTC"))
            .astimezone(india_tz)
        )

    return dt.astimezone(india_tz)


# =========================================================
# HELPER — RELATIVE TIME
#
# Just now
# 5 minutes ago
# 2 hours ago
# 3 days ago
# =========================================================

def relative_time(dt):
    if not dt:
        return None

    dt_ist = to_ist(dt)

    now = datetime.now(
        ZoneInfo("Asia/Kolkata")
    )

    diff = now - dt_ist

    seconds = int(
        diff.total_seconds()
    )

    if seconds < 0:
        return "Just now"

    if seconds < 60:
        return "Just now"

    minutes = seconds // 60

    if minutes < 60:
        return (
            f"{minutes} minute"
            f"{'s' if minutes != 1 else ''} ago"
        )

    hours = minutes // 60

    if hours < 24:
        return (
            f"{hours} hour"
            f"{'s' if hours != 1 else ''} ago"
        )

    days = hours // 24

    if days < 30:
        return (
            f"{days} day"
            f"{'s' if days != 1 else ''} ago"
        )

    months = days // 30

    if months < 12:
        return (
            f"{months} month"
            f"{'s' if months != 1 else ''} ago"
        )

    years = days // 365

    return (
        f"{years} year"
        f"{'s' if years != 1 else ''} ago"
    )


# =========================================================
# 1. CUSTOMER LIST
#
# GET /admin/customers
#
# Search:
# ?search=sachin
#
# Pagination:
# ?page=1&limit=20
# =========================================================

@router.get("")
def admin_customers(
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
        description="Search by name, email or phone",
    ),
):
    # =====================================================
    # BASE CUSTOMER QUERY
    # =====================================================

    query = (
        db.query(User)
        .filter(
            User.role == "customer"
        )
    )

    # =====================================================
    # SEARCH
    # =====================================================

    if search:
        value = search.strip()

        if value:
            pattern = f"%{value}%"

            query = query.filter(
                or_(
                    User.name.ilike(pattern),
                    User.email.ilike(pattern),
                    User.phone.ilike(pattern),
                )
            )

    # =====================================================
    # TOTAL CUSTOMERS
    # =====================================================

    total = query.count()

    # =====================================================
    # PAGINATION
    # =====================================================

    offset = (
        (page - 1)
        * limit
    )

    customers = (
        query
        .order_by(
            User.created_at.desc()
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    # =====================================================
    # CUSTOMER DATA
    # =====================================================

    result = []

    for customer in customers:

        # -----------------------------------------------
        # ORDER COUNTS
        # -----------------------------------------------

        total_orders = (
            db.query(
                func.count(Order.id)
            )
            .filter(
                Order.user_id == customer.id
            )
            .scalar()
            or 0
        )

        completed_orders = (
            db.query(
                func.count(Order.id)
            )
            .filter(
                Order.user_id == customer.id,
                Order.status == "delivered",
            )
            .scalar()
            or 0
        )

        cancelled_orders = (
            db.query(
                func.count(Order.id)
            )
            .filter(
                Order.user_id == customer.id,
                Order.status == "cancelled",
            )
            .scalar()
            or 0
        )

        pending_orders = (
            db.query(
                func.count(Order.id)
            )
            .filter(
                Order.user_id == customer.id,
                Order.status == "pending",
            )
            .scalar()
            or 0
        )

        # -----------------------------------------------
        # TOTAL SPENT
        # Exclude cancelled orders
        # -----------------------------------------------

        total_spent = (
            db.query(
                func.coalesce(
                    func.sum(
                        Order.total_price
                    ),
                    0,
                )
            )
            .filter(
                Order.user_id == customer.id,
                Order.status != "cancelled",
            )
            .scalar()
            or 0
        )

        # -----------------------------------------------
        # WALLET
        # -----------------------------------------------

        wallet = (
            db.query(Wallet)
            .filter(
                Wallet.user_id
                == customer.id
            )
            .first()
        )

        wallet_balance = (
            float(wallet.balance)
            if wallet
            else 0.0
        )

        # -----------------------------------------------
        # ACTIVE SUBSCRIPTION
        # -----------------------------------------------

        active_subscription = (
            db.query(
                func.count(
                    Subscription.id
                )
            )
            .filter(
                Subscription.user_id
                == customer.id,

                Subscription.status
                == "active",
            )
            .scalar()
            or 0
        )

        # -----------------------------------------------
        # PAYMENT COUNTS
        # -----------------------------------------------

        cod_orders = (
            db.query(
                func.count(Order.id)
            )
            .filter(
                Order.user_id == customer.id,
                Order.payment_method.ilike("cod"),
            )
            .scalar()
            or 0
        )

        upi_orders = (
            db.query(
                func.count(Order.id)
            )
            .filter(
                Order.user_id == customer.id,
                Order.payment_method.ilike("upi"),
            )
            .scalar()
            or 0
        )

        card_orders = (
            db.query(
                func.count(Order.id)
            )
            .filter(
                Order.user_id == customer.id,
                Order.payment_method.ilike("card"),
            )
            .scalar()
            or 0
        )

        # -----------------------------------------------
        # LAST ORDER
        # -----------------------------------------------

        last_order = (
            db.query(Order)
            .filter(
                Order.user_id
                == customer.id
            )
            .order_by(
                Order.created_at.desc()
            )
            .first()
        )

        result.append(
            {
                "id": str(
                    customer.id
                ),

                "name": customer.name,

                "email": customer.email,

                "phone": customer.phone,

                "profile_image": (
                    getattr(
                        customer,
                        "profile_image",
                        None,
                    )
                ),

                "is_active": (
                    customer.is_active
                ),

                "is_verified": (
                    customer.is_verified
                ),

                "join_date": (
                    customer.created_at.isoformat()
                    if customer.created_at
                    else None
                ),

                "join_date_relative": (
                    relative_time(
                        customer.created_at
                    )
                    if customer.created_at
                    else None
                ),

                "orders": {
                    "total": total_orders,
                    "completed": completed_orders,
                    "delivered": completed_orders,
                    "cancelled": cancelled_orders,
                    "pending": pending_orders,
                },

                "total_spent": round(
                    float(total_spent),
                    2,
                ),

                "subscriptions": {
                    "active": (
                        active_subscription
                    ),
                },

                "wallet": {
                    "balance": round(
                        wallet_balance,
                        2,
                    ),
                    "wallet_id": (
                        str(wallet.id)
                        if wallet
                        else None
                    ),
                },

                "payments": {
                    "cod": cod_orders,
                    "upi": upi_orders,
                    "card": card_orders,
                },

                "last_order": {
                    "id": (
                        str(last_order.id)
                        if last_order
                        else None
                    ),

                    "status": (
                        last_order.status
                        if last_order
                        else None
                    ),

                    "amount": (
                        round(
                            float(
                                last_order.total_price
                            ),
                            2,
                        )
                        if last_order
                        and last_order.total_price
                        is not None
                        else 0.0
                    ),

                    "created_at": (
                        last_order.created_at.isoformat()
                        if last_order
                        and last_order.created_at
                        else None
                    ),

                    "relative_time": (
                        relative_time(
                            last_order.created_at
                        )
                        if last_order
                        else None
                    ),
                },
            }
        )

    # =====================================================
    # PAGINATION
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

        "customers": result,
    }


# =========================================================
# 2. CUSTOMER DETAIL
#
# GET /admin/customers/{customer_id}
# =========================================================

@router.get("/{customer_id}")
def admin_customer_detail(
    customer_id: str,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_role(["admin"])
    ),
):
    # =====================================================
    # UUID VALIDATION
    # =====================================================

    try:
        customer_uuid = UUIDType(
            customer_id
        )

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid customer ID",
        )

    # =====================================================
    # CUSTOMER
    # =====================================================

    customer = (
        db.query(User)
        .filter(
            User.id == customer_uuid,
            User.role == "customer",
        )
        .first()
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    # =====================================================
    # ORDER COUNTS
    # =====================================================

    total_orders = (
        db.query(
            func.count(Order.id)
        )
        .filter(
            Order.user_id
            == customer.id
        )
        .scalar()
        or 0
    )

    completed_orders = (
        db.query(
            func.count(Order.id)
        )
        .filter(
            Order.user_id
            == customer.id,
            Order.status
            == "delivered",
        )
        .scalar()
        or 0
    )

    cancelled_orders = (
        db.query(
            func.count(Order.id)
        )
        .filter(
            Order.user_id
            == customer.id,
            Order.status
            == "cancelled",
        )
        .scalar()
        or 0
    )

    pending_orders = (
        db.query(
            func.count(Order.id)
        )
        .filter(
            Order.user_id
            == customer.id,
            Order.status
            == "pending",
        )
        .scalar()
        or 0
    )

    preparing_orders = (
        db.query(
            func.count(Order.id)
        )
        .filter(
            Order.user_id
            == customer.id,
            Order.status
            == "preparing",
        )
        .scalar()
        or 0
    )

    delivery_orders = (
        db.query(
            func.count(Order.id)
        )
        .filter(
            Order.user_id
            == customer.id,
            Order.status
            == "out_for_delivery",
        )
        .scalar()
        or 0
    )

    # =====================================================
    # SPENDING
    # =====================================================

    total_spent = (
        db.query(
            func.coalesce(
                func.sum(
                    Order.total_price
                ),
                0,
            )
        )
        .filter(
            Order.user_id
            == customer.id,
            Order.status
            != "cancelled",
        )
        .scalar()
        or 0
    )

    cancelled_amount = (
        db.query(
            func.coalesce(
                func.sum(
                    Order.total_price
                ),
                0,
            )
        )
        .filter(
            Order.user_id
            == customer.id,
            Order.status
            == "cancelled",
        )
        .scalar()
        or 0
    )

    # =====================================================
    # PAYMENT STATISTICS
    # =====================================================

    payment_methods = {}

    payment_rows = (
        db.query(
            Order.payment_method,
            func.count(Order.id),
            func.coalesce(
                func.sum(
                    Order.total_price
                ),
                0,
            ),
        )
        .filter(
            Order.user_id
            == customer.id
        )
        .group_by(
            Order.payment_method
        )
        .all()
    )

    for (
        method,
        count,
        amount,
    ) in payment_rows:

        key = (
            method.lower()
            if method
            else "unknown"
        )

        payment_methods[key] = {
            "orders": count,
            "amount": round(
                float(amount),
                2,
            ),
        }

    # =====================================================
    # WALLET
    # =====================================================

    wallet = (
        db.query(Wallet)
        .filter(
            Wallet.user_id
            == customer.id
        )
        .first()
    )

    wallet_balance = (
        float(wallet.balance)
        if wallet
        else 0.0
    )

    # =====================================================
    # WALLET TRANSACTION COUNT
    # =====================================================

    wallet_transactions_count = (
        db.query(
            func.count(
                WalletTransaction.id
            )
        )
        .filter(
            WalletTransaction.user_id
            == customer.id
        )
        .scalar()
        or 0
    )

    # =====================================================
    # WALLET CREDIT
    # =====================================================

    wallet_credit = (
        db.query(
            func.coalesce(
                func.sum(
                    WalletTransaction.amount
                ),
                0,
            )
        )
        .filter(
            WalletTransaction.user_id
            == customer.id,
            WalletTransaction.transaction_type.in_(
                [
                    "credit",
                    "add",
                    "refund",
                    "cashback",
                ]
            ),
        )
        .scalar()
        or 0
    )

    # =====================================================
    # WALLET DEBIT
    # =====================================================

    wallet_debit = (
        db.query(
            func.coalesce(
                func.sum(
                    WalletTransaction.amount
                ),
                0,
            )
        )
        .filter(
            WalletTransaction.user_id
            == customer.id,
            WalletTransaction.transaction_type.in_(
                [
                    "debit",
                    "deduct",
                    "payment",
                ]
            ),
        )
        .scalar()
        or 0
    )

    # =====================================================
    # SUBSCRIPTIONS
    # =====================================================

    subscriptions = (
        db.query(
            Subscription
        )
        .filter(
            Subscription.user_id
            == customer.id
        )
        .order_by(
            Subscription.created_at.desc()
        )
        .all()
    )

    subscription_data = []

    for subscription in subscriptions:

        subscription_data.append(
            {
                "id": str(
                    subscription.id
                ),

                "chef_id": str(
                    subscription.chef_id
                )
                if subscription.chef_id
                else None,

                "menu_id": str(
                    subscription.menu_id
                )
                if subscription.menu_id
                else None,

                "plan_id": (
                    subscription.plan_id
                ),

                "customer_name": (
                    subscription.customer_name
                ),

                "dish_name": (
                    subscription.dish_name
                ),

                "price": (
                    round(
                        float(
                            subscription.price
                        ),
                        2,
                    )
                    if subscription.price
                    is not None
                    else 0.0
                ),

                "meals_per_day": (
                    subscription.meals_per_day
                ),

                "breakfast_enabled": (
                    subscription.breakfast_enabled
                ),

                "breakfast_price": (
                    round(
                        float(
                            subscription.breakfast_price
                        ),
                        2,
                    )
                    if subscription.breakfast_price
                    is not None
                    else 0.0
                ),

                "delivery_days": (
                    subscription.delivery_days
                ),

                "delivery_time": (
                    subscription.delivery_time
                ),

                "address": (
                    subscription.address
                ),

                "start_date": (
                    subscription.start_date.isoformat()
                    if subscription.start_date
                    else None
                ),

                "end_date": (
                    subscription.end_date.isoformat()
                    if subscription.end_date
                    else None
                ),

                "status": (
                    subscription.status
                ),

                "created_at": (
                    subscription.created_at.isoformat()
                    if subscription.created_at
                    else None
                ),

                "created_relative": (
                    relative_time(
                        subscription.created_at
                    )
                    if subscription.created_at
                    else None
                ),
            }
        )

    # =====================================================
    # RESPONSE
    # =====================================================

    return {
        "success": True,

        "customer": {
            "id": str(
                customer.id
            ),

            "name": customer.name,

            "email": customer.email,

            "phone": customer.phone,

            "profile_image": (
                getattr(
                    customer,
                    "profile_image",
                    None,
                )
            ),

            "role": customer.role,

            "is_active": (
                customer.is_active
            ),

            "is_verified": (
                customer.is_verified
            ),

            "created_at": (
                customer.created_at.isoformat()
                if customer.created_at
                else None
            ),

            "created_relative": (
                relative_time(
                    customer.created_at
                )
                if customer.created_at
                else None
            ),
        },

        "orders": {
            "total": total_orders,
            "completed": completed_orders,
            "delivered": completed_orders,
            "cancelled": cancelled_orders,
            "pending": pending_orders,
            "preparing": preparing_orders,
            "out_for_delivery": delivery_orders,
        },

        "spending": {
            "total_spent": round(
                float(total_spent),
                2,
            ),

            "cancelled_amount": round(
                float(cancelled_amount),
                2,
            ),
        },

        "payments": payment_methods,

        "wallet": {
            "exists": (
                wallet is not None
            ),

            "wallet_id": (
                str(wallet.id)
                if wallet
                else None
            ),

            "balance": round(
                wallet_balance,
                2,
            ),

            "transactions": (
                wallet_transactions_count
            ),

            "total_credit": round(
                float(wallet_credit),
                2,
            ),

            "total_debit": round(
                float(wallet_debit),
                2,
            ),
        },

        "subscriptions": {
            "total": len(
                subscription_data
            ),

            "active": sum(
                1
                for x in subscription_data
                if x["status"] == "active"
            ),

            "history": subscription_data,
        },
    }


# =========================================================
# 3. CUSTOMER WALLET
#
# GET /admin/customers/{customer_id}/wallet
# =========================================================

@router.get("/{customer_id}/wallet")
def admin_customer_wallet(
    customer_id: str,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_role(["admin"])
    ),
):
    # =====================================================
    # UUID
    # =====================================================

    try:
        customer_uuid = UUIDType(
            customer_id
        )

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid customer ID",
        )

    # =====================================================
    # CUSTOMER
    # =====================================================

    customer = (
        db.query(User)
        .filter(
            User.id == customer_uuid,
            User.role == "customer",
        )
        .first()
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    # =====================================================
    # WALLET
    # =====================================================

    wallet = (
        db.query(Wallet)
        .filter(
            Wallet.user_id
            == customer.id
        )
        .first()
    )

    # =====================================================
    # NO WALLET
    # =====================================================

    if not wallet:
        return {
            "success": True,

            "customer": {
                "id": str(
                    customer.id
                ),
                "name": customer.name,
                "email": customer.email,
                "phone": customer.phone,
            },

            "wallet": {
                "exists": False,
                "balance": 0.0,
                "wallet_id": None,
                "transactions": [],
            },
        }

    # =====================================================
    # TRANSACTIONS
    # =====================================================

    transactions = (
        db.query(
            WalletTransaction
        )
        .filter(
            WalletTransaction.user_id
            == customer.id
        )
        .order_by(
            WalletTransaction.created_at.desc()
        )
        .all()
    )

    transaction_data = []

    for transaction in transactions:

        transaction_data.append(
            {
                "id": str(
                    transaction.id
                ),

                "amount": (
                    round(
                        float(
                            transaction.amount
                        ),
                        2,
                    )
                    if transaction.amount
                    is not None
                    else 0.0
                ),

                "transaction_type": (
                    transaction.transaction_type
                ),

                "meal_type": (
                    transaction.meal_type
                ),

                "subscription_id": (
                    str(
                        transaction.subscription_id
                    )
                    if transaction.subscription_id
                    else None
                ),

                "schedule_id": (
                    str(
                        transaction.schedule_id
                    )
                    if transaction.schedule_id
                    else None
                ),

                "description": (
                    transaction.description
                ),

                "created_at": (
                    transaction.created_at.isoformat()
                    if transaction.created_at
                    else None
                ),

                "created_at_ist": (
                    to_ist(
                        transaction.created_at
                    ).isoformat()
                    if transaction.created_at
                    else None
                ),

                "relative_time": (
                    relative_time(
                        transaction.created_at
                    )
                    if transaction.created_at
                    else None
                ),
            }
        )

    # =====================================================
    # RESPONSE
    # =====================================================

    return {
        "success": True,

        "customer": {
            "id": str(
                customer.id
            ),
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
        },

        "wallet": {
            "exists": True,

            "id": str(
                wallet.id
            ),

            "balance": round(
                float(wallet.balance),
                2,
            ),

            "created_at": (
                wallet.created_at.isoformat()
                if wallet.created_at
                else None
            ),

            "updated_at": (
                wallet.updated_at.isoformat()
                if wallet.updated_at
                else None
            ),

            "transactions": (
                transaction_data
            ),
        },
    }


# =========================================================
# 4. CUSTOMER WALLET TRANSACTIONS
#
# GET /admin/customers/{customer_id}/wallet/transactions
#
# Optional:
# ?transaction_type=debit
# ?meal_type=breakfast
# ?page=1&limit=20
# =========================================================

@router.get(
    "/{customer_id}/wallet/transactions"
)
def admin_customer_wallet_transactions(
    customer_id: str,

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

    transaction_type: str | None = Query(
        None
    ),

    meal_type: str | None = Query(
        None
    ),
):
    # =====================================================
    # UUID
    # =====================================================

    try:
        customer_uuid = UUIDType(
            customer_id
        )

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid customer ID",
        )

    # =====================================================
    # CUSTOMER
    # =====================================================

    customer = (
        db.query(User)
        .filter(
            User.id == customer_uuid,
            User.role == "customer",
        )
        .first()
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    # =====================================================
    # QUERY
    # =====================================================

    query = (
        db.query(
            WalletTransaction
        )
        .filter(
            WalletTransaction.user_id
            == customer.id
        )
    )

    # =====================================================
    # TRANSACTION TYPE
    # =====================================================

    if transaction_type:

        query = query.filter(
            WalletTransaction.transaction_type
            == transaction_type.strip()
        )

    # =====================================================
    # MEAL TYPE
    # =====================================================

    if meal_type:

        query = query.filter(
            WalletTransaction.meal_type
            == meal_type.strip()
        )

    # =====================================================
    # TOTAL
    # =====================================================

    total = query.count()

    # =====================================================
    # PAGINATION
    # =====================================================

    offset = (
        (page - 1)
        * limit
    )

    transactions = (
        query
        .order_by(
            WalletTransaction.created_at.desc()
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    # =====================================================
    # DATA
    # =====================================================

    result = []

    for transaction in transactions:

        result.append(
            {
                "id": str(
                    transaction.id
                ),

                "amount": (
                    round(
                        float(
                            transaction.amount
                        ),
                        2,
                    )
                    if transaction.amount
                    is not None
                    else 0.0
                ),

                "transaction_type": (
                    transaction.transaction_type
                ),

                "meal_type": (
                    transaction.meal_type
                ),

                "subscription_id": (
                    str(
                        transaction.subscription_id
                    )
                    if transaction.subscription_id
                    else None
                ),

                "schedule_id": (
                    str(
                        transaction.schedule_id
                    )
                    if transaction.schedule_id
                    else None
                ),

                "description": (
                    transaction.description
                ),

                "created_at": (
                    transaction.created_at.isoformat()
                    if transaction.created_at
                    else None
                ),

                "created_at_ist": (
                    to_ist(
                        transaction.created_at
                    ).isoformat()
                    if transaction.created_at
                    else None
                ),

                "relative_time": (
                    relative_time(
                        transaction.created_at
                    )
                    if transaction.created_at
                    else None
                ),
            }
        )

    # =====================================================
    # PAGINATION
    # =====================================================

    total_pages = (
        (total + limit - 1)
        // limit
        if total > 0
        else 0
    )

    return {
        "success": True,

        "customer": {
            "id": str(
                customer.id
            ),
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
        },

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

        "transactions": result,
    }