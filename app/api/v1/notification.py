# app/api/routes/notifications.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from app.api.deps import get_db, get_current_user
from app.models.notification import Notification


from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.fcm_device_token import FCMDeviceToken
from app.schemas.fcm_device_token import FCMDeviceTokenRequest
from app.core.firebase_notifications import send_push_notification


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




@router.post("/register-device")
def register_fcm_device(
    payload: FCMDeviceTokenRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    device = (
        db.query(FCMDeviceToken)
        .filter(FCMDeviceToken.token == payload.token)
        .first()
    )

    if device:
        device.user_id = current_user.id
    else:
        device = FCMDeviceToken(
            user_id=current_user.id,
            token=payload.token,
        )
        db.add(device)

    db.commit()

    return {"success": True, "message": "Device token registered"}


@router.post("/test-push")
def test_fcm_push(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    devices = (
        db.query(FCMDeviceToken)
        .filter(FCMDeviceToken.user_id == current_user.id)
        .all()
    )

    if not devices:
        raise HTTPException(
            status_code=404,
            detail="No FCM device token registered for this user",
        )

    results = []

    for device in devices:
        try:
            message_id = send_push_notification(
                token=device.token,
                title="Chef App Test",
                message="Push notification successfully received!",
            )
            results.append({
                "success": True,
                "message_id": message_id,
            })
        except Exception:
            results.append({
                "success": False,
                "message": "Push failed for this device",
            })

    if not any(result["success"] for result in results):
        raise HTTPException(
            status_code=502,
            detail={"message": "FCM could not deliver the test push", "results": results},
        )

    return {"success": True, "results": results}
