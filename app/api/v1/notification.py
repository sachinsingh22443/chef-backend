from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from app.api.deps import get_db, get_current_user
from app.models.notification import Notification

router = APIRouter(prefix="/notifications", tags=["Notifications"])


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

    return notifications


@router.put("/{id}/read")
def mark_read(id: str, db: Session = Depends(get_db)):
    notif = db.query(Notification).filter(Notification.id == id).first()
    if notif:
        notif.is_read = True
        db.commit()
    return {"msg": "read"}


@router.put("/mark-all-read")
def mark_all(db: Session = Depends(get_db), user=Depends(get_current_user)):
    db.query(Notification)\
        .filter(Notification.user_id == user.id)\
        .update({"is_read": True})
    db.commit()
    return {"msg": "all read"}