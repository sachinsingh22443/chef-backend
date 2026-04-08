from pydantic import BaseModel
from uuid import UUID

class ReviewCreate(BaseModel):
    chef_id: UUID
    rating: int
    comment: str


class ReviewResponse(BaseModel):
    id: UUID
    rating: int
    comment: str

    class Config:
        from_attributes = True