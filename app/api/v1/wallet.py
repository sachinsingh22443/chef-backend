from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.api.deps import (
    get_db,
    get_current_user,
    require_role,
)

from app.models.wallet import Wallet
from app.models.wallet_transaction import WalletTransaction
from app.models.user import User
from app.models.subscription import Subscription

from app.schemas.wallet import WalletHistoryResponse

from fastapi import (
    APIRouter,
    Depends,
    Query,
    HTTPException,
)


router = APIRouter(
    prefix="/wallet",
    tags=["Wallet"],
)


# =========================================================
# CUSTOMER WALLET HISTORY
# =========================================================

@router.get(
    "/history",
    response_model=WalletHistoryResponse,
)
def get_wallet_history(
    from_date: date | None = Query(
        default=None,
        description="History start date",
    ),
    to_date: date | None = Query(
        default=None,
        description="History end date",
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    # =====================================================
    # VALIDATE DATE RANGE
    # =====================================================

    if from_date and to_date and from_date > to_date:
        raise HTTPException(
            status_code=400,
            detail="from_date cannot be greater than to_date",
        )

    # =====================================================
    # GET CUSTOMER WALLET
    # =====================================================

    wallet = (
        db.query(Wallet)
        .filter(
            Wallet.user_id == current_user.id
        )
        .first()
    )

    # =====================================================
    # WALLET DOES NOT EXIST
    # =====================================================

    if not wallet:
        return WalletHistoryResponse(
            balance=0.0,
            transactions=[],
        )

    # =====================================================
    # BASE TRANSACTION QUERY
    # =====================================================

    query = (
        db.query(WalletTransaction)
        .filter(
            WalletTransaction.user_id
            == current_user.id
        )
    )

    # =====================================================
    # FROM DATE
    # =====================================================

    if from_date:
        start_datetime = datetime.combine(
            from_date,
            time.min,
        )

        query = query.filter(
            WalletTransaction.created_at
            >= start_datetime
        )

    # =====================================================
    # TO DATE
    # =====================================================

    if to_date:
        end_datetime = datetime.combine(
            to_date + timedelta(days=1),
            time.min,
        )

        query = query.filter(
            WalletTransaction.created_at
            < end_datetime
        )

    # =====================================================
    # GET TRANSACTIONS
    # NEWEST FIRST
    # =====================================================

    transactions = (
        query
        .order_by(
            WalletTransaction.created_at.desc()
        )
        .all()
    )

    # =====================================================
    # RESPONSE
    # =====================================================

    return WalletHistoryResponse(
        balance=wallet.balance,
        transactions=transactions,
    )


# =========================================================
# ADMIN — SUBSCRIBED CUSTOMER WALLETS
# =========================================================

@router.get(
    "/admin/subscribers",
)
def get_admin_subscriber_wallets(
    search: str | None = Query(
        default=None,
        description="Search customer by name, email or phone",
    ),
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin"])),
):

    # =====================================================
    # GET CUSTOMERS WHO HAVE ACTIVE SUBSCRIPTION
    # =====================================================

    active_subscription_user_ids = (
        db.query(Subscription.customer_id)
        .filter(
            Subscription.status == "active"
        )
        .distinct()
        .subquery()
    )

    customers_query = (
        db.query(User)
        .filter(
            User.role == "customer",
            User.id.in_(
                active_subscription_user_ids
            ),
        )
    )

    # =====================================================
    # SEARCH
    # =====================================================

    if search:
        search_value = f"%{search.strip()}%"

        customers_query = customers_query.filter(
            (
                User.name.ilike(search_value)
            )
            |
            (
                User.email.ilike(search_value)
            )
            |
            (
                User.phone.ilike(search_value)
            )
        )

    customers = (
        customers_query
        .order_by(User.name.asc())
        .all()
    )

    # =====================================================
    # RESULT
    # =====================================================

    result = []

    total_wallet_balance = 0.0
    total_credits = 0.0
    total_debits = 0.0
    total_transactions = 0

    # =====================================================
    # TRANSACTION TYPE MAPPING
    # =====================================================

    CREDIT_TYPES = {
        "credit",
        "add",
        "refund",
        "cashback",
        "meal_off_credit",
    }

    DEBIT_TYPES = {
        "debit",
        "deduct",
        "payment",
        "meal_payment",
    }

    # =====================================================
    # PROCESS EACH CUSTOMER
    # =====================================================

    for customer in customers:

        wallet = (
            db.query(Wallet)
            .filter(
                Wallet.user_id == customer.id
            )
            .first()
        )

        # -------------------------------------------------
        # ACTIVE SUBSCRIPTIONS
        # -------------------------------------------------

        subscriptions = (
            db.query(Subscription)
            .filter(
                Subscription.customer_id == customer.id,
                Subscription.status == "active",
            )
            .order_by(
                Subscription.start_date.desc()
            )
            .all()
        )

        # -------------------------------------------------
        # WALLET TRANSACTIONS
        # -------------------------------------------------

        transactions = (
            db.query(WalletTransaction)
            .filter(
                WalletTransaction.user_id
                == customer.id
            )
            .order_by(
                WalletTransaction.created_at.desc()
            )
            .all()
        )

        balance = (
            float(wallet.balance)
            if wallet
            else 0.0
        )

        customer_credit = 0.0
        customer_debit = 0.0

        transaction_data = []

        for transaction in transactions:

            amount = float(
                transaction.amount or 0
            )

            transaction_type = (
                transaction.transaction_type
                or ""
            ).lower().strip()

            # -------------------------------------------------
            # CREDIT / DEBIT
            # -------------------------------------------------

            if transaction_type in CREDIT_TYPES:
                transaction_direction = "credit"
                customer_credit += amount

            elif transaction_type in DEBIT_TYPES:
                transaction_direction = "debit"
                customer_debit += amount

            else:
                # Unknown type ko guess nahi karenge.
                # Original transaction_type preserve rahega.
                transaction_direction = "other"

            # -------------------------------------------------
            # TRANSACTION RESPONSE
            # -------------------------------------------------

            transaction_data.append(
                {
                    "id": str(transaction.id),

                    "amount": round(
                        amount,
                        2,
                    ),

                    "transaction_type":
                        transaction.transaction_type,

                    "direction":
                        transaction_direction,

                    "meal_type":
                        transaction.meal_type,

                    "subscription_id":
                        (
                            str(transaction.subscription_id)
                            if transaction.subscription_id
                            else None
                        ),

                    "schedule_id":
                        (
                            str(transaction.schedule_id)
                            if transaction.schedule_id
                            else None
                        ),

                    "description":
                        transaction.description,

                    "created_at":
                        (
                            transaction.created_at.isoformat()
                            if transaction.created_at
                            else None
                        ),
                }
            )

        # -------------------------------------------------
        # SUBSCRIPTION RESPONSE
        # -------------------------------------------------

        subscription_data = []

        for subscription in subscriptions:

            subscription_data.append(
                {
                    "id": str(subscription.id),

                    "plan":
                        getattr(
                            subscription,
                            "plan",
                            None,
                        ),

                    "plan_type":
                        getattr(
                            subscription,
                            "plan_type",
                            None,
                        ),

                    "status":
                        subscription.status,

                    "start_date":
                        (
                            subscription.start_date.isoformat()
                            if subscription.start_date
                            else None
                        ),

                    "end_date":
                        (
                            subscription.end_date.isoformat()
                            if subscription.end_date
                            else None
                        ),
                }
            )

        # -------------------------------------------------
        # CUSTOMER TOTALS
        # -------------------------------------------------

        total_wallet_balance += balance
        total_credits += customer_credit
        total_debits += customer_debit
        total_transactions += len(
            transactions
        )

        # -------------------------------------------------
        # CUSTOMER RESULT
        # -------------------------------------------------

        result.append(
            {
                "customer": {
                    "id": str(customer.id),

                    "name":
                        customer.name,

                    "email":
                        customer.email,

                    "phone":
                        customer.phone,

                    "profile_image":
                        customer.profile_image,

                    "is_active":
                        customer.is_active,

                    "created_at":
                        (
                            customer.created_at.isoformat()
                            if customer.created_at
                            else None
                        ),
                },

                "wallet": {
                    "exists":
                        wallet is not None,

                    "wallet_id":
                        (
                            str(wallet.id)
                            if wallet
                            else None
                        ),

                    "balance":
                        round(
                            balance,
                            2,
                        ),

                    "total_credit":
                        round(
                            customer_credit,
                            2,
                        ),

                    "total_debit":
                        round(
                            customer_debit,
                            2,
                        ),

                    "transaction_count":
                        len(transactions),

                    "transactions":
                        transaction_data,
                },

                "subscriptions": {
                    "count":
                        len(subscriptions),

                    "history":
                        subscription_data,
                },
            }
        )

    # =====================================================
    # FINAL RESPONSE
    # =====================================================

    return {
        "success": True,

        "stats": {
            "total_wallet_balance":
                round(
                    total_wallet_balance,
                    2,
                ),

            "total_credits":
                round(
                    total_credits,
                    2,
                ),

            "total_debits":
                round(
                    total_debits,
                    2,
                ),

            "total_transactions":
                total_transactions,

            "subscribed_customers":
                len(customers),
        },

        "customers":
            result,
    }