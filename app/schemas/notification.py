# app/schemas/notification.py

from pydantic import BaseModel
from uuid import UUID


class NotificationResponse(BaseModel):
    id: UUID
    type: str
    title: str
    message: str
    unread: bool   # 🔥 frontend compatible
    time: str      # 🔥 formatted time

    class Config:
        from_attributes = True