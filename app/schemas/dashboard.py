from pydantic import BaseModel
from typing import List

class WeeklyData(BaseModel):
    day: str
    earnings: float


class DashboardResponse(BaseModel):
    total_orders: int
    total_earnings: float
    today_earnings: float
    avg_rating: float
    weekly_data: List[WeeklyData]