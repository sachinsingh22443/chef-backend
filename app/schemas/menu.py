from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID

class MenuBase(BaseModel):
    name: str
    description: Optional[str]
    price: float

    prep_time: Optional[int]
    quantity: Optional[int]

    category: Optional[str]
    food_type: Optional[str]

    calories: Optional[int]
    protein: Optional[float]
    carbs: Optional[float]
    fats: Optional[float]

    ingredients: Optional[List[str]]


class MenuCreate(MenuBase):
    pass


from pydantic import BaseModel
from typing import Optional, List

class MenuUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    prep_time: Optional[int] = None
    quantity: Optional[int] = None
    category: Optional[str] = None
    food_type: Optional[str] = None

    calories: Optional[int] = None
    protein: Optional[float] = None
    carbs: Optional[float] = None
    fats: Optional[float] = None

    ingredients: Optional[List[str]] = None

class MenuResponse(MenuBase):
    id: UUID
    chef_id: UUID
    image_urls: Optional[List[str]]

    class Config:
        from_attributes = True