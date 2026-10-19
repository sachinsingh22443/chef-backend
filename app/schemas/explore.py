
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


EXPLORE_CATEGORIES = (
    "Protein Rich",
    "Healthy",
    "Anytime",
    "Bulk Order",
)


class ExploreProductCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    description: str | None = None
    category: str
    price: float = Field(..., gt=0)
    image_url: str | None = None
    quantity: int = Field(..., ge=0)

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        value = value.strip()

        for category in EXPLORE_CATEGORIES:
            if value.casefold() == category.casefold():
                return category

        raise ValueError(
            "Category must be Protein Rich, Healthy, Anytime, or Bulk Order"
        )


class ExploreProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = None
    category: str | None = None
    price: float | None = Field(default=None, gt=0)
    image_url: str | None = None
    quantity: int | None = Field(default=None, ge=0)
    is_active: bool | None = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str | None) -> str | None:
        if value is None:
            return value

        value = value.strip()

        for category in EXPLORE_CATEGORIES:
            if value.casefold() == category.casefold():
                return category

        raise ValueError(
            "Category must be Protein Rich, Healthy, Anytime, or Bulk Order"
        )


class ExploreProductResponse(BaseModel):
    id: UUID
    chef_id: UUID
    name: str
    description: str | None = None
    category: str
    price: float
    image_url: str | None = None
    quantity: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExploreCategoryResponse(BaseModel):
    name: str
    product_count: int
