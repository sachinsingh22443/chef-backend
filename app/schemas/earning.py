from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class EarningResponse(BaseModel):
    id: UUID
    amount: float
    created_at: datetime

    class Config:
        from_attributes = True