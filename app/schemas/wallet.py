from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class WalletTransactionOut(BaseModel):
    id: UUID

    amount: float
    transaction_type: str

    meal_type: str | None = None

    subscription_id: UUID | None = None
    schedule_id: UUID | None = None

    description: str | None = None

    created_at: datetime

    class Config:
        from_attributes = True


class WalletHistoryResponse(BaseModel):
    balance: float
    transactions: list[WalletTransactionOut]