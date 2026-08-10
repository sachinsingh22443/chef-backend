from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.wallet import Wallet
from app.models.wallet_transaction import WalletTransaction
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

        # Next day midnight use kar rahe hain
        # taaki selected to_date ka pura din include ho.

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