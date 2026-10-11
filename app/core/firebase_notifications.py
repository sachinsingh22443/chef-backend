
from firebase_admin import messaging

from app.core.firebase import initialize_firebase


def send_push_notification(
    token: str,
    title: str,
    message: str,
) -> str:
    initialize_firebase()

    notification = messaging.Notification(
        title=title,
        body=message,
    )

    android_config = messaging.AndroidConfig(
        priority="high",
        notification=messaging.AndroidNotification(
            channel_id="chef_notifications",
            sound="default",
        ),
    )

    push_message = messaging.Message(
        token=token,
        notification=notification,
        android=android_config,
    )

    return messaging.send(push_message)
