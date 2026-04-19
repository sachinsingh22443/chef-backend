# app/api/routes/notifications.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from app.api.deps import get_db, get_current_user
from app.models.notification import Notification

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# 🔥 TIME FORMAT FUNCTION
def time_ago(dt):
    diff = datetime.utcnow() - dt

    if diff.seconds < 60:
        return "Just now"
    elif diff.seconds < 3600:
        return f"{diff.seconds // 60} min ago"
    elif diff.seconds < 86400:
        return f"{diff.seconds // 3600} hr ago"
    else:
        return f"{diff.days} day ago"


# 🔥 FORMAT FUNCTION
def format_notification(n):
    return {
        "id": str(n.id),
        "type": n.type,
        "title": n.title,
        "message": n.message,
        "unread": not n.is_read,
        "time": time_ago(n.created_at)
    }


# ✅ GET ALL NOTIFICATIONS
@router.get("/")
def get_notifications(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    notifications = db.query(Notification)\
        .filter(Notification.user_id == user.id)\
        .order_by(Notification.created_at.desc())\
        .all()

    return [format_notification(n) for n in notifications]


# ✅ MARK SINGLE AS READ
@router.put("/{id}/read")
def mark_read(
    id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    notif = db.query(Notification)\
        .filter(Notification.id == id, Notification.user_id == user.id)\
        .first()

    if notif:
        notif.is_read = True
        db.commit()

    return {"message": "read"}


# ✅ MARK ALL AS READ
@router.put("/mark-all-read")
def mark_all_read(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    db.query(Notification)\
        .filter(Notification.user_id == user.id)\
        .update({"is_read": True})

    db.commit()

    return {"message": "all read"}


# 🔥 CREATE NOTIFICATION (VERY IMPORTANT)
@router.post("/create")
def create_notification(
    type: str,
    title: str,
    message: str,
    user_id: str,
    db: Session = Depends(get_db)
):
    notif = Notification(
        user_id=user_id,
        type=type,
        title=title,
        message=message
    )

    db.add(notif)
    db.commit()

    return {"message": "notification created"}