from pydantic import BaseModel
from uuid import UUID
from typing import Optional


class TomorrowSpecialCreate(BaseModel):
    dish_name: str
    description: Optional[str] = None

    price: float
    original_price: Optional[float] = None

    max_plates: int
    cutoff_time: str

    calories: Optional[int] = None
    protein: Optional[float] = None
    carbs: Optional[float] = None
    fats: Optional[float] = None

    preparation_time: Optional[int] = None
    ingredients: Optional[str] = None


class TomorrowSpecialResponse(BaseModel):
    id: UUID

    dish_name: str
    description: Optional[str]

    # 💰 Pricing
    price: float
    original_price: Optional[float]

    # 🥗 Nutrition
    calories: Optional[int]
    protein: Optional[float]
    carbs: Optional[float]
    fats: Optional[float]

    # 🍳 Preparation
    preparation_time: Optional[int]

    # 🧂 Ingredients
    ingredients: Optional[str]

    # 📦 Quantity
    max_plates: int
    pre_orders: int
    remaining: int

    # ⏰ Timing
    cutoff_time: str

    # 🖼️ Image
    image_url: Optional[str]

    # 🌱 Food Type
    food_type: str

    # 👨‍🍳 Chef
    chef_id: UUID
    chef_name: str

    # 📊 Status
    is_active: int

    class Config:
        from_attributes = True


class PreOrderCreate(BaseModel):
    special_id: UUID
    quantity: int = 1
    
