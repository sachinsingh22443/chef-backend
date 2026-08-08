import uuid

from sqlalchemy.orm import Session

from app.models.wallet import Wallet
from app.models.wallet_transaction import WalletTransaction


def get_or_create_wallet(
    db: Session,
    user_id: uuid.UUID,
) -> Wallet:
    """
    Customer ka wallet return karta hai.
    Wallet nahi hai to naya wallet create karta hai.
    """

    wallet = (
        db.query(Wallet)
        .filter(Wallet.user_id == user_id)
        .first()
    )

    if wallet:
        return wallet

    wallet = Wallet(
        user_id=user_id,
        balance=0.0,
    )

    db.add(wallet)
    db.flush()

    return wallet


def credit_wallet(
    db: Session,
    user_id: uuid.UUID,
    amount: float,
    transaction_type: str,
    description: str | None = None,
    meal_type: str | None = None,
    subscription_id: uuid.UUID | None = None,
    schedule_id: uuid.UUID | None = None,
) -> Wallet:
    """
    Customer wallet mein amount credit karta hai
    aur wallet transaction create karta hai.
    """

    if amount <= 0:
        raise ValueError(
            "Wallet credit amount must be greater than zero"
        )

    wallet = get_or_create_wallet(
        db=db,
        user_id=user_id,
    )

    wallet.balance += amount

    transaction = WalletTransaction(
        wallet_id=wallet.id,
        user_id=user_id,
        amount=amount,
        transaction_type=transaction_type,
        meal_type=meal_type,
        subscription_id=subscription_id,
        schedule_id=schedule_id,
        description=description,
    )

    db.add(transaction)
    db.flush()

    return wallet


def debit_wallet(
    db: Session,
    user_id: uuid.UUID,
    amount: float,
    transaction_type: str,
    description: str | None = None,
    meal_type: str | None = None,
    subscription_id: uuid.UUID | None = None,
    schedule_id: uuid.UUID | None = None,
) -> Wallet:
    """
    Customer wallet se amount deduct karta hai
    aur wallet transaction create karta hai.
    """

    if amount <= 0:
        raise ValueError(
            "Wallet debit amount must be greater than zero"
        )

    wallet = get_or_create_wallet(
        db=db,
        user_id=user_id,
    )

    if wallet.balance < amount:
        raise ValueError(
            "Insufficient wallet balance"
        )

    wallet.balance -= amount

    transaction = WalletTransaction(
        wallet_id=wallet.id,
        user_id=user_id,
        amount=-amount,
        transaction_type=transaction_type,
        meal_type=meal_type,
        subscription_id=subscription_id,
        schedule_id=schedule_id,
        description=description,
    )

    db.add(transaction)
    db.flush()

    return wallet