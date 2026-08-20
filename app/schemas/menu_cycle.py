from pydantic import BaseModel, Field
from uuid import UUID
from datetime import date


# =========================================================
# 30-DAY MENU CYCLE ITEM
# =========================================================

class MenuCycleItemCreate(BaseModel):
    cycle_day: int = Field(..., ge=1, le=30)
    menu_id: UUID


# =========================================================
# CREATE / UPDATE COMPLETE CYCLE
# =========================================================

class MenuCycleBulkCreate(BaseModel):
    cycle_start_date: date
    items: list[MenuCycleItemCreate]


# =========================================================
# CYCLE ITEM RESPONSE
# =========================================================

class MenuCycleItemResponse(BaseModel):
    id: UUID
    chef_id: UUID
    menu_id: UUID
    cycle_day: int
    cycle_start_date: date

    class Config:
        from_attributes = True


# =========================================================
# COMPLETE CYCLE RESPONSE
# =========================================================

class MenuCycleResponse(BaseModel):
    cycle_start_date: date
    total_days: int
    items: list[MenuCycleItemResponse]


# =========================================================
# DATE OVERRIDE
# =========================================================

class MenuDateOverrideCreate(BaseModel):
    menu_date: date
    menu_id: UUID


class MenuDateOverrideResponse(BaseModel):
    id: UUID
    chef_id: UUID
    menu_id: UUID
    menu_date: date

    class Config:
        from_attributes = True